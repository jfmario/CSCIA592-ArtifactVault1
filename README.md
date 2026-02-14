# Artifact Vault – CDK Infrastructure

Python AWS CDK app for the Artifact Vault serverless project. The default stack is set up for API Gateway, Lambda, DynamoDB, and S3 (no resources defined yet).

## Prerequisites

- Python 3.9+
- Node.js 18+ (for the CDK CLI)

## Setup

```bash
# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install CDK CLI (once, if needed)
npm install -g aws-cdk
```

## Commands

```bash
cdk synth      # Synthesize CloudFormation template
cdk diff       # Compare deployed stack with current state
cdk deploy     # Deploy the stack (when resources are added)
```

## Project layout

- `app.py` – CDK app entrypoint
- `artifact_vault_infra/` – Stack and constructs
  - `artifact_vault_stack.py` – Main stack (ready for API Gateway, Lambda, DynamoDB, S3)
