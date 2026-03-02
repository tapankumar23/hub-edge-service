#!/usr/bin/env bash
set -euo pipefail

echo "This script is deprecated. Use one of the following instead:" >&2
echo "  - POST /ingest with base64 payload (see docs/testcases.md)" >&2
echo "  - Run scripts/run_p0_e2e.sh for the full P0 journey" >&2
exit 1