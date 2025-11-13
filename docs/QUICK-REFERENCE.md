# Quick Reference Card

## 🚀 Essential Commands

### Start/Stop
```bash
./start-all.sh              # Start everything
./stop-all.sh               # Stop everything
./docker-prod.sh up -d      # Start production only
./docker-staging.sh up -d   # Start staging only
```

### Logs
```bash
./docker-prod.sh logs -f              # Production logs
./docker-staging.sh logs -f           # Staging logs
./docker-router.sh logs -f            # Router logs
./docker-prod.sh logs -f motherstream # Specific service
```

### Restart
```bash
./docker-prod.sh restart [service]      # Restart prod service
./docker-staging.sh restart [service]   # Restart staging service
./docker-router.sh restart              # Restart router
```

### Rebuild
```bash
./docker-prod.sh up -d --build       # Rebuild production
./docker-staging.sh up -d --build    # Rebuild staging
```

### Database
```bash
# Access database
./docker-prod.sh exec postgres psql -U postgres -d motherstream_prod
./docker-staging.sh exec postgres psql -U postgres -d motherstream_staging

# Backup
./docker-prod.sh exec postgres pg_dump -U postgres motherstream_prod > backup.sql

# Restore
cat backup.sql | ./docker-staging.sh exec -T postgres psql -U postgres -d motherstream_staging
```

## 🌐 URLs

| Environment | Frontend | Backend | RTMP |
|-------------|----------|---------|------|
| **Production** | https://motherstream.live | https://motherstream.live/backend | rtmp://motherstream.live:1935 |
| **Staging** | https://staging.motherstream.live | https://staging.motherstream.live/backend | rtmp://staging.motherstream.live:1936 |

> **Note**: `always12.live` is a legacy domain used for RTMP streaming only. For HTTP/HTTPS, use `motherstream.live`.

## 📦 Container Names

| Service | Production | Staging |
|---------|------------|---------|
| Backend | motherstream-prod | motherstream-staging |
| Frontend | frontend-prod | frontend-staging |
| Database | postgres-prod | postgres-staging |
| Nginx | nginx-prod | nginx-staging |
| Oryx | oryx-prod | oryx-staging |
| Router | nginx-router | - |

## 🔌 Port Mappings

| Service | Production | Staging |
|---------|------------|---------|
| Frontend | 5173 | 5174 |
| Backend | 8483 | 8484 |
| Database | 5432 | 5433 |
| RTMP | 1935 | 1936 |
| Stats | 8989 | 8990 |
| Oryx | 2022 | 2023 |
| Oryx HTTP | 8080 | 8082 |
| HTTP/HTTPS | 80/443 (router) | 80/443 (router) |

## 🔑 Environment Files

- `.env.prod` - Production backend env vars
- `.env.staging` - Staging backend env vars
- `frontend/.env.prod` - Production frontend env vars
- `frontend/.env.staging` - Staging frontend env vars

## 📂 Data Locations

| Data Type | Production | Staging |
|-----------|------------|---------|
| Database | `./pgdata/` | `./staging/pgdata/` |
| Recordings | `./stream-recordings/` | `./staging/stream-recordings/` |
| Oryx | `./oryx/` | `./staging/oryx/` |
| SSL Certs | `./certs/` | `./staging/certs/` |

## 🛠️ Troubleshooting One-Liners

```bash
# Check all containers
docker ps | grep -E "(prod|staging|router)"

# Check networks
docker network inspect prod-network
docker network inspect staging-network

# Test backend from router
docker exec nginx-router curl http://motherstream-prod:8483/health
docker exec nginx-router curl http://motherstream-staging:8483/health

# Check nginx config
docker exec nginx-router nginx -t

# View environment vars
./docker-prod.sh exec motherstream env | grep -E "DB_|RTMP_|ORYX_"
./docker-staging.sh exec motherstream env | grep -E "DB_|RTMP_|ORYX_"

# Restart everything
./stop-all.sh && ./start-all.sh
```

## 📋 Initial Setup Checklist

- [ ] Run `./setup-env-files.sh`
- [ ] Edit `.env.prod` - replace CHANGE_ME values
- [ ] Edit `.env.staging` - replace CHANGE_ME values
- [ ] Edit `frontend/.env.prod`
- [ ] Edit `frontend/.env.staging`
- [ ] Set up DNS for staging.motherstream.live
- [ ] Run `./setup-staging-dirs.sh`
- [ ] Get SSL cert for staging domain
- [ ] Run `./start-all.sh`
- [ ] Test production: https://motherstream.live
- [ ] Test staging: https://staging.motherstream.live

## 🔄 Deployment Workflow

1. Develop → 2. Push → 3. Deploy to Staging → 4. Test → 5. Deploy to Prod

```bash
# On server
git pull
./docker-staging.sh up -d --build   # Test on staging
# If OK:
./docker-prod.sh up -d --build      # Deploy to prod
```

