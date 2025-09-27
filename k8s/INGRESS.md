# Motherstream Kubernetes Ingress Configuration

This document explains how the Kubernetes Ingress resources replicate your original nginx configuration from `nginx-config/`.

## 🌐 Architecture Overview

The ingress configuration provides the same functionality as your original nginx setup but using Kubernetes-native resources:

### Original nginx Setup
```
nginx-config/
├── nginx.conf          # Main config with RTMP stats (port 8989)
├── https-config.conf    # SSL termination and domain routing
├── rtmp.conf           # RTMP streaming (port 1936)
└── stat.xsl            # Statistics styling
```

### Kubernetes Ingress Equivalent
```
k8s/base/
├── ingress.yaml        # HTTP/HTTPS routing + SSL termination
├── rtmp-ingress.yaml   # TCP routing for RTMP streaming
└── certificates.yaml   # Automatic SSL certificate management
```

## 🔄 Mapping: nginx → Kubernetes Ingress

### Domain Configuration

| nginx Config | Kubernetes Ingress | Purpose |
|---------------|-------------------|---------|
| `motherstream.live` | `motherstream.live` | Main frontend + backend API |
| `always12.live` | `always12.live` | Backend API only |
| SSL certificates in `/etc/letsencrypt/` | cert-manager with Let's Encrypt | Automatic SSL management |

### Service Routing

#### motherstream.live Domain
```nginx
# Original nginx
location / {
    proxy_pass http://127.0.0.1:5173/;  # Frontend
}
location /backend/ {
    proxy_pass http://127.0.0.1:8483/;  # Backend API
}
```

```yaml
# Kubernetes Ingress
- host: motherstream.live
  http:
    paths:
    - path: /backend
      backend:
        service:
          name: motherstream
          port:
            number: 8483
    - path: /
      backend:
        service:
          name: frontend  
          port:
            number: 5173
```

#### always12.live Domain
```nginx
# Original nginx - Multiple specific endpoints
location /queue-json { proxy_pass http://127.0.0.1:8483/queue-json; }
location /timer-data { proxy_pass http://127.0.0.1:8483/timer-data; }
# ... etc
location / { proxy_pass http://127.0.0.1:8483/; }  # Catch-all
```

```yaml
# Kubernetes Ingress - Same endpoint mapping
- host: always12.live
  http:
    paths:
    - path: /queue-json
      pathType: Exact
      backend:
        service:
          name: motherstream
          port:
            number: 8483
    # ... other specific endpoints
    - path: /
      pathType: Prefix  # Catch-all
      backend:
        service:
          name: motherstream
          port:
            number: 8483
```

### RTMP Streaming
```nginx
# Original nginx rtmp.conf
rtmp {
    server {
        listen 1936;
        application live {
            live on;
            record all manual;
        }
    }
}
```

```yaml
# Kubernetes TCP Ingress
apiVersion: v1
kind: ConfigMap
metadata:
  name: tcp-services
  namespace: ingress-nginx
data:
  1936: "motherstream/nginx-rtmp:1936"
```

### Statistics & Monitoring
```nginx
# Original nginx
location /stat {
    rtmp_stat all;
    rtmp_stat_stylesheet stat.xsl;
}
```

```yaml
# Kubernetes Ingress
- path: /stat
  pathType: Prefix
  backend:
    service:
      name: nginx-rtmp
      port:
        number: 8989
```

## 🛡️ Security Features

### SSL/TLS Configuration
The ingress automatically handles SSL termination that was previously done in nginx:

```nginx
# Original nginx https-config.conf
ssl_protocols TLSv1 TLSv1.1 TLSv1.2 TLSv1.3;
ssl_ciphers HIGH:!aNULL:!MD5;
add_header Strict-Transport-Security "max-age=31536000" always;
```

```yaml
# Kubernetes Ingress annotations
nginx.ingress.kubernetes.io/ssl-redirect: "true"
nginx.ingress.kubernetes.io/configuration-snippet: |
  add_header Strict-Transport-Security "max-age=31536000" always;
  add_header X-Frame-Options "SAMEORIGIN" always;
```

### CORS Headers
```nginx
# Original nginx
add_header 'Access-Control-Allow-Origin' '*' always;
```

```yaml
# Kubernetes Ingress
nginx.ingress.kubernetes.io/cors-allow-origin: "*"
nginx.ingress.kubernetes.io/cors-allow-methods: "GET, POST, OPTIONS"
```

### Rate Limiting
```yaml
# Kubernetes Ingress
nginx.ingress.kubernetes.io/rate-limit: "100"
nginx.ingress.kubernetes.io/rate-limit-window: "1m"
```

## 🚀 Prerequisites

### 1. NGINX Ingress Controller
```bash
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.8.2/deploy/static/provider/cloud/deploy.yaml
```

### 2. cert-manager for SSL
```bash
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.13.2/cert-manager.yaml
```

### 3. DNS Configuration
Point your domains to the ingress controller's external IP:
```bash
# Get ingress controller external IP
kubectl get service ingress-nginx-controller -n ingress-nginx

# Update DNS records
motherstream.live    A    <EXTERNAL-IP>
always12.live        A    <EXTERNAL-IP>
*.motherstream.live  A    <EXTERNAL-IP>
*.always12.live      A    <EXTERNAL-IP>
```

## 🌍 Environment Differences

### Staging Environment
- **Domains**: `staging.motherstream.local`, `staging.always12.local`
- **SSL**: Self-signed certificates or disabled
- **Rate Limiting**: Relaxed (1000 req/min)
- **Service Names**: Prefixed with `staging-`

### Production Environment  
- **Domains**: `motherstream.live`, `always12.live`
- **SSL**: Let's Encrypt certificates
- **Rate Limiting**: Strict (50 req/min)
- **Security**: Enhanced headers and CSP
- **Service Names**: Prefixed with `prod-`

## 📊 Monitoring & Troubleshooting

### Check Ingress Status
```bash
# View ingress resources
kubectl get ingress -n motherstream

# Describe ingress for detailed info
kubectl describe ingress motherstream-ingress -n motherstream

# Check certificate status
kubectl get certificates -n motherstream
```

### View Ingress Controller Logs
```bash
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

### Test Endpoints
```bash
# Test frontend
curl -H "Host: motherstream.live" http://<INGRESS-IP>/

# Test backend API
curl -H "Host: motherstream.live" http://<INGRESS-IP>/backend/health

# Test always12 API
curl -H "Host: always12.live" http://<INGRESS-IP>/queue-json

# Test RTMP (requires rtmp client)
ffmpeg -i input.mp4 -f flv rtmp://<INGRESS-IP>:1936/live/stream
```

### Common Issues

1. **502 Bad Gateway**: Backend service not ready
   ```bash
   kubectl get pods -n motherstream
   kubectl logs deployment/motherstream -n motherstream
   ```

2. **SSL Certificate Issues**: Check cert-manager
   ```bash
   kubectl describe certificate motherstream-live-cert -n motherstream
   kubectl logs -n cert-manager deployment/cert-manager
   ```

3. **RTMP Not Working**: Check TCP ingress configuration
   ```bash
   kubectl get configmap tcp-services -n ingress-nginx -o yaml
   ```

## 🔧 Customization

### Adding New Domains
1. Update `ingress.yaml` with new host rules
2. Create certificate in `certificates.yaml`
3. Update environment-specific patches if needed

### Modifying Rate Limits
Update the annotation in environment overlays:
```yaml
nginx.ingress.kubernetes.io/rate-limit: "custom-value"
```

### Adding Custom Headers
Extend the configuration snippet:
```yaml
nginx.ingress.kubernetes.io/configuration-snippet: |
  add_header Custom-Header "value" always;
```

## 📚 Additional Resources

- [NGINX Ingress Controller Documentation](https://kubernetes.github.io/ingress-nginx/)
- [cert-manager Documentation](https://cert-manager.io/docs/)
- [Kubernetes Ingress Concepts](https://kubernetes.io/docs/concepts/services-networking/ingress/) 