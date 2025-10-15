#!/bin/bash
# Sync Let's Encrypt certificates from certbot to Kubernetes secrets
# This script creates/updates TLS secrets in Kubernetes from local certbot certificates

set -e

CERT_BASE_DIR="/home/motherstream/Desktop/motherstream/certs/live"
NAMESPACE="motherstream"

echo "🔐 Syncing Let's Encrypt certificates to Kubernetes..."
echo ""

# Function to create or update a TLS secret from certbot certificates
sync_cert() {
    local domain=$1
    local secret_name=$2
    
    local cert_dir="${CERT_BASE_DIR}/${domain}"
    
    if [ ! -d "$cert_dir" ]; then
        echo "⚠️  Certificate directory not found: $cert_dir"
        echo "   Skipping $domain"
        return 1
    fi
    
    if [ ! -f "$cert_dir/fullchain.pem" ] || [ ! -f "$cert_dir/privkey.pem" ]; then
        echo "⚠️  Certificate files not found in: $cert_dir"
        echo "   Skipping $domain"
        return 1
    fi
    
    echo "📄 Syncing certificate for: $domain"
    echo "   Secret name: $secret_name"
    
    # Check certificate expiration
    local expiry=$(sudo openssl x509 -in "$cert_dir/cert.pem" -noout -enddate | cut -d= -f2)
    echo "   Expires: $expiry"
    
    # Create or update the secret (using sudo to read cert files)
    sudo kubectl create secret tls "$secret_name" \
        --cert="$cert_dir/fullchain.pem" \
        --key="$cert_dir/privkey.pem" \
        -n "$NAMESPACE" \
        --dry-run=client -o yaml | kubectl apply -f -
    
    if [ $? -eq 0 ]; then
        echo "   ✅ Secret $secret_name created/updated successfully"
    else
        echo "   ❌ Failed to create/update secret $secret_name"
        return 1
    fi
    
    echo ""
}

# Sync staging.motherstream.live certificate
sync_cert "staging.motherstream.live" "staging-motherstream-live-tls"

# Sync motherstream.live certificate (if it exists - for production)
sync_cert "motherstream.live" "motherstream-live-tls"

# Sync always12.live certificate (if it exists - for production)
sync_cert "always12.live" "always12-live-tls"

echo "✅ Certificate sync complete!"
echo ""
echo "To verify the secrets:"
echo "  kubectl get secrets -n $NAMESPACE | grep tls"
echo ""
echo "To check certificate details in a secret:"
echo "  kubectl get secret staging-motherstream-live-tls -n $NAMESPACE -o jsonpath='{.data.tls\.crt}' | base64 -d | openssl x509 -noout -text"

