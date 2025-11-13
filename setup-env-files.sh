#!/bin/bash
# Setup script to create environment files for prod and staging

echo "Creating environment files..."

# Create .env.prod
cat > .env.prod << 'EOF'
# Production Environment Variables
ENV=prod
DOMAIN=motherstream.live

# Database
DB_HOST=postgres-prod
DB_PORT=5432
DB_NAME=motherstream_prod
DB_USER=postgres
DB_PASSWORD=CHANGE_ME_PROD_PASSWORD

# Backend Configuration
DEBUG_PORT=5555
HOST=https://motherstream.live
BACKEND_PORT=8483

# RTMP Configuration
RTMP_HOST=nginx-prod
RTMP_PORT=1935
RTMP_RECORD_PORT=1936
NGINX_RTMP_PORT=1935

# Oryx/SRS Configuration
ORYX_HOST=oryx-prod
ORYX_PORT=2022
SRS_AUTHORIZATION_BEARER=CHANGE_ME_SRS_BEARER

# OBS Configuration
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=CHANGE_ME_OBS_PASSWORD

# Monitoring and Logging
SENTRY_DSN=CHANGE_ME_SENTRY_DSN
STAT_PORT=8989

# Security
JWT_SECRET=CHANGE_ME_JWT_SECRET

# SMTP (unused currently)
SMTP_SERVER=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=

# API URLs
VITE_API_URL=https://motherstream.live/backend

# Discord Notifications
DISCORD_WEBHOOK_URL=CHANGE_ME_DISCORD_WEBHOOK
TOGGLE_DISCORD_NOTIFICATIONS=true

# Recording
RECORD_DIR=/var/www/streams/stream-recordings
RECORD_STREAM=true

# Shazam
SHAZAM_RTMP_URL=rtmp://motherstream.live/motherstream/live
SHAZAMING=false

# CORS Origins (comma-separated)
ALLOWED_ORIGINS=https://motherstream.live,http://motherstream.live

# Locale
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
EOF

# Create .env.staging
cat > .env.staging << 'EOF'
# Staging Environment Variables
ENV=staging
DOMAIN=staging.motherstream.live

# Database
DB_HOST=postgres-staging
DB_PORT=5432
DB_NAME=motherstream_staging
DB_USER=postgres
DB_PASSWORD=CHANGE_ME_STAGING_PASSWORD

# Backend Configuration
DEBUG_PORT=5556
HOST=https://staging.motherstream.live
BACKEND_PORT=8483

# RTMP Configuration
RTMP_HOST=nginx-staging
RTMP_PORT=1935
RTMP_RECORD_PORT=1936
NGINX_RTMP_PORT=1935

# Oryx/SRS Configuration
ORYX_HOST=oryx-staging
ORYX_PORT=2022
SRS_AUTHORIZATION_BEARER=CHANGE_ME_SRS_BEARER_STAGING

# OBS Configuration
OBS_HOST=localhost
OBS_PORT=4455
OBS_PASSWORD=CHANGE_ME_OBS_PASSWORD_STAGING

# Monitoring and Logging
SENTRY_DSN=CHANGE_ME_SENTRY_DSN_STAGING
STAT_PORT=8989

# Security
JWT_SECRET=CHANGE_ME_JWT_SECRET_STAGING

# SMTP (unused currently)
SMTP_SERVER=
SMTP_PORT=
SMTP_USER=
SMTP_PASSWORD=

# API URLs
VITE_API_URL=https://staging.motherstream.live/backend

# Discord Notifications
DISCORD_WEBHOOK_URL=CHANGE_ME_DISCORD_WEBHOOK_STAGING
TOGGLE_DISCORD_NOTIFICATIONS=false

# Recording
RECORD_DIR=/var/www/streams/stream-recordings
RECORD_STREAM=true

# Shazam
SHAZAM_RTMP_URL=rtmp://staging.motherstream.live/motherstream/live
SHAZAMING=false

# CORS Origins (comma-separated)
ALLOWED_ORIGINS=https://staging.motherstream.live,http://staging.motherstream.live

# Locale
LANG=en_US.UTF-8
LC_ALL=en_US.UTF-8
EOF

# Create frontend/.env.prod
cat > frontend/.env.prod << 'EOF'
# Frontend Production Environment
VITE_API_URL=https://motherstream.live/backend
EOF

# Create frontend/.env.staging
cat > frontend/.env.staging << 'EOF'
# Frontend Staging Environment
VITE_API_URL=https://staging.motherstream.live/backend
EOF

echo "✓ Created .env.prod"
echo "✓ Created .env.staging"
echo "✓ Created frontend/.env.prod"
echo "✓ Created frontend/.env.staging"
echo ""
echo "⚠️  IMPORTANT: Update all 'CHANGE_ME_*' values with your actual credentials!"
echo ""

