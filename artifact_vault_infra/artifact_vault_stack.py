"""Artifact Vault stack – API Gateway, Lambda, DynamoDB, S3."""

import os

import aws_cdk as cdk
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
