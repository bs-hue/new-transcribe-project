# Production Developer Handoff

Welcome to the project! This document outlines what has recently been built, the current state of the application, and the exact steps required from you to get this application safely deployed to production.

## 1. What was just built
The **User Account Security and Email Delivery** features are now 100% complete and integrated into both the frontend and backend. 

**Backend (`FastAPI`):**
- A new `email.py` service has been added to handle sending SMTP emails (supporting both plain text and HTML fallback).
- API routes (`/api/v1/auth/recover-password`, `/api/v1/auth/reset-password`) are fully implemented and tied into the custom JWT authentication system.
- Tokens securely expire and are hashed in the database.

**Frontend (`React + Vite`):**
- Users can now click "Forgot Password" from the login page, enter their email, and receive a secure link.
- Users can access the "Account & Security" section in their Dashboard to manually change their password or dispatch an email link to themselves.

## 2. Your Responsibilities for Production Deployment

To take this application live, you must complete the following steps to configure the production environment.

### A. Real SMTP Provider Configuration
During local development, we used personal/testing email accounts (like Zoho or Gmail). **For production, you must configure a robust SMTP provider.**
1. Create an account with a provider like **SendGrid**, **Amazon SES**, or **Resend**.
2. **Verify the production domain** within that provider's dashboard (this requires updating DNS records for the domain).
3. Generate the SMTP credentials.

### B. Environment Variables (`.env.production`)
You will find an `.env.production.example` file in the root directory. Copy it to `.env.production` on the production server and fill it out completely.
Pay special attention to the new `SMTP_*` block:
```env
SMTP_HOST=smtp.yourprovider.com
SMTP_PORT=465
SMTP_USER=your_smtp_username
SMTP_PASSWORD=your_secure_smtp_password
SMTP_FROM_EMAIL=support@yourverified-domain.com
SMTP_FROM_NAME="Content Research Hub"
SMTP_TLS=true
```

### C. Server & DNS Setup
1. Ensure the production server has ports `80` and `443` open.
2. Ensure the **DNS A-record** for your domain correctly points to the production server's IP address. Caddy relies on this to automatically provision the SSL (HTTPS) certificate.

### D. Production Database Security
If you are using the self-hosted PostgreSQL option provided in the docker-compose stack, ensure you generate strong, random passwords for the `POSTGRES_PASSWORD` and `JWT_SECRET` fields in the `.env.production` file. Do not reuse development keys.

## 3. Final Deployment Command
Once your `.env.production` is completely filled out and the DNS resolves, you can deploy the stack with a single command:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

Monitor the logs to ensure Caddy successfully negotiates the TLS certificate and the FastAPI backend successfully applies the database migrations:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production logs -f
```
