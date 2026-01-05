#!/bin/bash
# =============================================================================
# Deploy service to Kubernetes using Kustomize
# =============================================================================
# Usage: ./deploy.sh <service-name>
# Example: ./deploy.sh scraper

set -e

SERVICE_NAME="${1:-scraper}"
DEPLOY_DIR="deployments/${SERVICE_NAME}"
NAMESPACE="job-application"

echo "=============================================="
echo "Deploying service: ${SERVICE_NAME}"
echo "Namespace: ${NAMESPACE}"
echo "=============================================="

# Check if deployment directory exists
if [ ! -d "$DEPLOY_DIR" ]; then
    echo "Error: Deployment directory not found at ${DEPLOY_DIR}"
    echo "Available deployments:"
    ls -la deployments/ 2>/dev/null || echo "  None found"
    exit 1
fi

# Check if kustomization.yaml exists
if [ ! -f "${DEPLOY_DIR}/kustomization.yaml" ]; then
    echo "Error: kustomization.yaml not found in ${DEPLOY_DIR}"
    exit 1
fi

# Create namespace if it doesn't exist
echo "Creating namespace (if not exists)..."
kubectl create namespace "${NAMESPACE}" --dry-run=client -o yaml | kubectl apply -f -

# Clean up existing resources (ignore errors if not found)
echo "Cleaning up existing resources..."
kubectl delete -k "${DEPLOY_DIR}" --ignore-not-found=true 2>/dev/null || true

# Apply new resources
echo "Applying Kustomize resources..."
kubectl apply -k "${DEPLOY_DIR}"

echo ""
echo "=============================================="
echo "Deployment complete!"
echo "=============================================="
echo ""
echo "Useful commands:"
echo "  kubectl get pods -n ${NAMESPACE}"
echo "  kubectl get cronjobs -n ${NAMESPACE}"
echo "  kubectl logs -f deployment/${SERVICE_NAME} -n ${NAMESPACE}"
echo "  kubectl describe pod -l app=${SERVICE_NAME} -n ${NAMESPACE}"
