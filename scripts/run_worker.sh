#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
source .venv/bin/activate 2>/dev/null || true
set -a
source .env
set +a
python3 -m src.worker.worker_aws
