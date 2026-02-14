"""Artifact Vault stack – API Gateway, Lambda, DynamoDB, S3."""

import os

import aws_cdk as cdk
from aws_cdk import aws_apigateway as apigw
from aws_cdk import aws_cognito as cognito
from aws_cdk import aws_dynamodb as dynamodb
from aws_cdk import aws_lambda as lambda_
from aws_cdk import aws_s3 as s3
from constructs import Construct


class ArtifactVaultStack(cdk.Stack):
    """
    Serverless stack for Artifact Vault.
    Includes: DynamoDB table (artifact metadata), S3 bucket (artifact files).
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # DynamoDB: artifact metadata (id, title, description, tags, status, timestamps, owner_id, file_keys)
        # Query by owner (partition key); get/query by artifact id (sort key or GSI).
        self.artifacts_table = dynamodb.Table(
            self,
            "ArtifactsTable",
            table_name="artifact-vault-artifacts",
            partition_key=dynamodb.Attribute(
                name="owner_id",
                type=dynamodb.AttributeType.STRING,
            ),
            sort_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
            billing_mode=dynamodb.BillingMode.PAY_PER_REQUEST,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        # GSI: look up by artifact id without knowing owner
        self.artifacts_table.add_global_secondary_index(
            index_name="ById",
            partition_key=dynamodb.Attribute(
                name="id",
                type=dynamodb.AttributeType.STRING,
            ),
            projection_type=dynamodb.ProjectionType.ALL,
        )

        # S3: artifact file storage; keys should include owner and artifact context (e.g. {owner_id}/{artifact_id}/...)
        self.artifacts_bucket = s3.Bucket(
            self,
            "ArtifactsBucket",
            block_public_access=s3.BlockPublicAccess.BLOCK_ALL,
            encryption=s3.BucketEncryption.S3_MANAGED,
            versioned=True,
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )

        # Lambda: artifact CRUD (create, list, get, update, delete); placeholder owner until auth
        handler_dir = os.path.join(os.path.dirname(__file__), "functions", "artifact_crud")
        self.artifact_crud_function = lambda_.Function(
            self,
            "ArtifactCrudFunction",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=lambda_.Code.from_asset(handler_dir),
            environment={
                "ARTIFACTS_TABLE_NAME": self.artifacts_table.table_name,
                "ARTIFACTS_BUCKET_NAME": self.artifacts_bucket.bucket_name,
            },
        )
        self.artifacts_table.grant_read_write_data(self.artifact_crud_function)
        self.artifacts_bucket.grant_read_write(self.artifact_crud_function)

        # Cognito User Pool for authentication
        self.user_pool = cognito.UserPool(
            self,
            "UserPool",
            user_pool_name="artifact-vault-users",
            self_sign_up_enabled=True,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=8,
                require_lowercase=True,
                require_uppercase=True,
                require_digits=True,
                require_symbols=False,
            ),
            removal_policy=cdk.RemovalPolicy.RETAIN,
        )
        self.user_pool_client = self.user_pool.add_client(
            "WebClient",
            user_pool_client_name="artifact-vault-web",
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True,
            ),
            generate_secret=False,
        )

        # Cognito Identity Pool (federated with User Pool) for future use (e.g. direct AWS credential access)
        self.identity_pool = cognito.CfnIdentityPool(
            self,
            "IdentityPool",
            identity_pool_name="artifact_vault_identity_pool",
            allow_unauthenticated_identities=False,
            cognito_identity_providers=[
                cognito.CfnIdentityPool.CognitoIdentityProviderProperty(
                    client_id=self.user_pool_client.user_pool_client_id,
                    provider_name=self.user_pool.user_pool_provider_name,
                ),
            ],
        )

        # API Gateway: REST API with Cognito authorizer
        api = apigw.RestApi(
            self,
            "ArtifactVaultApi",
            rest_api_name="artifact-vault-api",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "Authorization"],
            ),
        )
        cognito_authorizer = apigw.CognitoUserPoolsAuthorizer(
            self,
            "CognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name="artifact-vault-cognito",
            identity_source="method.request.header.Authorization",
        )
        method_options = apigw.MethodOptions(authorizer=cognito_authorizer)

        crud_integration = apigw.LambdaIntegration(
            self.artifact_crud_function,
            proxy=True,
        )
        artifacts = api.root.add_resource("artifacts")
        artifacts.add_method("GET", crud_integration, method_options)
        artifacts.add_method("POST", crud_integration, method_options)
        artifact_id = artifacts.add_resource("{id}")
        artifact_id.add_method("GET", crud_integration, method_options)
        artifact_id.add_method("PUT", crud_integration, method_options)
        artifact_id.add_method("PATCH", crud_integration, method_options)
        artifact_id.add_method("DELETE", crud_integration, method_options)
        upload_urls = artifact_id.add_resource("upload-urls")
        upload_urls.add_method("POST", crud_integration, method_options)
        files_resource = artifact_id.add_resource("files")
        file_filename = files_resource.add_resource("{filename}")
        file_filename.add_method("GET", crud_integration, method_options)

        # Stack outputs for front-end config
        cdk.CfnOutput(
            self,
            "ApiEndpointUrl",
            value=api.url,
            description="Artifact Vault API base URL",
            export_name="ArtifactVaultApiEndpointUrl",
        )
        cdk.CfnOutput(
            self,
            "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID for front-end auth",
            export_name="ArtifactVaultUserPoolId",
        )
        cdk.CfnOutput(
            self,
            "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID for front-end auth",
            export_name="ArtifactVaultUserPoolClientId",
        )
        cdk.CfnOutput(
            self,
            "IdentityPoolId",
            value=self.identity_pool.ref,
            description="Cognito Identity Pool ID (optional, for direct AWS credentials)",
            export_name="ArtifactVaultIdentityPoolId",
        )
        cdk.CfnOutput(
            self,
            "Region",
            value=self.region,
            description="AWS Region (for front-end Cognito config)",
            export_name="ArtifactVaultRegion",
        )
