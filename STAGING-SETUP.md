# Staging Environment Setup Guide

This guide explains how to set up and manage the production and staging environments for Motherstream.

## Overview

Both production and staging environments run on the same server with:
- **Production**: `motherstream.live` (HTTP/HTTPS frontend and backend)
- **Production RTMP**: `always12.live:1935` (RTMP streaming only - legacy domain)
- **Staging**: `staging.motherstream.live`

A shared Nginx router handles HTTPS for both environments on standard ports (80/443) and routes traffic based on domain name.

## Architecture

```
Internet (Port 80/443)
    ↓
Nginx Router (nginx-router)
    ├─→ motherstream.live → Production Stack
    │   ├─ frontend-prod:5173
    │   ├─ motherstream-prod:8483
    │   ├─ postgres-prod:5432
    │   ├─ oryx-prod:2022
    │   └─ nginx-prod:1935 (RTMP)
    │
    └─→ staging.motherstream.live → Staging Stack
        ├─ frontend-staging:5174
        ├─ motherstream-staging:8484
        ├─ postgres-staging:5433
        ├─ oryx-staging:2023
        └─ nginx-staging:1936 (RTMP)
```

## Initial Setup

### 1. Create Environment Files

Run the setup script to create environment files:

```bash
./setup-env-files.sh
```

This creates:
- `.env.prod` - Production environment variables
- `.env.staging` - Staging environment variables
- `frontend/.env.prod` - Frontend production config
- `frontend/.env.staging` - Frontend staging config

**⚠️ IMPORTANT**: Edit these files and replace all `CHANGE_ME_*` values with your actual credentials!

### 2. Set Up Staging Directories

```bash
./setup-staging-dirs.sh
```

This creates the necessary directory structure for staging:
- `staging/stream-recordings` - Stream recordings
- `staging/oryx` - Oryx media server data
- `staging/certs` - SSL certificates
- `staging/pgdata` - PostgreSQL data

### 3. Configure DNS

Add an A record for your staging domain:
```
staging.motherstream.live → [Your Server IP]
```

Wait for DNS propagation (5-15 minutes).

### 4. Get SSL Certificate for Staging

Before starting the services, you need SSL certificates. Update your certbot configuration or run:

```bash
# Start the router to serve certbot challenges
./docker-router.sh up -d

# Get staging certificate
sudo certbot certonly --webroot \
  -w ./certbot/www \
  -d staging.motherstream.live \
  --cert-path ./staging/certs/live/staging.motherstream.live \
  --email your@email.com \
  --agree-tos
```

## Daily Operations

### Starting Services

**Start Everything:**
```bash
./start-all.sh
```

**Start Individual Environments:**
```bash
./docker-prod.sh up -d      # Production only
./docker-staging.sh up -d   # Staging only
./docker-router.sh up -d    # Router only
```

### Stopping Services

**Stop Everything:**
```bash
./stop-all.sh
```

**Stop Individual Environments:**
```bash
./docker-prod.sh down      # Production only
./docker-staging.sh down   # Staging only
./docker-router.sh down    # Router only
```

### Viewing Logs

```bash
./docker-prod.sh logs -f              # All production services
./docker-staging.sh logs -f           # All staging services
./docker-router.sh logs -f            # Router logs

./docker-prod.sh logs -f motherstream      # Specific service
./docker-staging.sh logs -f frontend       # Specific service
```

### Restarting Services

```bash
./docker-prod.sh restart motherstream      # Restart production backend
./docker-staging.sh restart frontend       # Restart staging frontend
```

### Rebuilding Containers

After code changes:
```bash
./docker-prod.sh up -d --build            # Rebuild production
./docker-staging.sh up -d --build         # Rebuild staging
```

## Accessing the Environments

- **Production Frontend**: https://motherstream.live
- **Production API**: https://motherstream.live/backend
- **Production RTMP**: rtmp://motherstream.live:1935/live/[stream-key] or rtmp://always12.live:1935/live/[stream-key]

- **Staging Frontend**: https://staging.motherstream.live
- **Staging API**: https://staging.motherstream.live/backend
- **Staging RTMP**: rtmp://staging.motherstream.live:1936/live/[stream-key]

> **Note**: `always12.live` is a legacy domain that only supports RTMP streaming (port 1935). It does not serve HTTP/HTTPS traffic. For all web access, use `motherstream.live`.

## Testing Staging

### 1. Test API Connectivity
```bash
curl https://staging.motherstream.live/backend/health
```

### 2. Test RTMP Streaming
```bash
ffmpeg -re -i test.mp4 -c copy -f flv \
  rtmp://staging.motherstream.live:1936/live/[your-stream-key]
```

### 3. Test Frontend
Open your browser to `https://staging.motherstream.live`

## Database Management

### Access Production Database
```bash
./docker-prod.sh exec postgres psql -U postgres -d motherstream_prod
```

### Access Staging Database
```bash
./docker-staging.sh exec postgres psql -U postgres -d motherstream_staging
```

### Backup Production Database
```bash
./docker-prod.sh exec postgres pg_dump -U postgres motherstream_prod > backup_prod.sql
```

### Restore to Staging
```bash
cat backup_prod.sql | ./docker-staging.sh exec -T postgres psql -U postgres -d motherstream_staging
```

## Troubleshooting

### Check Container Status
```bash
docker ps | grep -E "(prod|staging|router)"
```

### Check Network Connectivity
```bash
docker network inspect prod-network
docker network inspect staging-network
```

### Test Backend from Router
```bash
docker exec nginx-router curl http://motherstream-prod:8483/health
docker exec nginx-router curl http://motherstream-staging:8483/health
```

### Check Nginx Router Configuration
```bash
docker exec nginx-router nginx -t
./docker-router.sh restart
```

### View All Logs
```bash
./docker-prod.sh logs --tail=100
./docker-staging.sh logs --tail=100
./docker-router.sh logs --tail=100
```

### Common Issues

**"Container not found"**
- Ensure networks are created: `docker network create prod-network staging-network`
- Start services in order: prod/staging first, then router

**"SSL certificate not found"**
- Ensure certbot has obtained certificates for both domains
- Check certificate paths match in `nginx-config/router.conf`

**"Cannot connect to database"**
- Check that postgres containers are running
- Verify DB_HOST in .env files matches container names
- Check database credentials

**"CORS errors"**
- Verify ALLOWED_ORIGINS in .env files includes correct domains
- Check that frontend VITE_API_URL points to correct backend

## Deployment Workflow

1. **Develop locally** with `./start-dev.sh`
2. **Push changes** to git repository
3. **Pull on server** and test on staging:
   ```bash
   git pull
   ./docker-staging.sh up -d --build
   # Test on staging.motherstream.live
   ```
4. **Deploy to production** if staging tests pass:
   ```bash
   ./docker-prod.sh up -d --build
   ```

## File Structure

```
motherstream/
├── .env.prod                      # Production environment vars
├── .env.staging                   # Staging environment vars
├── docker-compose.base.yml        # Base services definition
├── docker-compose.prod.yml        # Production overrides
├── docker-compose.staging.yml     # Staging overrides
├── docker-compose.router.yml      # Nginx router
├── docker-prod.sh                 # Production helper
├── docker-staging.sh              # Staging helper
├── docker-router.sh               # Router helper
├── start-all.sh                   # Start everything
├── stop-all.sh                    # Stop everything
├── setup-env-files.sh             # Create .env files
├── setup-staging-dirs.sh          # Create staging dirs
├── nginx-config/
│   └── router.conf                # Nginx routing config
├── frontend/
│   ├── .env.prod                  # Frontend prod config
│   └── .env.staging               # Frontend staging config
└── staging/                       # Staging data (gitignored)
    ├── stream-recordings/
    ├── oryx/
    ├── certs/
    └── pgdata/
```

## Security Notes

- Never commit `.env.prod` or `.env.staging` files
- Use strong, unique passwords for each environment
- Rotate secrets regularly
- Keep staging database separate from production
- Use different Discord webhooks for prod/staging notifications

## Monitoring

- **Production Sentry**: Use production SENTRY_DSN
- **Staging Sentry**: Use separate staging SENTRY_DSN (or disable)
- **Discord**: Separate webhooks for prod/staging alerts

## SSL Certificate Renewal

Certificates auto-renew with certbot. Set up a cron job:

```bash
# Add to crontab (crontab -e)
0 3 * * * cd /home/motherstream/Desktop/motherstream && certbot renew --webroot -w ./certbot/www && ./docker-router.sh restart
```

## Additional Resources

- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Nginx Documentation](https://nginx.org/en/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)

