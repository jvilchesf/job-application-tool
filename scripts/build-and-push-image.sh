#!/bin/bash
# =============================================================================
# Build Docker image and load into Kind cluster
# =============================================================================
# Usage: ./build-and-push-image.sh <service-name>
# Example: ./build-and-push-image.sh scraper

set -e

SERVICE_NAME="${1:-scraper}"
IMAGE_NAME="${SERVICE_NAME}-image"
DOCKERFILE="docker/${SERVICE_NAME}.Dockerfile"

echo "=============================================="
echo "Building Docker image for: ${SERVICE_NAME}"
echo "=============================================="

# Check if Dockerfile exists
if [ ! -f "$DOCKERFILE" ]; then
    echo "Error: Dockerfile not found at ${DOCKERFILE}"
    echo "Available Dockerfiles:"
    ls -la docker/*.Dockerfile 2>/dev/null || echo "  None found"
    exit 1
fi

# Build the Docker image
echo "Building image: ${IMAGE_NAME}"
docker build -t "${IMAGE_NAME}" -f "${DOCKERFILE}" .

# Check if Kind is available and load image
if command -v kind &> /dev/null; then
    # Get cluster name (default: knowbe4, or first available)
    CLUSTER_NAME=$(kind get clusters 2>/dev/null | head -n1)

    if [ -n "$CLUSTER_NAME" ]; then
        echo "Loading image into Kind cluster: ${CLUSTER_NAME}"
        kind load docker-image "${IMAGE_NAME}" --name "${CLUSTER_NAME}"
        echo "Image loaded successfully!"
    else
        echo "No Kind cluster found. Image built locally only."
        echo "To create a cluster: kind create cluster --name <cluster-name>"
    fi
else
    echo "Kind not installed. Image built locally only."
    echo "To install Kind: https://kind.sigs.k8s.io/docs/user/quick-start/"
fi

echo ""
echo "Build complete: ${IMAGE_NAME}"
echo "=============================================="
