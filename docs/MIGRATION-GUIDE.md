# Migration Guide: Single to Multi-Environment Setup

This guide helps you migrate from the existing single docker-compose.yml to the new multi-environment setup.

## What Changed

### Files Added
- `docker-compose.base.yml` - Base configuration
- `docker-compose.prod.yml` - Production overrides
- `docker-compose.staging.yml` - Staging overrides
- `docker-compose.router.yml` - Nginx router
- `.env.prod` / `.env.staging` - Environment-specific configs
- `nginx-config/router.conf` - Routing configuration
- Multiple helper scripts (`.sh` files)

### Files Modified
- `main.py` - Added ALLOWED_ORIGINS from env
- `app/api/rtmp_endpoints.py` - RTMP URLs from env
- `app/core/process_manager.py` - Stream health URLs from env
- `app/core/srs_stream_manager.py` - Oryx API URLs from env
- `app/api/shazam.py` - Shazam RTMP URL from env
- `frontend/src/main.tsx` - API URL from env
- `frontend/src/routes/_layout/admin.tsx` - Standardized env var

### Old docker-compose.yml
Your existing `docker-compose.yml` has been preserved. The new system uses separate files.

## Migration Steps

### Step 1: Backup Current Setup

```bash
# Backup your current environment
cp .env .env.backup
docker-compose ps > containers-backup.txt

# Backup databases
docker-compose exec postgres pg_dump -U postgres [DB_NAME] > db-backup.sql
```

### Step 2: Stop Current Services

```bash
docker-compose down
```

### Step 3: Create Environment Files

```bash
# Run the setup script
./setup-env-files.sh

# Copy values from your old .env to .env.prod
# Edit and update any CHANGE_ME values
nano .env.prod
nano .env.staging
nano frontend/.env.prod
nano frontend/.env.staging
```

### Step 4: Set Up Staging Directories

```bash
./setup-staging-dirs.sh
```

### Step 5: Copy Production Data

If you want to use existing data for production:

```bash
# Production will use existing directories by default
# Just ensure permissions are correct
sudo chown -R $USER:$USER pgdata/ oryx/ stream-recordings/
```

### Step 6: Create Docker Networks

```bash
docker network create prod-network
docker network create staging-network
```

### Step 7: Start Production First

```bash
# Start production environment
./docker-prod.sh up -d

# Check logs
./docker-prod.sh logs -f

# Test that production works
curl https://motherstream.live/backend/health
```

### Step 8: Set Up Staging SSL

```bash
# Get staging SSL certificate
sudo certbot certonly --webroot \
  -w ./certbot/www \
  -d staging.motherstream.live \
  --cert-path ./staging/certs/live/staging.motherstream.live \
  --email your@email.com \
  --agree-tos

# Copy certificate to staging directory if needed
sudo cp -r /etc/letsencrypt/live/staging.motherstream.live ./staging/certs/live/
sudo chown -R $USER:$USER ./staging/certs/
```

### Step 9: Start Staging

```bash
# Start staging environment
./docker-staging.sh up -d

# Check logs
./docker-staging.sh logs -f
```

### Step 10: Start Router

```bash
# Start the nginx router
./docker-router.sh up -d

# Check that router can reach both environments
docker exec nginx-router curl http://motherstream-prod:8483/health
docker exec nginx-router curl http://motherstream-staging:8483/health
```

### Step 11: Test Everything

```bash
# Test production
curl https://motherstream.live/backend/health
open https://motherstream.live

# Test staging
curl https://staging.motherstream.live/backend/health
open https://staging.motherstream.live
```

## Rollback Plan

If something goes wrong, you can rollback:

```bash
# Stop new setup
./stop-all.sh

# Start old setup
docker-compose -f docker-compose.yml up -d

# Restore database if needed
cat db-backup.sql | docker-compose exec -T postgres psql -U postgres [DB_NAME]
```

## Environment Variable Mapping

Old `.env` → New `.env.prod`:

| Old Variable | New Variable | Notes |
|--------------|--------------|-------|
| DB_HOST | DB_HOST | Now `postgres-prod` instead of `localhost` or `postgres` |
| (new) | RTMP_HOST | New: `nginx-prod` |
| (new) | RTMP_PORT | New: `1935` |
| (new) | ORYX_HOST | New: `oryx-prod` |
| (new) | ORYX_PORT | New: `2022` |
| (new) | ALLOWED_ORIGINS | New: Comma-separated CORS origins |
| (new) | SHAZAM_RTMP_URL | New: RTMP URL for Shazam |

## Common Migration Issues

### Issue: "Cannot connect to database"
**Solution**: Update DB_HOST in .env files from `localhost` to `postgres-prod` or `postgres-staging`

### Issue: "CORS errors in browser"
**Solution**: Add your domains to ALLOWED_ORIGINS in .env files

### Issue: "Containers can't communicate"
**Solution**: Ensure containers are on the same network:
```bash
docker network inspect prod-network
docker network inspect staging-network
```

### Issue: "Old containers still running"
**Solution**: Clean up old containers:
```bash
docker ps -a | grep motherstream
docker rm -f [container-id]
```

### Issue: "Port already in use"
**Solution**: Check what's using the port:
```bash
sudo lsof -i :443
sudo lsof -i :80
```

## Verification Checklist

After migration, verify:

- [ ] Production frontend loads at https://motherstream.live
- [ ] Production API responds at https://motherstream.live/backend
- [ ] Staging frontend loads at https://staging.motherstream.live
- [ ] Staging API responds at https://staging.motherstream.live/backend
- [ ] Production database has existing data
- [ ] Staging database is separate/empty
- [ ] RTMP streaming works on both environments
- [ ] OBS can connect to both environments
- [ ] All environment variables are set correctly
- [ ] Logs show no connection errors
- [ ] Router correctly routes based on domain

## Post-Migration

1. **Update documentation** with new URLs and commands
2. **Update CI/CD pipelines** to use new scripts
3. **Notify team** about new staging environment
4. **Test deployment workflow** on staging first
5. **Monitor both environments** for issues

## Questions?

If you encounter issues not covered here, check:
1. `STAGING-SETUP.md` for detailed operations
2. Container logs: `./docker-prod.sh logs -f`
3. Router logs: `./docker-router.sh logs -f`
4. Network connectivity: `docker network inspect prod-network`

