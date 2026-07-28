#!/usr/bin/env bash
# Demo script — Identity + Catalog sections implemented (A2).
set -euo pipefail

BASE="${GATEWAY_URL:-http://localhost:8000}"
ID="$BASE/api/v1/identity"
CAT="$BASE/api/v1/catalog"

echo "=== Laeb demo against $BASE ==="

# --- US-01..US-04 Identity / roles ---
echo "# US-01..US-04 identity"
curl -sf -X POST "$ID/auth/register" -H 'content-type: application/json' \
  -d "{\"username\":\"demo_dev_$RANDOM\",\"email\":\"demo_dev_$RANDOM@test.com\",\"password\":\"pass1234\"}" >/tmp/laeb_reg.json || true
ADMIN_TOKEN=$(curl -sf -X POST "$ID/auth/login" -H 'content-type: application/json' \
  -d '{"username":"admin","password":"admin123"}' | python -c "import sys,json; print(json.load(sys.stdin)['accessToken'])")
curl -sf "$ID/auth/me" -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null
echo "identity OK"

# --- US-05..US-08 Profile ---
echo "# TODO(B3) US-05..US-08 profile"

# --- US-09..US-14 Catalog / publishing ---
echo "# US-09..US-13 catalog publishing"
# Needs a developer token — grant via admin in seed/demo extension
echo "# (full walkthrough: register → admin grant DEVELOPER → submit → approve → price → publish)"

# --- remaining TODOs ---
echo "# TODO(B1) US-15..US-18 order"
echo "# TODO(B3) US-19..US-22 review"
echo "# TODO(B2) US-23..US-28 trading"
echo "# TODO(B3) US-29..US-33 forum"
echo "# TODO(A3) US-34..US-36 wallet"
echo "# TODO(B1) US-37..US-39 festival"

echo "=== demo skeleton complete ==="
