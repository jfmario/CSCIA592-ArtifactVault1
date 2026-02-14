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
  - `artifact_vault_stack.py` – Main stack (API Gateway, Lambda, DynamoDB, S3, Cognito)
  - `functions/artifact_crud/` – Lambda handler (CRUD + file upload/download)
- `frontend/` – Static single-page app (auth + artifacts UI)

## Running the front-end

1. **Deploy the stack** (if not already):
   ```bash
   cdk deploy
   ```
   Note the stack outputs: `ApiEndpointUrl`, `UserPoolId`, `UserPoolClientId`, `Region`.

2. **Configure the app**: Open `frontend/index.html` in a browser (or serve it locally). On first load you’ll see a **Configuration** form. Enter:
   - **API base URL** – from `ApiEndpointUrl` (include the trailing slash, e.g. `https://xxx.execute-api.us-east-1.amazonaws.com/prod/`)
   - **AWS Region** – e.g. `us-east-1`
   - **User Pool ID** – from `UserPoolId`
   - **User Pool Client ID** – from `UserPoolClientId`  
   Click **Save and reload**. Values are stored in `localStorage`.

3. **Serve the front-end over HTTP** (required for Cognito and CORS):
   ```bash
   cd frontend
   npx serve -l 3000
   ```
   Or: `python -m http.server 3000` (from the `frontend` directory).  
   Open **http://localhost:3000** (or the port you used).

4. **Sign up** with a new username, email, and password (min 8 chars, upper, lower, digit). Then **sign in**. You can create artifacts, list/view/edit/delete them, and upload or download files.
