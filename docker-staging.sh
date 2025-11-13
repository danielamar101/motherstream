#!/bin/bash
# Staging Docker Compose Helper Script

docker compose -p motherstream-staging -f docker-compose.base.yml -f docker-compose.staging.yml --env-file .env.staging "$@"

