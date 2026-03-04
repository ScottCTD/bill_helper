#!/usr/bin/env bash
# Setup shared env file for cross-worktree development.
#
# Usage:
#   ./scripts/setup_shared_env.sh          # copy local .env → shared location
#   ./scripts/setup_shared_env.sh --clean   # create a blank template from .env.example

set -euo pipefail

SHARED_DIR="$HOME/.config/bill-helper"
SHARED_ENV="$SHARED_DIR/.env"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$SHARED_DIR"

if [[ "${1:-}" == "--clean" ]]; then
    cp "$REPO_ROOT/.env.example" "$SHARED_ENV"
    echo "Created blank template at $SHARED_ENV — fill in your secrets."
elif [[ -f "$REPO_ROOT/.env" ]]; then
    cp "$REPO_ROOT/.env" "$SHARED_ENV"
    echo "Copied .env → $SHARED_ENV"
else
    cp "$REPO_ROOT/.env.example" "$SHARED_ENV"
    echo "No local .env found. Created template at $SHARED_ENV — fill in your secrets."
fi
