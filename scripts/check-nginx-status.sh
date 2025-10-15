#!/bin/bash

# Check nginx and port status script

echo "🔍 Checking nginx and port status..."
echo ""

echo "📊 Current processes on port 80:"
sudo lsof -i :80 || echo "No processes found or lsof not available"
echo ""

echo "📊 Current processes on port 443:"
sudo lsof -i :443 || echo "No processes found or lsof not available"
echo ""

echo "🌐 Network listening status:"
ss -tlnp | grep -E ":(80|443)"
echo ""

echo "🔧 nginx service status:"
sudo systemctl status nginx --no-pager -l || echo "nginx service not found"
echo ""

echo "📝 nginx configuration test:"
sudo nginx -t || echo "nginx configuration test failed"
echo ""

echo "📂 nginx sites enabled:"
ls -la /etc/nginx/sites-enabled/ || echo "sites-enabled directory not found"
echo ""

echo "🧪 Test staging configuration:"
echo "Testing local connection to staging..."
curl -I -H "Host: staging.motherstream.live" http://localhost --connect-timeout 5 || echo "Local test failed"
echo ""

echo "🌍 Test external staging access:"
echo "Testing external connection..."
curl -I http://staging.motherstream.live --connect-timeout 10 || echo "External test failed"
echo ""

echo "✅ Status check complete!"
