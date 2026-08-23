#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m compileall -q shared services tools tests
python3 -m unittest discover -s tests -v
python3 tools/shadow_e2e.py
python3 tools/http_e2e.py
python3 tools/load_test.py
python3 tools/dr_drill.py
python3 tools/compliance_gate.py --mode source
python3 spec/tools/validate_package.py
python3 tools/generate_source_sbom.py
if python3 tools/compliance_gate.py --mode distribution; then
  echo "Distribution gate passed. Confirm signed attestation before publishing."
else
  echo "Distribution remains blocked; this is expected until all external evidence exists."
fi
