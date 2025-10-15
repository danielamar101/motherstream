#!/bin/bash

# Cleanup port conflicts and start nginx properly

set -e

echo "🧹 Cleaning up port conflicts and starting nginx..."

# Stop any socat processes that might be using port 80
echo "🛑 Stopping socat processes..."
sudo pkill socat || echo "No socat processes found"

# Wait a moment for processes to stop
sleep 2

# Check if port 80 is now free
echo "🔍 Checking port 80 status..."
if sudo lsof -i :80 | grep -v COMMAND; then
    echo "⚠️  Port 80 is still in use. Checking what's using it:"
    sudo lsof -i :80
    echo ""
    echo "You may need to manually stop the process above."
    exit 1
else
    echo "✅ Port 80 is now free"
fi

# Copy the updated staging configuration
echo "📝 Installing staging configuration..."
sudo cp staging-nginx.conf /etc/nginx/sites-available/staging

# Make sure the staging site is enabled
echo "🔗 Enabling staging site..."
sudo ln -sf /etc/nginx/sites-available/staging /etc/nginx/sites-enabled/staging

# Remove default site to avoid conflicts
echo "🗑️  Removing default site..."
sudo rm -f /etc/nginx/sites-enabled/default

# Test nginx configuration
echo "🧪 Testing nginx configuration..."
sudo nginx -t

if [ $? -eq 0 ]; then
    echo "✅ Configuration test passed!"
    
    # Start nginx
    echo "▶️  Starting nginx..."
    sudo systemctl start nginx
    sudo systemctl enable nginx
    
    # Check status
    echo "📊 Nginx status:"
    sudo systemctl status nginx --no-pager -l
    
    echo ""
    echo "🎉 Success! nginx is now running with staging configuration."
    echo ""
    echo "🧪 Testing local connection..."
    sleep 2
    curl -I -H "Host: staging.motherstream.live" http://localhost --connect-timeout 5 || echo "Local test failed - this might be normal if minikube isn't responding"
    
    echo ""
    echo "🌍 Testing external connection..."
    curl -I http://staging.motherstream.live --connect-timeout 10 || echo "External test failed - this might be normal initially"
    
    echo ""
    echo "📋 Next steps:"
    echo "1. Test: curl -H 'Host: staging.motherstream.live' http://localhost"
    echo "2. Test: curl http://staging.motherstream.live"
    echo "3. Set up SSL: sudo certbot --nginx -d staging.motherstream.live"
    echo "4. Uncomment HTTPS section in /etc/nginx/sites-available/staging"
    
else
    echo "❌ Configuration test failed. Check the error above."
    exit 1
fi
