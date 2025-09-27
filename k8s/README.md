# Motherstream Kubernetes Manifests (Kustomize)

This directory contains Kubernetes manifests organized using **Kustomize** for clean separation of environments. The manifests are converted from the original Docker Compose configuration and provide the same functionality but are designed to run on Kubernetes with proper environment separation.

## 🏗️ Architecture Overview

The deployment consists of the following services:

- **Motherstream**: Main application service
- **Frontend**: React frontend application  
- **PostgreSQL**: Database service
- **Jaeger**: Distributed tracing
- **NGINX RTMP**: RTMP streaming server
- **Oryx**: SRS streaming server

## 📁 Directory Structure

```
k8s/
├── base/                          # Common base manifests
│   ├── configmap.yaml            # Base configuration
│   ├── frontend.yaml             # Frontend deployment & service
│   ├── jaeger.yaml              # Jaeger tracing
│   ├── kustomization.yaml       # Base kustomization
│   ├── motherstream.yaml        # Main app deployment & service
│   ├── namespace.yaml           # Namespace definition
│   ├── nginx-rtmp.yaml          # NGINX RTMP server
│   ├── oryx.yaml               # Oryx streaming server
│   └── postgres.yaml           # PostgreSQL database
├── overlays/
│   ├── staging/                 # Staging environment
│   │   ├── secrets.yaml         # Staging secrets
│   │   ├── persistent-volumes.yaml  # Staging storage
│   │   ├── service-patches.yaml # NodePort services for staging
│   │   └── kustomization.yaml   # Staging overlay config
│   └── production/              # Production environment
│       ├── secrets.yaml         # Production secrets (update for real prod!)
│       ├── persistent-volumes.yaml  # Production storage
│       ├── resource-patches.yaml    # Production resource limits
│       └── kustomization.yaml   # Production overlay config
├── deploy-staging.sh            # Deploy staging environment
├── deploy-production.sh         # Deploy production environment  
├── cleanup.sh                   # Environment cleanup script
└── README.md                    # This file
```

## 🚀 Quick Start

### Prerequisites

1. **Kubernetes Cluster**: Running cluster (minikube, kind, or full cluster)
2. **kubectl**: Kubernetes CLI configured
3. **Kustomize**: Built into kubectl (v1.14+) or standalone
4. **Docker Images**: Build the custom images first:

```bash
# Build application images
docker build -t motherstream:staging .
docker build -t frontend:staging ./frontend/
docker build -t nginx-rtmp:staging ./nginx-config/

# For production, use proper versioned tags
docker build -t motherstream:v1.0.0 .
docker build -t frontend:v1.0.0 ./frontend/
docker build -t nginx-rtmp:v1.0.0 ./nginx-config/
```

### Deploy Staging Environment

```bash
# Quick deploy
chmod +x deploy-staging.sh
./deploy-staging.sh

# Or manually with kustomize
kubectl apply -k overlays/staging
```

### Deploy Production Environment

```bash
# ⚠️ Update secrets first! See Configuration section below
chmod +x deploy-production.sh
./deploy-production.sh

# Or manually with kustomize
kubectl apply -k overlays/production
```

## ⚙️ Configuration

### Environment Secrets

**🔴 IMPORTANT**: Before deploying to production, update the secrets in `overlays/production/secrets.yaml`:

```bash
# Generate base64 encoded values
echo -n "your-production-password" | base64

# Update these in overlays/production/secrets.yaml:
# - DB_PASSWORD
# - JWT_SECRET  
# - OBS_PASSWORD
# - SENTRY_DSN
# - DISCORD_WEBHOOK_URL
# - SRS_AUTHORIZATION_BEARER
```

### Storage Configuration

Each environment uses separate storage paths:

- **Staging**: `./staging/{pgdata,stream-recordings,oryx,certs}`
- **Production**: `./production/{pgdata,stream-recordings,oryx,certs}`

Storage sizes:
- **Staging**: Smaller allocations for testing
- **Production**: Large allocations for real workloads

### Resource Configuration

- **Staging**: Minimal resources for development
- **Production**: Higher resources and multiple replicas

## 🌐 Accessing Services

### Staging Environment
Services are exposed via NodePort for easy development access:

- **Frontend**: http://localhost:30173
- **Motherstream API**: http://localhost:30483  
- **Jaeger UI**: http://localhost:30686
- **Oryx Dashboard**: http://localhost:30800
- **NGINX**: http://localhost:30080, https://localhost:30443
- **RTMP Stream**: rtmp://localhost:31936

### Production Environment
Uses ClusterIP services by default. For production access, consider:
- Ingress controllers
- Load balancers
- Port forwarding for debugging

## 📊 Monitoring & Management

### Check Deployment Status

```bash
# Staging environment
kubectl get pods -n motherstream -l environment=staging
kubectl get services -n motherstream -l environment=staging

# Production environment  
kubectl get pods -n motherstream -l environment=production
kubectl get services -n motherstream -l environment=production

# All environments
kubectl get all -n motherstream
```

### View Logs

```bash
# Staging
kubectl logs -f deployment/staging-motherstream -n motherstream
kubectl logs -f deployment/staging-frontend -n motherstream

# Production
kubectl logs -f deployment/prod-motherstream -n motherstream
kubectl logs -f deployment/prod-frontend -n motherstream
```

### Debug Services

```bash
# Port forward for debugging
kubectl port-forward service/staging-motherstream 8483:8483 -n motherstream
kubectl port-forward service/prod-motherstream 8484:8483 -n motherstream

# Execute into pods
kubectl exec -it deployment/staging-motherstream -n motherstream -- /bin/bash
```

## 🔧 Customization

### Adding New Environments

1. Create new overlay directory: `overlays/new-env/`
2. Copy and modify files from `staging/` or `production/`
3. Update `kustomization.yaml` with environment-specific settings
4. Create deployment script: `deploy-new-env.sh`

### Modifying Base Resources

Common changes go in `base/` directory and affect all environments:
- Service definitions
- Base container configurations  
- Common labels and annotations

### Environment-Specific Changes

Use overlays for environment-specific modifications:
- **Patches**: Modify existing resources
- **Resources**: Add environment-specific resources
- **ConfigMaps/Secrets**: Environment-specific configuration

## 🧹 Cleanup

```bash
# Interactive cleanup script
chmod +x cleanup.sh
./cleanup.sh

# Or specific environments
kubectl delete -k overlays/staging
kubectl delete -k overlays/production

# Nuclear option (delete everything)
kubectl delete namespace motherstream
```

## 🔄 Key Differences from Docker Compose

### Kustomize Benefits

- **Environment Separation**: Clean staging/production separation
- **DRY Principle**: Common base with environment-specific overlays
- **Versioning**: Different image tags per environment
- **Resource Management**: Environment-appropriate resource allocation
- **Configuration Management**: Separate secrets and configs per environment

### Network Changes

- **Docker Compose**: `network_mode: host`
- **Kubernetes**: Proper service discovery with ClusterIP/NodePort
- **Staging**: NodePort for development access
- **Production**: ClusterIP + potential Ingress

### Storage Changes

- **Docker Compose**: Direct bind mounts
- **Kubernetes**: PersistentVolumes with environment-specific paths
- **Staging**: Smaller storage allocations
- **Production**: Large storage allocations

### Dependency Management

- **Docker Compose**: `depends_on`  
- **Kubernetes**: initContainers with service discovery

## 🛡️ Security Considerations

### Secrets Management

- Store secrets in Kubernetes Secrets (not in Git!)
- Use external secret managers in production (Vault, AWS Secrets Manager)
- Rotate secrets regularly
- Never commit real production secrets to version control

### Resource Limits

- Set appropriate CPU/memory limits
- Use resource quotas per namespace
- Monitor resource usage

### Network Security

- Use NetworkPolicies to restrict pod-to-pod communication
- Consider service mesh for advanced traffic management
- Use proper Ingress with TLS termination

## 🚀 Production Readiness

Before deploying to production:

1. **✅ Update all secrets** in `overlays/production/secrets.yaml`
2. **✅ Review resource limits** in `overlays/production/resource-patches.yaml`
3. **✅ Set up proper storage classes** (replace hostPath)
4. **✅ Configure monitoring** (Prometheus, Grafana)
5. **✅ Set up backup strategies** for PostgreSQL
6. **✅ Configure Ingress** for external access
7. **✅ Implement CI/CD pipelines** for automated deployments
8. **✅ Set up log aggregation** (ELK stack, Fluentd)

## 📚 Further Reading

- [Kustomize Documentation](https://kustomize.io/)
- [Kubernetes Best Practices](https://kubernetes.io/docs/concepts/configuration/overview/)
- [Managing Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Resource Management](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/) 