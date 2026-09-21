# Deployment Guide

This project supports deployment to Azure using Docker containers.

## Prerequisites

- Azure subscription
- Azure Container Registry (ACR)
- Azure App Service (container-based)
- Azure CLI installed
- Docker installed

## Setup for Your Azure Resources

### Option 1: Manual Deployment Scripts

1. **Edit the deployment script**:
   - `scripts/deploy.sh`

2. **Update these values**:
   ```bash
   ACR_NAME="your-acr-name"
   APP_NAME="your-app-name" 
   RESOURCE_GROUP="your-resource-group"
   ```

3. **Run the script**:
   ```bash
   ./scripts/deploy.sh
   ```

### Option 2: GitHub Actions (Recommended)

1. **Set GitHub Secrets** in your repository settings:
   - `AZURE_CLIENT_ID` - Your Azure service principal client ID
   - `AZURE_TENANT_ID` - Your Azure tenant ID
   - `AZURE_SUBSCRIPTION_ID` - Your Azure subscription ID

2. **Set GitHub Variables** in your repository settings:
   - `ACR_NAME` - Your Azure Container Registry name
   - `APP_NAME` - Your Azure App Service name
   - `RESOURCE_GROUP` - Your Azure resource group name

3. **Push to main** - The workflow will automatically deploy

## Security Notes

- **No secrets in code** - All sensitive values are placeholders
- **GitHub Secrets** - Use GitHub's secret management for credentials
- **GitHub Variables** - Use GitHub variables for resource names (not secrets)
- **Environment-specific** - Customize scripts for your environment only

## Local Testing

Before deploying, test locally:

```bash
# Build and run locally
docker-compose up -d --build

# Test the app
curl http://localhost:5000

# Check logs
docker-compose logs -f web
```

## Troubleshooting

- **Template not found**: Ensure templates/ folder is copied in Dockerfile
- **Playwright errors**: Check that PLAYWRIGHT_BROWSERS_PATH is set correctly
- **Permission errors**: Verify non-root user has access to browser cache

## Production Considerations

- Use a production WSGI server (gunicorn) instead of Flask dev server
- Set `WEBSITES_PORT=5000` in Azure App Service settings if using port 5000
- Configure proper logging and monitoring
- Set up health checks and auto-restart policies