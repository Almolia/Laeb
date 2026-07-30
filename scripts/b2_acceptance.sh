#!/usr/bin/env bash
# B2 acceptance helpers. Tokens and IDs are intentionally supplied by the caller.
set -euo pipefail

BASE="${GATEWAY_URL:-http://localhost:8000}"
TRADING="$BASE/api/v1/trading"
FESTIVAL="$BASE/api/v1/festival"
CATALOG="$BASE/api/v1/catalog"

: "${ADMIN_TOKEN:?set ADMIN_TOKEN}"
: "${DEVELOPER_TOKEN:?set DEVELOPER_TOKEN}"
: "${BUYER_TOKEN:?set BUYER_TOKEN}"
: "${SELLER_TOKEN:?set SELLER_TOKEN}"
: "${GAME_ID:?set GAME_ID}"

json_value() {
  python -c "import json,sys; print(json.load(sys.stdin)['$1'])"
}

echo "# Create item (US-23)"
ITEM_ID=$(curl -sf -X POST "$TRADING/games/$GAME_ID/items" \
  -H "Authorization: Bearer $DEVELOPER_TOKEN" \
  -H 'content-type: application/json' \
  -d '{"name":"B2 Demo Item","description":"marketplace acceptance"}' | json_value itemId)
echo "ITEM_ID=$ITEM_ID"

echo "# Grant seller inventory (US-24)"
: "${SELLER_ID:?set SELLER_ID}"
curl -sf -X POST "$TRADING/items/$ITEM_ID/grants" \
  -H "Authorization: Bearer $DEVELOPER_TOKEN" \
  -H 'content-type: application/json' \
  -d "{\"recipientMode\":\"EXPLICIT\",\"userIds\":[\"$SELLER_ID\"],\"quantityMode\":\"FIXED\",\"quantity\":2}" >/dev/null

echo "# Place seller at 100 and buyer at 150 (US-25/26)"
curl -sf -X POST "$TRADING/orders/sell" \
  -H "Authorization: Bearer $SELLER_TOKEN" -H 'content-type: application/json' \
  -d "{\"itemId\":\"$ITEM_ID\",\"priceMinor\":100,\"quantity\":1}" >/dev/null
curl -sf -X POST "$TRADING/orders/buy" \
  -H "Authorization: Bearer $BUYER_TOKEN" -H 'content-type: application/json' \
  -d "{\"itemId\":\"$ITEM_ID\",\"priceMinor\":150,\"quantity\":1}" >/dev/null

echo "# Trigger cycle without waiting five minutes (US-27)"
curl -sf -X POST "$TRADING/internal/run-match-cycle" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
echo

echo "# Show seller-price trade and cycle history"
curl -sf "$TRADING/trades?itemId=$ITEM_ID" -H "Authorization: Bearer $BUYER_TOKEN"
echo
curl -sf "$TRADING/match-cycles" -H "Authorization: Bearer $BUYER_TOKEN"
echo

echo "# Optional festival round trip; set SUPPORT_TOKEN and STARTS_AT/ENDS_AT"
if [[ -n "${SUPPORT_TOKEN:-}" && -n "${STARTS_AT:-}" && -n "${ENDS_AT:-}" ]]; then
  FESTIVAL_ID=$(curl -sf -X POST "$FESTIVAL/festivals" \
    -H "Authorization: Bearer $SUPPORT_TOKEN" -H 'content-type: application/json' \
    -d "{\"name\":\"B2 Demo Festival\",\"startsAt\":\"$STARTS_AT\",\"endsAt\":\"$ENDS_AT\"}" | json_value festivalId)
  curl -sf -X POST "$FESTIVAL/festivals/$FESTIVAL_ID/entries" \
    -H "Authorization: Bearer $SUPPORT_TOKEN" -H 'content-type: application/json' \
    -d "{\"gameId\":\"$GAME_ID\",\"discountPercent\":30}" >/dev/null
  curl -sf -X POST "$FESTIVAL/festivals/$FESTIVAL_ID/entries/$GAME_ID/approve" \
    -H "Authorization: Bearer $DEVELOPER_TOKEN" >/dev/null
  curl -sf -X POST "$FESTIVAL/internal/festivals/$FESTIVAL_ID/activate" \
    -H "Authorization: Bearer $ADMIN_TOKEN" >/dev/null
  sleep 3
  curl -sf "$CATALOG/games/$GAME_ID/effective-price"
  echo
fi
