# SSL Setup Guide for staging.motherstream.live

## 🎯 Problem Summary

You had **two SSL certificate systems competing**:
1. **certbot** (Docker Compose) - configured in host nginx
2. **cert-manager** (Kubernetes) - configured in ingress

Your host nginx was intercepting ACME challenges and trying to serve them from the local filesystem, preventing cert-manager from responding to Let's Encrypt.

## ✅ Solution: SSL Termination at Kubernetes Ingress

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                         Internet                            │
└────────────────────┬──────────────┬──────────────────────────┘
                     │              │
                 HTTP:80        HTTPS:443
                     │              │
                     ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│              Host nginx (192.168.1.231)                      │
│  • Port 80:  HTTP proxy  → Minikube:31741                   │
│  • Port 443: TCP stream  → Minikube:32763 (passthrough)     │
└────────────────────┬──────────────┬──────────────────────────┘
                     │              │
                     ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│         Minikube Ingress Controller (192.168.49.2)           │
│  • Port 31741: HTTP ingress                                  │
│  • Port 32763: HTTPS ingress (SSL TERMINATION HERE)         │
└────────────────────┬──────────────┬──────────────────────────┘
                     │              │
                     ▼              ▼
┌──────────────────────────────────────────────────────────────┐
│                    Kubernetes Pods                           │
│  • staging-frontend                                          │
│  • staging-motherstream                                      │
│  • staging-nginx-rtmp                                        │
└──────────────────────────────────────────────────────────────┘
```

### Key Points

1. **Host nginx does NOT terminate SSL** - it just forwards traffic
2. **Kubernetes ingress terminates SSL** - using cert-manager certificates
3. **cert-manager gets certificates** - via HTTP-01 ACME challenge
4. **ACME challenges flow through** - Host nginx → Minikube → cert-manager

## 📋 Setup Steps

### Step 1: Update Host nginx Configuration

I've already updated `staging-nginx.conf` to:
- Remove the HTTPS server block (was trying to terminate SSL)
- Only proxy HTTP traffic to minikube
- Forward ACME challenges to cert-manager

**Apply the changes:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 2: Add HTTPS Passthrough (Stream Module)

I've created `staging-nginx-stream.conf` for TCP-level HTTPS forwarding.

**Include it in your main nginx config:**

Edit `/etc/nginx/nginx.conf` and add this line at the **TOP LEVEL** (outside the `http` block):

```nginx
# At the top of nginx.conf, BEFORE the http block
include /home/motherstream/Desktop/motherstream/staging-nginx-stream.conf;

http {
    # existing http configuration...
}
```

**Test and reload:**
```bash
sudo nginx -t
sudo systemctl reload nginx
```

### Step 3: Apply Certificate Resources in Kubernetes

I've added Certificate resources for staging domains to `k8s/base/certificates.yaml`.

**Apply them:**
```bash
kubectl apply -f /home/motherstream/Desktop/motherstream/k8s/base/certificates.yaml
```

**Check certificate status:**
```bash
# Watch certificate creation
kubectl get certificate -n motherstream -w

# Check challenges
kubectl get challenges -n motherstream

# Check certificate details
kubectl describe certificate staging-motherstream-live-cert -n motherstream
```

### Step 4: Verify ACME Challenge Flow

Once you've applied the changes, cert-manager will automatically:
1. Create an HTTP-01 challenge
2. Start a temporary pod to respond to `/.well-known/acme-challenge/`
3. Let's Encrypt will hit your domain on port 80
4. Request flows: Internet → Host nginx → Minikube → cert-manager pod
5. Certificate gets issued and stored in Kubernetes secret

**Monitor the process:**
```bash
# Watch challenges (should go from 'pending' to 'valid')
kubectl get challenges -n motherstream -w

# Check cert-manager logs
kubectl logs -n cert-manager deployment/cert-manager -f

# Once complete, verify certificate
kubectl get certificate staging-motherstream-live-cert -n motherstream
# Should show READY=True
```

## 🔍 Troubleshooting

### If ACME Challenge Fails

**Check if traffic reaches minikube:**
```bash
# On host, test HTTP flow
curl -v http://staging.motherstream.live/.well-known/acme-challenge/test

# Check ingress logs
kubectl logs -n ingress-nginx deployment/ingress-nginx-controller
```

**Check cert-manager:**
```bash
# Describe the challenge to see errors
kubectl describe challenge <challenge-name> -n motherstream

# Check if challenge pod is running
kubectl get pods -n motherstream | grep cm-acme
```

### If HTTPS Doesn't Work

**Verify stream configuration:**
```bash
# Check if nginx stream is listening on 443
sudo netstat -tlnp | grep :443

# Check stream logs
sudo tail -f /var/log/nginx/staging_stream_error.log
```

**Test connectivity to minikube:**
```bash
# From host, test if minikube HTTPS port is reachable
curl -k https://192.168.49.2:32763 -H "Host: staging.motherstream.live"
```

## 📊 What Each File Does

| File | Purpose | Where It Runs |
|------|---------|---------------|
| `staging-nginx.conf` | HTTP proxy configuration | Host nginx |
| `staging-nginx-stream.conf` | HTTPS TCP passthrough | Host nginx |
| `k8s/base/certificates.yaml` | Certificate definitions for cert-manager | Kubernetes |
| `k8s/overlays/staging/staging-ingress.yaml` | Ingress routing rules | Kubernetes |

## ✅ Success Indicators

1. **Certificate issued:**
   ```bash
   kubectl get certificate staging-motherstream-live-cert -n motherstream
   # READY column shows True
   ```

2. **Secret created:**
   ```bash
   kubectl get secret staging-motherstream-live-tls -n motherstream
   # Should exist
   ```

3. **HTTPS works:**
   ```bash
   curl -v https://staging.motherstream.live
   # Should return 200 OK with valid SSL certificate
   ```

## 🚀 Quick Command Summary

```bash
# 1. Reload host nginx
sudo nginx -t && sudo systemctl reload nginx

# 2. Apply certificates
kubectl apply -f k8s/base/certificates.yaml

# 3. Watch progress
kubectl get certificate -n motherstream -w

# 4. Test HTTP (should work immediately)
curl http://staging.motherstream.live

# 5. Test HTTPS (works after certificate is issued)
curl https://staging.motherstream.live
```

## ❓ FAQ

### Do I need certificates on the host?
**No.** The host nginx only forwards traffic. SSL termination happens in Kubernetes.

### Can I use certbot instead of cert-manager?
**Not recommended.** Since you're using Kubernetes ingress for SSL termination, cert-manager is the natural choice. Certbot would require syncing certificates from host to Kubernetes.

### What about the docker-compose-certbot.yml file?
**It's for a different purpose.** That's likely for manual certificate management or other domains. For staging.motherstream.live, use cert-manager.

### Why TCP stream for HTTPS?
**Because the traffic is encrypted.** nginx can't read the HTTP headers (like `Host:`) until after SSL termination. So we forward the encrypted stream to Kubernetes, where the ingress controller terminates SSL.

## 📚 References

- [cert-manager HTTP-01 Challenge](https://cert-manager.io/docs/configuration/acme/http01/)
- [nginx Stream Module](https://nginx.org/en/docs/stream/ngx_stream_core_module.html)
- [Kubernetes Ingress TLS](https://kubernetes.io/docs/concepts/services-networking/ingress/#tls)

