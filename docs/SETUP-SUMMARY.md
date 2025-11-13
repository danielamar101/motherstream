# 🎉 Staging Environment Setup - Complete!

Your Motherstream application now supports running production and staging environments on the same server!

## ✅ What Was Done

### 1. **Application Code Updates**
- ✅ `main.py` - Dynamic CORS origins from environment
- ✅ `app/api/rtmp_endpoints.py` - Configurable RTMP URLs
- ✅ `app/core/process_manager.py` - Environment-aware stream health checking
- ✅ `app/core/srs_stream_manager.py` - Configurable Oryx API endpoints
- ✅ `app/api/shazam.py` - Environment-specific Shazam RTMP URLs
- ✅ `frontend/src/main.tsx` - Dynamic API URL from environment
- ✅ `frontend/src/routes/_layout/admin.tsx` - Standardized environment variables

### 2. **Docker Infrastructure**
- ✅ `docker-compose.base.yml` - Shared service definitions
- ✅ `docker-compose.prod.yml` - Production configuration
- ✅ `docker-compose.staging.yml` - Staging configuration
- ✅ `docker-compose.router.yml` - Nginx router for domain-based routing
- ✅ `nginx-config/router.conf` - Smart routing for both domains on port 443

### 3. **Helper Scripts**
- ✅ `setup-env-files.sh` - Creates environment files
- ✅ `setup-staging-dirs.sh` - Creates staging directories
- ✅ `docker-prod.sh` - Production docker-compose wrapper
- ✅ `docker-staging.sh` - Staging docker-compose wrapper
- ✅ `docker-router.sh` - Router docker-compose wrapper
- ✅ `start-all.sh` - Start everything with one command
- ✅ `stop-all.sh` - Stop everything with one command

### 4. **Documentation**
- ✅ `STAGING-SETUP.md` - Complete operations guide
- ✅ `MIGRATION-GUIDE.md` - Step-by-step migration instructions
- ✅ `SETUP-SUMMARY.md` - This file

### 5. **Configuration**
- ✅ Updated `.gitignore` to exclude environment files and staging data
- ✅ Made all shell scripts executable

## 🚀 Next Steps (REQUIRED)

### Step 1: Create Environment Files
```bash
./setup-env-files.sh
```

Then edit the created files and replace all `CHANGE_ME_*` values:
- `.env.prod`
- `.env.staging`
- `frontend/.env.prod`
- `frontend/.env.staging`

**Critical variables to update:**
- Database passwords
- JWT secrets
- OBS passwords
- Sentry DSNs (if using)
- Discord webhooks
- SRS authorization bearers

### Step 2: Set Up DNS
Add an A record for staging:
```
staging.motherstream.live → [Your Server IP]
```

### Step 3: Create Staging Directories
```bash
./setup-staging-dirs.sh
```

### Step 4: Get SSL Certificate for Staging
```bash
# First, ensure port 80 is available
sudo certbot certonly --webroot \
  -w ./certbot/www \
  -d staging.motherstream.live \
  --email your@email.com \
  --agree-tos

# Copy to staging directory
sudo cp -r /etc/letsencrypt/live/staging.motherstream.live ./staging/certs/live/
sudo chown -R $USER:$USER ./staging/certs/
```

### Step 5: Start Everything
```bash
./start-all.sh
```

This will:
1. Create Docker networks
2. Start production environment
3. Start staging environment
4. Start nginx router

## 🧪 Testing

### Test Production
```bash
# Check API
curl https://motherstream.live/backend/health

# Open in browser
open https://motherstream.live
```

### Test Staging
```bash
# Check API
curl https://staging.motherstream.live/backend/health

# Open in browser
open https://staging.motherstream.live
```

### Test RTMP Streaming
```bash
# Production RTMP (port 1935)
ffmpeg -re -i test.mp4 -c copy -f flv \
  rtmp://motherstream.live:1935/live/[your-stream-key]

# Staging RTMP (port 1936)
ffmpeg -re -i test.mp4 -c copy -f flv \
  rtmp://staging.motherstream.live:1936/live/[your-stream-key]
```

## 📊 Service Overview

### Production Stack
- **Frontend**: https://motherstream.live
- **Backend**: https://motherstream.live/backend
- **RTMP**: rtmp://motherstream.live:1935
- **Database**: localhost:5432
- **Container Names**: `*-prod`

### Staging Stack
- **Frontend**: https://staging.motherstream.live
- **Backend**: https://staging.motherstream.live/backend
- **RTMP**: rtmp://staging.motherstream.live:1936
- **Database**: localhost:5433
- **Container Names**: `*-staging`

### Router
- **Ports**: 80, 443
- **Function**: Routes traffic by domain name to correct environment
- **Container**: `nginx-router`

## 🔧 Daily Commands

### View Status
```bash
docker ps | grep -E "(prod|staging|router)"
```

### View Logs
```bash
./docker-prod.sh logs -f              # Production
./docker-staging.sh logs -f           # Staging
./docker-router.sh logs -f            # Router
```

### Restart Service
```bash
./docker-prod.sh restart motherstream     # Production backend
./docker-staging.sh restart frontend      # Staging frontend
```

### Rebuild After Code Changes
```bash
./docker-staging.sh up -d --build    # Test on staging first!
./docker-prod.sh up -d --build       # Then deploy to prod
```

## 📁 Important File Locations

### Environment Files (DO NOT COMMIT)
- `.env.prod` - Production secrets
- `.env.staging` - Staging secrets
- `frontend/.env.prod` - Frontend production config
- `frontend/.env.staging` - Frontend staging config

### Data Directories (GITIGNORED)
- `pgdata/` - Production database
- `oryx/` - Production media server data
- `stream-recordings/` - Production recordings
- `staging/pgdata/` - Staging database
- `staging/oryx/` - Staging media server data
- `staging/stream-recordings/` - Staging recordings

### Configuration Files
- `docker-compose.base.yml` - Shared services
- `docker-compose.prod.yml` - Production overrides
- `docker-compose.staging.yml` - Staging overrides
- `docker-compose.router.yml` - Nginx router
- `nginx-config/router.conf` - Routing rules

## 🔐 Security Reminders

- ❌ Never commit `.env.prod` or `.env.staging`
- ✅ Use different passwords for prod and staging
- ✅ Use separate Discord webhooks
- ✅ Use separate Sentry projects
- ✅ Keep staging database isolated from production
- ✅ Set `TOGGLE_DISCORD_NOTIFICATIONS=false` in staging

## 🐛 Troubleshooting

### "Cannot connect to service"
Check container is running and on correct network:
```bash
docker ps | grep [service-name]
docker network inspect prod-network
```

### "Database connection failed"
Verify DB_HOST in .env matches container name:
- Production: `DB_HOST=postgres-prod`
- Staging: `DB_HOST=postgres-staging`

### "CORS errors"
Add your domain to ALLOWED_ORIGINS in .env files:
```bash
ALLOWED_ORIGINS=https://yoursite.com,http://yoursite.com
```

### "SSL certificate not found"
Ensure certbot obtained certificates and they're in correct locations:
- Prod: `./certs/live/motherstream.live/`
- Staging: `./staging/certs/live/staging.motherstream.live/`

## 📚 Additional Documentation

- **`STAGING-SETUP.md`** - Detailed operations guide
- **`MIGRATION-GUIDE.md`** - Migrating from old setup
- **`README.md`** - Original project README

## 🎯 Deployment Workflow

1. **Develop locally** with `./start-dev.sh`
2. **Push to git**
3. **Deploy to staging** and test:
   ```bash
   git pull
   ./docker-staging.sh up -d --build
   ```
4. **Test thoroughly** on staging.motherstream.live
5. **Deploy to production** if tests pass:
   ```bash
   ./docker-prod.sh up -d --build
   ```

## 🆘 Need Help?

1. Check the detailed guides:
   - Operations: `STAGING-SETUP.md`
   - Migration: `MIGRATION-GUIDE.md`

2. Check logs:
   ```bash
   ./docker-prod.sh logs --tail=100
   ./docker-staging.sh logs --tail=100
   ./docker-router.sh logs --tail=100
   ```

3. Check container status:
   ```bash
   docker ps -a
   docker network ls
   ```

## 🎊 You're All Set!

Your Motherstream application is now ready for dual-environment deployment. Follow the "Next Steps" section above to complete the setup.

Happy streaming! 🎥✨

