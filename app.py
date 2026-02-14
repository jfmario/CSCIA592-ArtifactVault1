#!/usr/bin/env python3
"""Artifact Vault – CDK app entrypoint."""

import aws_cdk as cdk

from artifact_vault_infra.artifact_vault_stack import ArtifactVaultStack

app = cdk.App()
ArtifactVaultStack(app, "ArtifactVaultStack", description="Artifact Vault serverless stack (API Gateway, Lambda, DynamoDB, S3)")

app.synth()
