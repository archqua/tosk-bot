#!/bin/bash
set -euo pipefail

usage() {
  cat >&2 <<EOF
Usage: $0 docker-user [pass-store-path|'none']
  docker-user       Docker Hub username (required)
  pass-store-path   pass store path to Docker Hub token (default: hub.docker.com/token)
                      Use 'none' to disable pass and fallback to DOCKERHUB_TOKEN env var.
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
if [ "$PASS_STORE" != "none" ] && command -v pass >/dev/null 2>&1; then
  DOCKERHUB_TOKEN=$(pass "$PASS_STORE" 2>/dev/null || echo "")
  if [ -z "$DOCKERHUB_TOKEN" ]; then
    echo "Error: Password store entry '$PASS_STORE' empty or missing." >&2
    exit 1
  fi
elif [ "$PASS_STORE" = "none" ]; then
  if [ -z "${DOCKERHUB_TOKEN:-}" ]; then
    echo "Error: DOCKERHUB_TOKEN environment variable not set and pass usage disabled." >&2
    exit 1
  fi
  DOCKERHUB_TOKEN="$DOCKERHUB_TOKEN"
else
  echo "Warning: 'pass' command not found or PASS_STORE issue. Falling back to DOCKERHUB_TOKEN env var." >&2
  if [ -z "${DOCKERHUB_TOKEN:-}" ]; then
    echo "Error: DOCKERHUB_TOKEN environment variable not set." >&2
    exit 1
  fi
  DOCKERHUB_TOKEN="$DOCKERHUB_TOKEN"
fi

# Login securely using password-stdin
echo "$DOCKERHUB_TOKEN" | docker login --username "$DOCKER_USER" --password-stdin

docker build -t "$DOCKER_USER/$IMAGE_NAME:$TAG" .
docker push "$DOCKER_USER/$IMAGE_NAME:$TAG"
