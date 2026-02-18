#!/bin/bash
set -e

# Sage CLI - Unified entrypoint for all Sage services

# Ensure Node.js 20 is used (required for Next.js 15 PWA)
export NVM_DIR="$HOME/.nvm"
if [ -s "$NVM_DIR/nvm.sh" ]; then
    \. "$NVM_DIR/nvm.sh"
    nvm use 20 > /dev/null 2>&1 || nvm install 20
fi
source .venv/bin/activate
python3 sage.py "$@"
