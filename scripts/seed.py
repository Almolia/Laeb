"""Idempotent seed skeleton. Safe to run repeatedly.

Creates via HTTP through the gateway (when services are implemented):
admin login → 2 developers, 1 support, 4 base users → wallets topped up →
3 games walked to Published → items defined and granted → forum posts.

Wave A writes users-and-games parts; Wave B extends marked TODOs.
"""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("GATEWAY_URL", "http://localhost:8000")


def main() -> int:
    print(f"seeding against {BASE}")
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        # Smoke that gateway routes exist
        for svc in (
            "identity",
            "profile",
            "catalog",
            "order",
            "wallet",
            "review",
            "trading",
            "forum",
            "festival",
            "media",
            "notification",
        ):
            r = client.get(f"/api/v1/{svc}/health")
            print(f"  {svc}: {r.status_code}")
            r.raise_for_status()

        # TODO(A2): create admin / developers / support / base users via identity
        # TODO(A3): top up wallets via wallet + mock-psp
        # TODO(A2): walk 3 games to Published via catalog
        # TODO(B2): define items and grant via trading
        # TODO(B3): create forum posts

    print("seed skeleton OK (domain creates still TODO)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
