# Manual nginx Setup for Staging

## 🚨 Current Issue
The original setup script installed nginx configuration with SSL certificates that don't exist yet, causing nginx to fail to start.

## 🔧 Manual Fix Steps

Run these commands one by one:

### 1. Copy the corrected configuration (without SSL)
```bash
cd /home/motherstream/Desktop/motherstream
sudo cp staging-nginx.conf /etc/nginx/sites-available/staging
```

### 2. Test the configuration
```bash
sudo nginx -t
```
This should now pass without SSL certificate errors.

### 3. Start nginx
```bash
sudo systemctl start nginx
sudo systemctl enable nginx
```

### 4. Check nginx status
```bash
sudo systemctl status nginx
```

### 5. Test local connection
```bash
curl -I -H "Host: staging.motherstream.live" http://localhost
```

### 6. Test external connection
```bash
curl -I http://staging.motherstream.live
```

## 🎯 Expected Results

After step 2, you should see:
```
nginx: the configuration file /etc/nginx/nginx.conf syntax is ok
nginx: configuration file /etc/nginx/nginx.conf test is successful
```

After step 5, you should see HTTP headers from your staging frontend.

After step 6, you should see the same headers, confirming external access works.

## 🔍 Key Difference

The `staging-nginx.conf` file has the HTTPS section commented out:
- ✅ HTTP server block (port 80) - ACTIVE
- 💤 HTTPS server block (port 443) - COMMENTED OUT until SSL is set up

This allows nginx to start without requiring SSL certificates.
