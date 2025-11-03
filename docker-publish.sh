#!/bin/bash
set -euo pipefail

cleanup() {
  if [ "${DOCKER_STARTED_BY_SCRIPT:-false}" = true ]; then
    echo "Stopping Docker service started by script..." >&2
    sudo systemctl stop docker
  fi
}
trap cleanup EXIT

usage() {
  cat >&2 <<EOF
Usage: $0 docker-user [pass-store-path|'input']
  docker-user       Docker Hub username (required)
  pass-store-path   pass store path to Docker Hub token (default: hub.docker.com/token)
                      Use 'input' to disable pass and write the password interactively.
EOF
  exit 1
}

if [ $# -lt 1 ]; then
  usage
fi

DOCKER_USER="$1"
PASS_STORE="${2:-hub.docker.com/token}"
IMAGE_NAME="tosk-bot"

BRANCH_NAME=$(git rev-parse --abbrev-ref HEAD || echo "")

# Check if Docker CLI is installed
if ! command -v docker >/dev/null 2>&1; then
  echo "Error: Docker is not installed or not in PATH." >&2
  exit 1
fi

# Check Docker service status
if systemctl is-active --quiet docker; then
  :
else
  if command -v systemctl >/dev/null 2>&1; then
    echo "Docker service not running. Starting it now..." >&2
    sudo systemctl start docker
    DOCKER_STARTED_BY_SCRIPT=true
  else
    echo "Docker does not appear to be running and systemd is not available to start it." >&2
    exit 1
  fi
fi

if [ -z "$BRANCH_NAME" ]; then
  echo "Warning: Could not detect git branch. Using 'undefined' as tag." >&2
  TAG="undefined"
else
  case "$BRANCH_NAME" in
    master|main)
      TAG="stable"
      ;;
    dev)
      TAG="latest"
      ;;
    *)
      TAG="$BRANCH_NAME"
      ;;
  esac
fi

# Retrieve Docker Hub token
if [ "$PASS_STORE" != "input" ] && command -v pass >/dev/null 2>&1; then
  DOCKERHUB_TOKEN=$(pass "$PASS_STORE" 2>/dev/null || echo "")
  if [ -z "$DOCKERHUB_TOKEN" ]; then
    echo "Error: Password store entry '$PASS_STORE' empty or missing." >&2
    exit 1
  fi
else
  read -s DOCKERHUB_TOKEN
  echo >&2  # new line after silent input
  if [ -z "$DOCKERHUB_TOKEN" ]; then
    echo "Error: No token entered." >&2
    exit 1
  fi
fi

# Login securely using password-stdin
echo "$DOCKERHUB_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin

docker build -t "$DOCKER_USER/$IMAGE_NAME:$TAG" .
docker push "$DOCKER_USER/$IMAGE_NAME:$TAG"
