# Environment Setup

This project uses environment variables to store sensitive configuration data. Follow these steps to set up your environment:

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit the `.env` file and replace the placeholder values with your actual:
   - `CALENDAR_ID`: Your Google Calendar ID
   - `FROM_EMAIL`: Your Gmail address (sender)
   - `TO_EMAIL`: Recipient email address
   - `GMAIL_APP_PASSWORD`: Your Gmail app password

3. The `.env` file is already added to `.gitignore` and will not be tracked by Git.

## Required Environment Variables

### Email and Calendar
- `CALENDAR_ID`: The ID of the Google Calendar to fetch events from
- `FROM_EMAIL`: Gmail address used to send emails
- `TO_EMAIL`: Email address to send invoices to
- `GMAIL_APP_PASSWORD`: Gmail app password for authentication

### Google OAuth Credentials
- `GOOGLE_CLIENT_ID`: Google OAuth client ID from Google Cloud Console
- `GOOGLE_PROJECT_ID`: Google Cloud project ID
- `GOOGLE_CLIENT_SECRET`: Google OAuth client secret

## Getting Google OAuth Credentials

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the Google Calendar API
4. Go to "Credentials" and create OAuth 2.0 client credentials
5. Download the credentials and extract the values for your `.env` file
6. Note that you may need to add a test user email address

Make sure all these variables are set in your `.env` file before running the application.