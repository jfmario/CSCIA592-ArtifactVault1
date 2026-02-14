"""Artifact Vault stack – ready for API Gateway, Lambda, DynamoDB, and S3."""

import aws_cdk as cdk
from constructs import Construct


class ArtifactVaultStack(cdk.Stack):
    """
    Serverless stack for Artifact Vault.
    Suitable for adding: API Gateway, Lambda, DynamoDB, S3.
    No AWS resources are defined yet; add them in the next step.
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Ready for:
        # - aws_apigateway
        # - aws_lambda
        # - aws_dynamodb
        # - aws_s3
