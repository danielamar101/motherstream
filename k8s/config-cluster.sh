#!/bin/bash

# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.19.0/cert-manager.yaml

# Enable ingress-nginx
minikube addons enable ingress

sudo systemctl start nginx
sudo systemctl enable nginx

 helm upgrade --install tailscale-operator tailscale/tailscale-operator   --namespace=tailscale   --create-namespace   --set-string oauth.clientId="$CLIENT_ID"   --set-string oauth.clientSecret="$CLIENT_SECRET"   --wait

# sudo systemctl start cert-manager
# sudo systemctl enable cert-manager

# Copy home nginx to proper lcoations