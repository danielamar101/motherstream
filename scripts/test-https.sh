#!/bin/bash

# Test HTTPS configuration

echo "🔧 Testing HTTPS setup for staging.motherstream.live..."

# Check if certificates exist
echo "📋 Checking SSL certificates..."
if [ -f "/home/motherstream/Desktop/motherstream/certs/live/staging.motherstream.live/fullchain.pem" ]; then
    echo "✅ Certificate found"
    ls -la /home/motherstream/Desktop/motherstream/certs/live/staging.motherstream.live/
else
    echo "❌ Certificate not found!"
    exit 1
fi

# Update nginx configuration
echo "📝 Updating nginx configuration..."
sudo cp staging-nginx.conf /etc/nginx/sites-available/staging

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuration test passed!"
    
    # Restart nginx
    echo "🔄 Restarting nginx..."
    sudo systemctl restart nginx
    
    # Wait a moment
    sleep 2
    
    # Test HTTP
    echo ""
    echo "🧪 Testing HTTP access..."
    curl -I http://staging.motherstream.live --connect-timeout 10
    
    # Test HTTPS
    echo ""
    echo "🧪 Testing HTTPS access..."
    curl -I https://staging.motherstream.live --connect-timeout 10 -k
    
    echo ""
    echo "✅ nginx restarted! Test the following URLs:"
    echo "   HTTP:  http://staging.motherstream.live"
    echo "   HTTPS: https://staging.motherstream.live"
    
else
    echo "❌ Configuration test failed. Check the error above."
    exit 1
fi
