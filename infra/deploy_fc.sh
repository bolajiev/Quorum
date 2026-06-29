#!/usr/bin/env bash
# Deploy the sandbox Function Compute function via Serverless Devs.
# Prereqs: `npm install -g @serverless-devs/s` and `s config add`
# Usage: bash infra/deploy_fc.sh
set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel)"

echo "==> Deploying sandbox function to Alibaba Cloud Function Compute"
cd "$REPO_ROOT/sandbox_function"
s deploy --use-local -y

echo "==> Getting function endpoint"
s info 2>/dev/null | grep -E "(endpoint|url|http)" || true

echo "==> Done. Set FC_ENDPOINT and FC_FUNCTION_NAME in .env to use FC sandbox."
