#!/bin/bash

# Build and Deploy script for Motherstream Staging Environment
# Builds Docker images and deploys using Kustomize

set -e

echo "🏗️  Building and Deploying Motherstream STAGING environment..."
echo ""

# Ensure we're in the k8s directory
cd "$(dirname "$0")"
PROJECT_ROOT="$(dirname "$(pwd)")"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored messages
print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Check if minikube is running
print_info "Checking minikube status..."
if ! minikube status &> /dev/null; then
    print_error "Minikube is not running!"
    echo "Please start minikube first:"
    echo "  minikube start"
    exit 1
fi
print_success "Minikube is running"

# Build images on host (has internet access), then load into minikube
# This avoids network connectivity issues inside minikube's Docker daemon
print_info "Building images on host Docker daemon..."
print_info "Images will be built locally and then loaded into minikube"

echo ""
echo "🔨 Building Docker Images..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
print_info "Building images with tag: staging"
print_info "Kubernetes will use these local images via imagePullPolicy: Always"
echo ""

# Build Backend (Motherstream)
print_info "Building Motherstream backend..."
cd "$PROJECT_ROOT"
docker build -t motherstream:staging \
    -f Dockerfile . 2>&1 | grep -E "^Step|Successfully|ERROR" || true
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    print_success "Motherstream backend built successfully"
    print_info "Loading Motherstream backend into minikube..."
    minikube image load motherstream:staging
    print_success "Image loaded into minikube"
else
    print_error "Failed to build Motherstream backend"
    exit 1
fi 
# Build Frontend
print_info "Building Frontend..."
cd "$PROJECT_ROOT/frontend"

# Build with staging API URL as build arg (though it's mainly used at runtime in dev mode)
docker build \
    --build-arg VITE_API_URL=https://staging.motherstream.live/backend \
    -t frontend:staging \
    -f Dockerfile . 2>&1 | grep -E "^Step|Successfully|ERROR" || true

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    print_success "Frontend built successfully"
    print_info "Loading Frontend into minikube..."
    minikube image load frontend:staging
    print_success "Image loaded into minikube"
else
    print_error "Failed to build Frontend"
    exit 1
fi

# Build NGINX RTMP
print_info "Building NGINX RTMP server..."
cd "$PROJECT_ROOT/nginx-config"
docker build -t nginx-rtmp:staging \
    -f Dockerfile . 2>&1 | grep -E "^Step|Successfully|ERROR" || true
if [ ${PIPESTATUS[0]} -eq 0 ]; then
    print_success "NGINX RTMP server built successfully"
    print_info "Loading NGINX RTMP server into minikube..."
    minikube image load nginx-rtmp:staging
    print_success "Image loaded into minikube"
else
    print_error "Failed to build NGINX RTMP server"
    exit 1
fi

echo ""
print_success "All images built and loaded successfully!"
print_info "Images are ready for deployment in minikube"

# List built images on host
echo ""
echo "📦 Built Images (on host):"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
docker images | grep -E "(motherstream|frontend|nginx-rtmp).*staging" | head -10 || print_warning "No staging images found"

echo ""
echo "🚀 Deploying to Kubernetes..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

echo "🔍 Images in minikube:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
minikube image list


# Return to k8s directory
cd "$PROJECT_ROOT/k8s"

# Create staging data directories if they don't exist
print_info "Creating staging data directories..."
mkdir -p "$PROJECT_ROOT/staging/pgdata/data"
mkdir -p "$PROJECT_ROOT/staging/stream-recordings"
mkdir -p "$PROJECT_ROOT/staging/oryx"
mkdir -p "$PROJECT_ROOT/staging/certs"
print_success "Data directories created"

# Build and apply staging configuration
print_info "Building staging configuration with Kustomize..."
kubectl kustomize overlays/staging > /tmp/staging-manifest.yaml

print_info "Applying staging manifests..."
kubectl apply -f /tmp/staging-manifest.yaml

# Wait for staging infrastructure to be ready
echo ""
print_info "Waiting for staging infrastructure services to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres,environment=staging -n motherstream --timeout=300s 2>&1 || print_warning "Postgres not ready yet"
kubectl wait --for=condition=ready pod -l app=jaeger,environment=staging -n motherstream --timeout=300s 2>&1 || print_warning "Jaeger not ready yet"

# Wait for staging application services
print_info "Waiting for staging application services to be ready..."
kubectl wait --for=condition=ready pod -l app=motherstream,environment=staging -n motherstream --timeout=300s 2>&1 || print_warning "Motherstream not ready yet"
kubectl wait --for=condition=ready pod -l app=frontend,environment=staging -n motherstream --timeout=300s 2>&1 || print_warning "Frontend not ready yet"
kubectl wait --for=condition=ready pod -l app=nginx-rtmp,environment=staging -n motherstream --timeout=300s 2>&1 || print_warning "NGINX RTMP not ready yet"

echo ""
print_success "Staging deployment completed!"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🌐 Staging Services Access"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Local Development (NodePort):"
echo "  • Frontend:        http://localhost:30173"
echo "  • Motherstream API: http://localhost:30483"
echo "  • Jaeger UI:       http://localhost:30686"
echo "  • Oryx:            http://localhost:30800"
echo "  • NGINX RTMP:      http://localhost:30080"
echo ""
echo "External Access (Ingress):"
echo "  • Frontend:        https://staging.motherstream.live"
echo "  • Backend API:     https://staging.motherstream.live/backend"
echo "  • Legacy API:      https://staging.always12.live"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Useful Commands"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Check deployment status:"
echo "  kubectl get pods -n motherstream -l environment=staging"
echo "  kubectl get services -n motherstream -l environment=staging"
echo "  kubectl get ingress -n motherstream"
echo ""
echo "View logs:"
echo "  kubectl logs -f deployment/staging-motherstream -n motherstream"
echo "  kubectl logs -f deployment/staging-frontend -n motherstream"
echo "  kubectl logs -f deployment/staging-nginx-rtmp -n motherstream"
echo ""
echo "Restart services:"
echo "  kubectl rollout restart deployment/staging-motherstream -n motherstream"
echo "  kubectl rollout restart deployment/staging-frontend -n motherstream"
echo ""
echo "Clean up:"
echo "  kubectl delete -k overlays/staging"
echo ""

# Clean up temporary manifest
rm -f /tmp/staging-manifest.yaml

print_success "Build and deployment complete! 🎉"
echo ""

