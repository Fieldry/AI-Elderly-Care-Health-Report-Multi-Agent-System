#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

exec python -m unittest \
  tests.api_flows.test_elderly_api_flow \
  tests.api_flows.test_family_api_flow \
  tests.api_flows.test_doctor_api_flow
