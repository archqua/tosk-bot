#!/bin/bash
set -euo pipefail 

# Default values
TAG=${TAG:-latest}
USERNAME=""

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

if [ -z "$USERNAME" ]; then
  echo "Error: username required. Usage: ./release.sh -u username [-t tag]" >&2
  exit 1
fi

# labels
TITLE="$(grep -oP '^name\s*=\s*"\K[^"]+' pyproject.toml)"
VERSION="$(poetry version -s)"
DESCRIPTION="$(grep -oP '^description\s*=\s*"\K[^"]+' pyproject.toml || echo "")"
LICENSE="$(grep -oP '^license\s*=\s*"\K[^"]+' pyproject.toml || echo "Unlicense")"
SOURCE="$(git ls-remote --get-url origin 2>/dev/null || echo "")"
REVISION="$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")"
CREATED="$(date -Iseconds)"

# Export for compose.yaml interpolation
export USERNAME TAG
export TITLE VERSION DESCRIPTION LICENSE SOURCE REVISION CREATED
podman-compose build --build-args="\"${BUILD_LABELS}\""
podman-compose push

