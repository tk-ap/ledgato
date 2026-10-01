#!/usr/bin/env bash
# Static-first sandbox build for here.now (see .agent-os/deployment.yaml).
# Production still builds through vercel.json and is not affected.
set -euo pipefail
cd "$(dirname "$0")/../web"
npm install
npm run test
npm run build
echo "Static sandbox build ready: web/dist (publish with --spa)"
