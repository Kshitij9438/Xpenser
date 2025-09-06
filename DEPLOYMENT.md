# Railway Deployment Guide

## Prerequisites
1. Railway account (https://railway.app)
2. Google AI API key
3. PostgreSQL database (Railway provides this)

## Environment Variables
Set these in your Railway project settings:

### Required Variables:
- `GOOGLE_API_KEY` - Your Google AI API key
- `DATABASE_URL` - PostgreSQL connection string (Railway will provide this)

### Optional Variables:
- `DEBUG` - Set to `false` for production
- `PORT` - Railway will set this automatically

## Deployment Steps

### 1. Connect to Railway
1. Go to https://railway.app
2. Click "New Project"
3. Select "Deploy from GitHub repo" (or upload your code)

### 2. Add Database
1. In your Railway project, click "New"
2. Select "Database" → "PostgreSQL"
3. Railway will automatically set the `DATABASE_URL` environment variable

### 3. Set Environment Variables
1. Go to your service settings
2. Add the following variables:
   - `GOOGLE_API_KEY`: Your Google AI API key
   - `DEBUG`: `false`

### 4. Deploy
1. Railway will automatically build and deploy your Docker container
2. The app will be available at the provided Railway URL

## Health Check
Your app includes a health check endpoint at `/health` that Railway will use to monitor the service.

## Logs
View logs in the Railway dashboard under your service's "Deployments" tab.

## Troubleshooting
- Check that all environment variables are set correctly
- Ensure your Google API key has the necessary permissions
- Verify the database connection is working
- Check the logs for any startup errors
