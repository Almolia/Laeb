#!/usr/bin/env bash
# A2 acceptance — Identity login + Catalog publish walkthrough
set -euo pipefail
BASE="${GATEWAY_URL:-http://localhost:8000}"
ID="$BASE/api/v1/identity"
CAT="$BASE/api/v1/catalog"

echo "register + admin login"
curl -sf -X POST "$ID/auth/register" -H 'content-type: application/json' \
  -d "{\"username\":\"a2dev_$RANDOM\",\"email\":\"a2dev_$RANDOM@test.com\",\"password\":\"pass1234\"}" | tee /tmp/a2_reg.json
ADMIN=$(curl -sf -X POST "$ID/auth/login" -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin123"}')
TOKEN=$(echo "$ADMIN" | python -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")
curl -sf "$ID/auth/me" -H "Authorization: Bearer $TOKEN" >/dev/null
echo "Identity acceptance OK (login JWT works)"
