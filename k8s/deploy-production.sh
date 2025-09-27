#!/bin/bash

# Deploy script for Motherstream Production Environment
# Uses Kustomize to deploy the production overlay

set -e

echo "🚀 Deploying Motherstream PRODUCTION environment..."
echo "⚠️  WARNING: This will deploy to PRODUCTION! Make sure you've reviewed all configurations."

# Ensure we're in the correct directory
cd "$(dirname "$0")"

# Prompt for confirmation in production
read -p "Are you sure you want to deploy to PRODUCTION? (yes/no): " -r
if [[ ! $REPLY =~ ^yes$ ]]; then
    echo "❌ Production deployment cancelled."
    exit 1
fi

# Create production data directories if they don't exist
echo "📁 Creating production data directories..."
mkdir -p ../production/{pgdata/data,stream-recordings,oryx,certs}

# Validate production secrets
echo "🔐 Validating production secrets..."
if kubectl get secret prod-motherstream-secrets -n motherstream >/dev/null 2>&1; then
    echo "✅ Production secrets found"
else
    echo "⚠️  Production secrets not found. Please ensure secrets are properly configured!"
    echo "    Check k8s/overlays/production/secrets.yaml and update with real production values."
    read -p "Continue anyway? (yes/no): " -r
    if [[ ! $REPLY =~ ^yes$ ]]; then
        echo "❌ Production deployment cancelled."
        exit 1
    fi
fi

# Build and apply production configuration
echo "🔧 Building production configuration with Kustomize..."
kubectl kustomize overlays/production > /tmp/production-manifest.yaml

echo "📋 Applying production manifests..."
kubectl apply -f /tmp/production-manifest.yaml

# Wait for production infrastructure to be ready
echo "⏳ Waiting for production infrastructure services to be ready..."
kubectl wait --for=condition=ready pod -l app=prod-postgres -n motherstream --timeout=600s || echo "⚠️  Postgres not ready yet"
kubectl wait --for=condition=ready pod -l app=prod-jaeger -n motherstream --timeout=300s || echo "⚠️  Jaeger not ready yet"

# Wait for production application services (with replicas)
echo "⏳ Waiting for production application services to be ready..."
kubectl wait --for=condition=ready pod -l app=prod-motherstream -n motherstream --timeout=600s || echo "⚠️  Motherstream not ready yet"
kubectl wait --for=condition=ready pod -l app=prod-frontend -n motherstream --timeout=600s || echo "⚠️  Frontend not ready yet"

echo "✅ Production deployment completed!"
echo ""
echo "🌐 Production services status:"
kubectl get pods -n motherstream -l environment=production
echo ""
echo "📊 Check production deployment:"
echo "  kubectl get pods -n motherstream -l environment=production"
echo "  kubectl get services -n motherstream -l environment=production"
echo "  kubectl logs -f deployment/prod-motherstream -n motherstream"
echo ""
echo "🗑️ Clean up production manifest:"
echo "  rm /tmp/production-manifest.yaml"

# Clean up temporary file
rm -f /tmp/production-manifest.yaml 