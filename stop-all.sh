#!/bin/bash
# Stop all services (production, staging, and router)

echo "🛑 Stopping all services..."
echo ""

echo "Stopping Router..."
./docker-router.sh down

echo "Stopping Production..."
./docker-prod.sh down

echo "Stopping Staging..."
./docker-staging.sh down

echo ""
echo "✅ All services stopped!"

