#!/bin/bash
set -euo pipefail 

# Default values
TAG=${TAG:-latest}
USERNAME=${USERNAME:?Error: username required. Usage: ./release.sh -u username [-t tag]}

# Parse options
while getopts "t:u:h" opt; do
  case $opt in
    t) TAG="$OPTARG" ;;
    u) USERNAME="$OPTARG" ;;
    h) cat << 'HELP'
Usage: $0 [-t TAG] [-u USERNAME]
  -t: tag (default: latest)
  -u: registry username (required)
Examples:
  ./release.sh -u username
  ./release.sh -u username -t latest
HELP
      exit 0 ;;
    *) echo "Invalid option -$OPTARG"; exit 1 ;;
  esac
done

PYPROJECT_VERSION=$(poetry version -s)
PROJECT_NAME=$(grep -oP '^name\s*=\s*"\K[^"]+' pyproject.toml)
DESCRIPTION=$(grep -oP '^description\s*=\s*"\K[^"]+' pyproject.toml || echo "")
LICENSE=$(grep -oP '^license\s*=\s*"\K[^"]+' pyproject.toml || echo "Unlicense")
SOURCE_URL=$(git ls-remote --get-url origin 2>/dev/null || echo "")
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")

# Full OCI Labels
BUILD_LABELS="\
--label org.opencontainers.image.title=\"${PROJECT_NAME}\" \
--label org.opencontainers.image.description=\"${DESCRIPTION}\" \
--label org.opencontainers.image.version=\"${PYPROJECT_VERSION}\" \
--label org.opencontainers.image.created=\"$(date -Iseconds)\" \
--label org.opencontainers.image.source=\"${SOURCE_URL}\" \
--label org.opencontainers.image.revision=\"${GIT_COMMIT}\" \
--label org.opencontainers.image.licenses=\"${LICENSE}\""

# Export for compose.yaml interpolation
export USERNAME TAG
podman-compose build --podman-build-args="${BUILD_LABELS}"
podman-compose push

