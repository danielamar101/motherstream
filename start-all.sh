#!/bin/bash
# Start all services (production, staging, and router)

set -e

echo "🚀 Starting Motherstream Production and Staging Environments..."
echo ""

# Create networks if they don't exist
echo "📡 Creating Docker networks..."
docker network create prod-network 2>/dev/null || echo "  ℹ️  prod-network already exists"
docker network create staging-network 2>/dev/null || echo "  ℹ️  staging-network already exists"
echo ""

# Start production
echo "🟢 Starting Production environment..."
./docker-prod.sh up -d --build
echo ""

# Start staging
echo "🟡 Starting Staging environment..."
./docker-staging.sh up -d --build 
echo ""

# Start router
echo "🔀 Starting Nginx Router..."
./docker-router.sh up -d
echo ""

echo "✅ All services started successfully!"
echo ""
echo "Production:  https://motherstream.live"
echo "Staging:     https://staging.motherstream.live"
echo ""
echo "View logs with:"
echo "  Production: ./docker-prod.sh logs -f"
echo "  Staging:    ./docker-staging.sh logs -f"
echo "  Router:     ./docker-router.sh logs -f"

