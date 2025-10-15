# 🔗 Tailscale Integration for Minikube Cluster

## Quick Setup (Recommended)

1. **Get your Tailscale auth key:**
   ```bash
   # Go to: https://login.tailscale.com/admin/settings/keys
   # Create a new auth key with:
   # ✅ Reusable
   # ✅ Ephemeral  
   # ✅ Tags: k8s:minikube (optional)
   ```

2. **Deploy Tailscale to your cluster:**
   ```bash
   ./setup-tailscale.sh YOUR_AUTH_KEY_HERE
   ```

3. **Verify it's working:**
   ```bash
   # Check Tailscale pod status
   kubectl get pods -l app=tailscale-gateway -n motherstream
   
   # View logs
   kubectl logs -l app=tailscale-gateway -n motherstream
   
   # Test connectivity from a pod
   kubectl run test-pod --image=alpine --rm -it -- sh
   # In the pod: ping 100.108.225.64  # your macbook-pro IP
   ```

## What This Gives You

✅ **Access Tailscale devices** from any pod in the cluster  
✅ **Secure networking** through Tailscale's encrypted mesh  
✅ **Automatic discovery** - cluster appears as "minikube-motherstream"  
✅ **Route advertising** - exposes cluster subnets to Tailscale network  

## Alternative Options

### Option 2: Host Network Access
For simple cases, use host network in specific deployments:
```bash
kubectl apply -f k8s/overlays/staging/tailscale-host-patch.yaml
```

### Option 3: Tailscale Operator (Advanced)
For production environments:
```bash
# Install Tailscale operator
helm repo add tailscale https://pkgs.tailscale.com/helmcharts
helm upgrade --install tailscale-operator tailscale/tailscale-operator \
  --namespace=tailscale --create-namespace \
  --set-string oauth.clientId="YOUR_CLIENT_ID" \
  --set-string oauth.clientSecret="YOUR_CLIENT_SECRET"

# Apply connector
kubectl apply -f k8s/base/tailscale-operator.yaml
```

## Current Tailscale Network

Your current devices (from `tailscale status`):
- 🖥️ **motherstream-r730**: 100.70.138.25 (your local machine)  
- 💻 **macbook-pro**: 100.108.225.64 (active)
- ☁️ **aws-ec2-1**: 100.96.130.107 (offline)
- ☁️ **ec2-motherstream**: 100.80.228.42 (offline)

## Troubleshooting

### DNS Issues
If you see DNS warnings:
```bash
# Check Tailscale DNS settings
kubectl exec -it deployment/tailscale-gateway -n motherstream -- tailscale status

# Or use custom DNS in pod specs:
dnsPolicy: "None"
dnsConfig:
  nameservers:
  - "100.100.100.100"  # Tailscale Magic DNS
  - "8.8.8.8"
```

### Connectivity Issues
```bash
# Check routes
kubectl exec -it deployment/tailscale-gateway -n motherstream -- ip route

# Test from Tailscale pod
kubectl exec -it deployment/tailscale-gateway -n motherstream -- ping 100.108.225.64
```

### Pod-to-Tailscale Connectivity
If pods can't reach Tailscale network:
1. Ensure the Tailscale gateway is advertising routes
2. Add network policies if needed
3. Check firewall rules on Tailscale devices
