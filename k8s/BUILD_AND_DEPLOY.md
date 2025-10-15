# Build and Deploy Guide

This guide explains how to build Docker images and deploy the Motherstream application to Kubernetes.

## Quick Start - Staging

The easiest way to build and deploy to staging is to use the all-in-one script:

```bash
cd k8s
./build-and-deploy-staging.sh
```

This script will:
1. ✅ Check that minikube is running
2. 🔧 Configure Docker to use minikube's environment
3. 🔨 Build all Docker images directly in minikube (motherstream, frontend, nginx-rtmp)
4. 🏷️  Tag images for staging
5. 🚀 Deploy to Kubernetes using Kustomize
6. ⏳ Wait for all services to be ready
7. 📊 Display access URLs and useful commands

> **Note**: Images are built directly in minikube's Docker daemon, so no registry push is needed!

## Prerequisites

### 1. Minikube
Make sure minikube is running:

```bash
minikube start
```

> **Note**: The build script uses minikube's Docker daemon directly, so no external registry is needed for local development!

### 2. kubectl
Verify kubectl is configured to talk to your cluster:

```bash
kubectl cluster-info
kubectl get nodes
```

## Manual Build and Deploy

If you prefer to do each step manually:

### Step 1: Build Images

Build images in minikube's Docker environment:

```bash
# Use minikube's Docker daemon (required for staging)
eval $(minikube docker-env)

# Build backend
docker build -t motherstream:staging .

# Build frontend with staging environment
docker build --build-arg VITE_API_URL=https://staging.motherstream.live/backend \
  -t frontend:staging ./frontend/

# Build NGINX RTMP
docker build -t nginx-rtmp:staging ./nginx-config/
```

> **Why minikube's Docker daemon?** Building directly in minikube's environment is faster and simpler for local development. Images are immediately available to Kubernetes without needing to push to a registry.

### Step 2: Deploy with Kustomize

```bash
# Apply staging configuration
kubectl apply -k overlays/staging

# Or use the deploy script (deployment only, no build)
./deploy-staging.sh
```

### Step 3: Verify Deployment

```bash
# Check pod status
kubectl get pods -n motherstream -l environment=staging

# Check services
kubectl get services -n motherstream -l environment=staging

# Check ingress
kubectl get ingress -n motherstream

# View logs
kubectl logs -f deployment/staging-motherstream -n motherstream
kubectl logs -f deployment/staging-frontend -n motherstream
```

## Environment Configuration

### Staging Environment Variables

The frontend environment variables are configured in Kubernetes secrets:

- **File**: `k8s/overlays/staging/secrets.yaml`
- **Secret**: `frontend-secrets`
- **Key**: `VITE_API_URL`
- **Value**: `https://staging.motherstream.live/backend` (base64 encoded)

To update the API URL:

```bash
# Generate new base64 value
echo -n "https://staging.motherstream.live/backend" | base64

# Update in k8s/overlays/staging/secrets.yaml
```

### Local Development

For local development, create a `.env` file in the frontend directory:

```bash
# frontend/.env
VITE_API_URL=http://localhost:8483
```

## Access URLs

After successful deployment, you can access:

### Local Development (NodePort Services)
- Frontend: http://localhost:30173
- Backend API: http://localhost:30483
- Jaeger UI: http://localhost:30686
- Oryx: http://localhost:30800
- NGINX RTMP: http://localhost:30080

### External Access (Ingress - requires DNS/hosts setup)
- Frontend: https://staging.motherstream.live
- Backend API: https://staging.motherstream.live/backend
- Legacy API: https://staging.always12.live

## Troubleshooting

### Images Not Found

If pods are showing `ImagePullBackOff`:

```bash
# Make sure you're using minikube's docker daemon
eval $(minikube docker-env)

# Rebuild images
./build-and-deploy-staging.sh

# Or manually rebuild a specific image
docker build -t frontend:staging ./frontend/
kubectl rollout restart deployment/staging-frontend -n motherstream
```

### Services Not Ready

Check pod logs for errors:

```bash
# Check all pods
kubectl get pods -n motherstream

# View logs for specific service
kubectl logs -f deployment/staging-motherstream -n motherstream
kubectl logs -f deployment/staging-frontend -n motherstream

# Describe pod for detailed events
kubectl describe pod <pod-name> -n motherstream
```

### Port Conflicts

If NodePort services aren't accessible, check for port conflicts:

```bash
# List services with NodePorts
kubectl get services -n motherstream -l environment=staging

# Check if ports are in use
netstat -tuln | grep -E "30173|30483|30686|30800|30080"

# If needed, edit service-patches.yaml to use different ports
```

### Database Issues

If the database isn't initializing:

```bash
# Check postgres pod
kubectl logs -f deployment/staging-postgres -n motherstream

# Check persistent volume
kubectl get pv,pvc -n motherstream

# If needed, delete and recreate
kubectl delete pvc staging-postgres-pv-claim -n motherstream
kubectl apply -k overlays/staging
```

## Cleanup

To remove the staging deployment:

```bash
# Delete all staging resources
kubectl delete -k overlays/staging

# Or use the cleanup script
./cleanup.sh staging

# To also remove persistent data
rm -rf ../staging/
```

## Production Deployment

⚠️ **Warning**: Production deployment requires additional configuration!

Before deploying to production:

1. Update secrets in `overlays/production/secrets.yaml`
2. Configure proper TLS certificates
3. Set appropriate resource limits
4. Review security settings

See [README.md](README.md) for full production deployment guide.

## Scripts Reference

- `build-and-deploy-staging.sh` - Complete build and deploy for staging
- `deploy-staging.sh` - Deploy only (no build) for staging
- `deploy-production.sh` - Deploy production environment
- `cleanup.sh` - Clean up environments

## Additional Resources

- [Kustomize Documentation](https://kustomize.io/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Minikube Documentation](https://minikube.sigs.k8s.io/docs/)

