#!/bin/bash

# Setup script for staging nginx reverse proxy
# This installs nginx on the host system and configures it to route staging.motherstream.live

set -e

echo "🚀 Setting up staging nginx reverse proxy..."

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   echo "❌ This script should not be run as root. Run with sudo when prompted."
   exit 1
fi

# Stop nginx to configure it
echo "⏹️  Stopping nginx for configuration..."
sudo systemctl stop nginx

# Backup default configuration
echo "💾 Backing up default nginx configuration..."
sudo cp /etc/nginx/sites-available/default /etc/nginx/sites-available/default.backup

# Copy our staging configuration
echo "📝 Installing staging configuration..."
sudo cp staging-nginx-http.conf /etc/nginx/sites-available/staging

# Enable the staging site
echo "🔗 Enabling staging site..."
sudo ln -sf /etc/nginx/sites-available/staging /etc/nginx/sites-enabled/staging

sudo cp staging-nginx-stream.conf /etc/nginx/nginx.conf

# Remove default site to avoid conflicts
echo "🗑️  Removing default site..."
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

# Start nginx
echo "▶️  Starting nginx..."
sudo systemctl start nginx
sudo systemctl enable nginx

# Check status
echo "📊 Nginx status:"
sudo systemctl status nginx --no-pager -l

echo ""
echo "✅ Staging nginx setup complete!"
echo ""
echo "📋 Next steps:"
echo "1. Test HTTP access: curl -H 'Host: staging.motherstream.live' http://localhost"
echo "2. Set up SSL certificate: sudo certbot --nginx -d staging.motherstream.live"
echo "3. Test external access: curl http://staging.motherstream.live"
echo ""
echo "🔍 Logs:"
echo "   Access: sudo tail -f /var/log/nginx/staging_access.log"
echo "   Error:  sudo tail -f /var/log/nginx/staging_error.log"
