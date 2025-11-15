#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: scripts/run_migrations.sh [--env prod|staging]

Runs Alembic migrations inside the motherstream Docker service for the given
environment. The corresponding docker-compose file must already be running.

Examples:
  scripts/run_migrations.sh --env prod
  scripts/run_migrations.sh staging
USAGE
  exit 1
}

env_name=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    -e|--env)
      env_name="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      env_name="$1"
      shift
      ;;
  esac
done

if [[ -z "$env_name" ]]; then
  echo "Error: missing --env argument." >&2
  usage
fi

case "$env_name" in
  prod|production)
    compose_file="docker-compose.prod.yml"
    ;;
  stage|staging)
    compose_file="docker-compose.staging.yml"
    ;;
  *)
    echo "Error: unsupported environment '$env_name' (use prod or staging)." >&2
    usage
    ;;
esac

base_compose="docker-compose.base.yml"
if [[ ! -f "$base_compose" ]]; then
  echo "Error: $base_compose not found in $(pwd)" >&2
  exit 1
fi

if [[ ! -f "$compose_file" ]]; then
  echo "Error: $compose_file not found in $(pwd)" >&2
  exit 1
fi

if docker compose version >/dev/null 2>&1; then
  compose_cmd=(docker compose -f "$base_compose" -f "$compose_file")
elif docker-compose version >/dev/null 2>&1; then
  compose_cmd=(docker-compose -f "$base_compose" -f "$compose_file")
else
  echo "Error: docker compose is not installed." >&2
  exit 1
fi

service_name="motherstream"

is_service_running() {
  # Check both via docker compose AND via docker ps directly
  # This handles cases where containers were started outside compose tracking
  local compose_container_id
  compose_container_id=$("${compose_cmd[@]}" ps -q "${service_name}" 2>/dev/null || true)
  
  if [[ -n "${compose_container_id}" ]]; then
    return 0
  fi
  
  # Also check if a container with the expected name is running
  local container_name
  case "$env_name" in
    prod|production)
      container_name="motherstream-prod"
      ;;
    stage|staging)
      container_name="motherstream-staging"
      ;;
  esac
  
  local running_container
  running_container=$(docker ps -q -f "name=^/${container_name}$" 2>/dev/null || true)
  [[ -n "${running_container}" ]]
}

wait_for_service() {
  local attempt=0
  local max_attempts=30
  local sleep_seconds=2

  while ! is_service_running; do
    if (( attempt >= max_attempts )); then
      echo "Error: service '${service_name}' did not reach running state within $((max_attempts * sleep_seconds)) seconds." >&2
      exit 1
    fi
    sleep "${sleep_seconds}"
    ((attempt++))
  done
}

ensure_service_running() {
  if is_service_running; then
    return
  fi

  echo "Service '${service_name}' is not running. Starting it via docker compose..."
  "${compose_cmd[@]}" up -d "${service_name}"

  echo "Waiting for service '${service_name}' to report as running..."
  wait_for_service
  echo "Service '${service_name}' is running."
}

echo "Running Alembic migrations for '$env_name' via $base_compose + $compose_file..."
echo "Ensuring the '${service_name}' service is running before executing migrations..."

ensure_service_running

# Determine the actual container name to use for exec
container_name=""
case "$env_name" in
  prod|production)
    container_name="motherstream-prod"
    ;;
  stage|staging)
    container_name="motherstream-staging"
    ;;
esac

# Try compose exec first, fall back to direct docker exec if needed
compose_container_id=$("${compose_cmd[@]}" ps -q "${service_name}" 2>/dev/null || true)
if [[ -n "${compose_container_id}" ]]; then
  echo "Executing migrations via docker compose exec..."
  "${compose_cmd[@]}" exec "${service_name}" bash -c "cd /app && /app/dependencies/bin/alembic upgrade head"
else
  echo "Executing migrations via docker exec (container: ${container_name})..."
  docker exec "${container_name}" bash -c "cd /app && /app/dependencies/bin/alembic upgrade head"
fi

