#!/usr/bin/env bash
set -euo pipefail

BASE="${GATEWAY_URL:-http://localhost:8000}"
SERVICES=(identity profile catalog order wallet review trading forum festival media notification)
failed=0

for s in "${SERVICES[@]}"; do
  url="$BASE/api/v1/$s/health"
  code=$(curl -s -o /tmp/laeb-smoke.json -w "%{http_code}" "$url" || echo "000")
  if [[ "$code" == "200" ]]; then
    echo "OK  $url"
  else
    echo "FAIL $url (HTTP $code)"
    failed=1
  fi
done

if [[ "$failed" -ne 0 ]]; then
  echo "smoke failed"
  exit 1
fi
echo "smoke passed: ${#SERVICES[@]} services"
