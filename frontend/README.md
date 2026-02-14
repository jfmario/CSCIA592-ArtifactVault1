# Artifact Vault – Front-end

Single-page app (one HTML file) that uses **Cognito User Pool** for sign-in and talks to the Artifact Vault API.

## Prerequisites

- Deployed CDK stack (so you have API URL, User Pool ID, Client ID, Region).
- A local HTTP server (browsers require HTTP for Cognito and cross-origin API calls).

## Quick start

1. Get these from the CDK stack outputs after `cdk deploy`:
   - **ApiEndpointUrl**
   - **UserPoolId**
   - **UserPoolClientId**
   - **Region**

2. Serve the folder over HTTP, for example:
   ```bash
   npx serve -l 3000
   ```
   or:
   ```bash
   python3 -m http.server 3000
   ```
   (Run from this `frontend` directory.)

3. Open **http://localhost:3000** in your browser.

4. On first load, fill in the **Configuration** form with the four values above and click **Save and reload**.

5. **Sign up** (create account). If email verification is enabled, check your email for a code and enter it in the **Confirm** form, then **Sign in**. After that you can:
   - Create, list, view, edit, and delete artifacts.
   - Upload one or more files to an artifact (View → Upload file(s)).
   - Download files (View → click Download next to a file).

## Features

- **Auth**: Sign up, sign in, sign out via Cognito User Pool (AWS Amplify Auth).
- **Artifacts**: Create (title, description, tags, status), list with filters, view, edit, delete.
- **Files**: Upload files to an artifact (presigned S3 URLs); download via presigned URL.

## Config storage

Configuration is stored in the browser’s `localStorage` under keys `av_apiUrl`, `av_region`, `av_userPoolId`, `av_clientId`. To switch to another stack or environment, re-enter the values in the Configuration form and save.
