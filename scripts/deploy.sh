#!/bin/bash
# Deploy to Azure Container Registry and App Service
# 
# USAGE:
#   1. Set your Azure resource names below
#   2. Run: ./scripts/deploy.sh

set -e

# TODO: Update these values for your Azure resources
ACR_NAME="YOUR_ACR_NAME"
IMAGE_NAME="prayer-times-ics-generator"
TAG="latest"
APP_NAME="YOUR_APP_NAME"
RESOURCE_GROUP="YOUR_RESOURCE_GROUP"

# Check if values are customized
if [ "$ACR_NAME" = "YOUR_ACR_NAME" ] || [ "$APP_NAME" = "YOUR_APP_NAME" ] || [ "$RESOURCE_GROUP" = "YOUR_RESOURCE_GROUP" ]; then
    echo "Error: Please update the Azure resource names in this script first"
    echo "   Edit the ACR_NAME, APP_NAME, and RESOURCE_GROUP variables"
    exit 1
fi

echo "Logging in to Azure Container Registry..."
az acr login --name $ACR_NAME

echo "Building Docker image..."
docker build -t $IMAGE_NAME .

echo "Tagging image for ACR..."
docker tag $IMAGE_NAME $ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG

echo "Pushing image to ACR..."
docker push $ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG

echo "Updating Azure App Service..."
az webapp config container set \
    --name $APP_NAME \
    --resource-group $RESOURCE_GROUP \
    --docker-custom-image-name $ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG \
    --docker-registry-server-url https://$ACR_NAME.azurecr.io

echo "Deployment complete!"
echo "Your app should be available at: https://$APP_NAME.azurewebsites.net"
