#!/bin/bash
# Production Docker Compose Helper Script

sudo docker compose -p motherstream-prod -f docker-compose.base.yml -f docker-compose.prod.yml --env-file .env.prod "$@"

