#!/bin/bash

# Deploy script for Motherstream Staging Environment
# Uses Kustomize to deploy the staging overlay

set -e

echo "🚀 Deploying Motherstream STAGING environment..."

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Create staging data directories if they don't exist
echo "📁 Creating staging data directories..."
mkdir -p ../staging/{pgdata/data,stream-recordings,oryx,certs}

# Build and apply staging configuration
echo "🔧 Building staging configuration with Kustomize..."
kubectl kustomize overlays/staging > /tmp/staging-manifest.yaml

echo "📋 Applying staging manifests..."
kubectl apply -f /tmp/staging-manifest.yaml

# Wait for staging infrastructure to be ready
echo "⏳ Waiting for staging infrastructure services to be ready..."
kubectl wait --for=condition=ready pod -l app=postgres,environment=staging -n motherstream --timeout=300s || echo "⚠️  Postgres not ready yet"
kubectl wait --for=condition=ready pod -l app=jaeger,environment=staging -n motherstream --timeout=300s || echo "⚠️  Jaeger not ready yet"

# Wait for staging application services
echo "⏳ Waiting for staging application services to be ready..."
kubectl wait --for=condition=ready pod -l app=motherstream,environment=staging -n motherstream --timeout=300s || echo "⚠️  Motherstream not ready yet"
kubectl wait --for=condition=ready pod -l app=frontend,environment=staging -n motherstream --timeout=300s || echo "⚠️  Frontend not ready yet"

echo "✅ Staging deployment completed!"
echo ""
echo "🌐 Staging services are accessible at:"
echo "  - Frontend: http://localhost:30173"
echo "  - Motherstream API: http://localhost:30483"
echo "  - Jaeger UI: http://localhost:30686"
echo "  - Oryx: http://localhost:30800"
echo "  - NGINX RTMP: http://localhost:30080"
echo ""
echo "📊 Check staging deployment status:"
echo "  kubectl get pods -n motherstream -l environment=staging"
echo "  kubectl get services -n motherstream -l environment=staging"
echo ""
echo "🗑️ Clean up staging manifest:"
echo "  rm /tmp/staging-manifest.yaml"

# Clean up temporary file
rm -f /tmp/staging-manifest.yaml 