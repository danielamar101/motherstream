#!/bin/bash

echo "🔗 Setting up Tailscale in minikube cluster..."

# Check if auth key is provided
if [ -z "$1" ]; then
    echo "❌ Usage: $0 <tailscale-auth-key>"
    echo "Get your auth key from: https://login.tailscale.com/admin/settings/keys"
    echo "Make sure to enable 'Reusable' and 'Ephemeral' options"
    exit 1
fi

AUTH_KEY="$1"

echo "📝 Updating Tailscale auth key..."
sed -i "s/REPLACE_WITH_YOUR_TAILSCALE_AUTH_KEY/$AUTH_KEY/" k8s/base/tailscale-config.yaml

echo "🚀 Deploying Tailscale to cluster..."
kubectl apply -f k8s/base/tailscale-config.yaml

echo "⏳ Waiting for Tailscale pod to be ready..."
kubectl wait --for=condition=ready pod -l app=tailscale-gateway -n motherstream --timeout=120s

echo "✅ Checking Tailscale status..."
kubectl logs -l app=tailscale-gateway -n motherstream --tail=20

echo ""
echo "🎉 Tailscale setup complete!"
echo ""
echo "Your minikube cluster should now appear as 'minikube-motherstream' in your Tailscale admin console"
echo "The cluster can now access your Tailscale network devices:"
tailscale status | grep -E "(100\.|offline|active)"

echo ""
echo "🔧 To test connectivity from a pod:"
echo "kubectl run test-pod --image=alpine --rm -it -- sh"
echo "# Then in the pod: ping 100.108.225.64  # your macbook-pro"
