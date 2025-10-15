#!/bin/bash
# Obtain Let's Encrypt certificates using docker-compose-certbot.yml
# This updates the docker-compose file with the specified domain and runs certbot

set -e

DOMAIN=$1
EMAIL="itsalways12@gmail.com"
COMPOSE_FILE="/home/motherstream/Desktop/motherstream/docker-compose-certbot.yml"

if [ -z "$DOMAIN" ]; then
    echo "❌ Usage: $0 <domain> [--renew]"
    echo ""
    echo "Examples:"
    echo "  $0 staging.motherstream.live          # Obtain new certificate"
    echo "  $0 staging.motherstream.live --renew  # Force renewal"
    echo "  $0 staging.always12.live"
    echo ""
    echo "Available domains:"
    echo "  - staging.motherstream.live"
    echo "  - staging.always12.live"
    echo "  - always12.live"
    echo "  - motherstream.live"
    exit 1
fi

FORCE_RENEWAL=""
if [ "$2" == "--renew" ]; then
    FORCE_RENEWAL="--force-renewal"
    echo "🔄 Force renewal enabled"
fi

echo "🔐 Obtaining Let's Encrypt certificate for: $DOMAIN"
echo ""

# Ensure webroot directory exists
mkdir -p ./certbot/www/.well-known/acme-challenge
mkdir -p ./certs
mkdir -p ./logs

# Create a temporary ingress to serve the ACME challenge via nginx ingress
echo "📝 Creating temporary ACME challenge ingress in Kubernetes..."
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ConfigMap
metadata:
  name: certbot-webroot
  namespace: motherstream
data: {}
---
apiVersion: v1
kind: Pod
metadata:
  name: certbot-webroot
  namespace: motherstream
  labels:
    app: certbot-webroot
spec:
  containers:
  - name: nginx
    image: nginx:alpine
    ports:
    - containerPort: 80
    volumeMounts:
    - name: webroot
      mountPath: /usr/share/nginx/html
  volumes:
  - name: webroot
    hostPath:
      path: /home/motherstream/Desktop/motherstream/certbot/www
      type: DirectoryOrCreate
---
apiVersion: v1
kind: Service
metadata:
  name: certbot-webroot
  namespace: motherstream
spec:
  selector:
    app: certbot-webroot
  ports:
  - port: 80
    targetPort: 80
---
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: certbot-acme-challenge
  namespace: motherstream
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "false"
spec:
  ingressClassName: nginx
  rules:
  - host: $DOMAIN
    http:
      paths:
      - path: /.well-known/acme-challenge
        pathType: Prefix
        backend:
          service:
            name: certbot-webroot
            port:
              number: 80
EOF

echo "⏳ Waiting for ACME challenge service to be ready..."
sleep 8

# Update docker-compose-certbot.yml with the specified domain
echo "📝 Updating docker-compose-certbot.yml..."
cat > "$COMPOSE_FILE" <<EOF
services: 
  certbot:
    container_name: certbot
    image: certbot/certbot:latest
    network_mode: host
    dns:
      - 8.8.8.8
      - 1.1.1.1
    volumes:
      - ./certbot/www/:/var/www/certbot/:rw
      - ./certs/:/etc/letsencrypt/:rw
      - ./logs/:/var/log/letsencrypt/:rw
    command: certonly -v --webroot --webroot-path /var/www/certbot -d $DOMAIN --email $EMAIL --agree-tos $FORCE_RENEWAL
EOF

echo "🚀 Running certbot via docker-compose..."
echo ""
docker compose -f "$COMPOSE_FILE" up

echo ""
echo "✅ Certificate obtained successfully!"
echo ""

# Cleanup temporary resources
echo "🧹 Cleaning up temporary Kubernetes resources..."
kubectl delete ingress certbot-acme-challenge -n motherstream --ignore-not-found
kubectl delete service certbot-webroot -n motherstream --ignore-not-found
kubectl delete pod certbot-webroot -n motherstream --ignore-not-found
kubectl delete configmap certbot-webroot -n motherstream --ignore-not-found

echo ""
echo "📋 Next steps:"
echo "1. Sync the certificate to Kubernetes:"
echo "   ./scripts/sync-certs-to-k8s.sh"
echo ""
echo "2. Verify HTTPS is working:"
echo "   curl -v https://$DOMAIN"

