#!/bin/bash

# Cleanup script for Motherstream Kubernetes deployments
# Can clean up staging, production, or both environments

set -e

echo "🧹 Motherstream Kubernetes Cleanup Script"
echo ""
echo "Available options:"
echo "  1) Clean up STAGING environment"
echo "  2) Clean up PRODUCTION environment" 
echo "  3) Clean up BOTH environments"
echo "  4) Clean up entire namespace (everything)"
echo ""

read -p "Select option (1-4): " -r option

case $option in
    1)
        echo "🗑️ Cleaning up STAGING environment..."
        kubectl delete all -l environment=staging -n motherstream --ignore-not-found=true
        kubectl delete pvc -l environment=staging -n motherstream --ignore-not-found=true
        kubectl delete secrets -l environment=staging -n motherstream --ignore-not-found=true
        kubectl delete configmaps -l environment=staging -n motherstream --ignore-not-found=true
        echo "✅ Staging environment cleaned up!"
        ;;
    2)
        echo "🗑️ Cleaning up PRODUCTION environment..."
        echo "⚠️  WARNING: This will delete PRODUCTION resources!"
        read -p "Are you sure? (yes/no): " -r
        if [[ $REPLY =~ ^yes$ ]]; then
            kubectl delete all -l environment=production -n motherstream --ignore-not-found=true
            kubectl delete pvc -l environment=production -n motherstream --ignore-not-found=true
            kubectl delete secrets -l environment=production -n motherstream --ignore-not-found=true
            kubectl delete configmaps -l environment=production -n motherstream --ignore-not-found=true
            echo "✅ Production environment cleaned up!"
        else
            echo "❌ Production cleanup cancelled."
        fi
        ;;
    3)
        echo "🗑️ Cleaning up BOTH environments..."
        echo "⚠️  WARNING: This will delete ALL deployment resources!"
        read -p "Are you sure? (yes/no): " -r
        if [[ $REPLY =~ ^yes$ ]]; then
            kubectl delete all -l project=motherstream -n motherstream --ignore-not-found=true
            kubectl delete pvc -n motherstream --ignore-not-found=true
            kubectl delete secrets -n motherstream --ignore-not-found=true
            kubectl delete configmaps -n motherstream --ignore-not-found=true
            echo "✅ Both environments cleaned up!"
        else
            echo "❌ Cleanup cancelled."
        fi
        ;;
    4)
        echo "🗑️ Cleaning up ENTIRE namespace..."
        echo "⚠️  WARNING: This will delete the ENTIRE motherstream namespace!"
        read -p "Are you absolutely sure? (yes/no): " -r
        if [[ $REPLY =~ ^yes$ ]]; then
            kubectl delete namespace motherstream --ignore-not-found=true
            echo "✅ Entire namespace cleaned up!"
        else
            echo "❌ Cleanup cancelled."
        fi
        ;;
    *)
        echo "❌ Invalid option selected."
        exit 1
        ;;
esac

echo ""
echo "📝 Note: Persistent volume data may still exist on the host system."
echo "   Check these directories if you need to clean up data:"
echo "   - Staging: ./staging/"
echo "   - Production: ./production/" 