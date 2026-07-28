#!/usr/bin/env bash
# Demo script skeleton — one section per user-story group.
# Wave A implements Identity/Catalog/Wallet sections; Wave B fills the rest.
set -euo pipefail

BASE="${GATEWAY_URL:-http://localhost:8000}"
echo "=== Laeb demo against $BASE ==="

# --- US-01..US-04 Identity / roles ---
# TODO(A2): register, login, role request, admin grant
echo "# TODO(A2) US-01..US-04 identity"

# --- US-05..US-08 Profile ---
# TODO(B3): profile, purchased games projection, top posts, presence
echo "# TODO(B3) US-05..US-08 profile"

# --- US-09..US-14 Catalog / publishing / revenue split ---
# TODO(A2): submit, review, price negotiate, publish
echo "# TODO(A2) US-09..US-14 catalog publishing"

# --- US-15..US-18 Order purchase / gift / refund ---
# TODO(B1): purchase, gift + 0.2% message, 12h refund
echo "# TODO(B1) US-15..US-18 order"

# --- US-19..US-22 Reviews ---
# TODO(B3): owner-only review, reactions
echo "# TODO(B3) US-19..US-22 review"

# --- US-23..US-28 Trading ---
# TODO(B2): items, grant, buy/sell orders, 5-min match, settle
echo "# TODO(B2) US-23..US-28 trading"

# --- US-29..US-33 Forum ---
# TODO(B3): posts, comments, emoji, search
echo "# TODO(B3) US-29..US-33 forum"

# --- US-34..US-36 Wallet ---
# TODO(A3): top-up via mock-psp, gift card, refund ledger reverse
echo "# TODO(A3) US-34..US-36 wallet"

# --- US-37..US-39 Festival ---
# TODO(B1): create festival, developer confirm, discounted buy
echo "# TODO(B1) US-37..US-39 festival"

echo "=== demo skeleton complete (fill TODOs in Wave B) ==="
