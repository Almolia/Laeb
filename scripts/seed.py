"""Idempotent seed for Identity + Catalog (A2)."""

from __future__ import annotations

import os
import sys

import httpx

BASE = os.environ.get("GATEWAY_URL", "http://localhost:8000")


def main() -> int:
    print(f"seeding against {BASE}")
    with httpx.Client(base_url=BASE, timeout=30.0) as client:
        for svc in ("identity", "catalog"):
            r = client.get(f"/api/v1/{svc}/health")
            print(f"  {svc}: {r.status_code}")
            r.raise_for_status()

        admin = client.post(
            "/api/v1/identity/auth/login",
            json={"username": "admin", "password": "admin123"},
        )
        admin.raise_for_status()
        ah = {"Authorization": f"Bearer {admin.json()['accessToken']}"}

        def ensure_user(username: str, email: str, password: str) -> str:
            reg = client.post(
                "/api/v1/identity/auth/register",
                json={"username": username, "email": email, "password": password},
            )
            if reg.status_code == 201:
                return reg.json()["userId"]
            login = client.post(
                "/api/v1/identity/auth/login",
                json={"username": username, "password": password},
            )
            login.raise_for_status()
            return login.json()["userId"]

        def grant(uid: str, role: str) -> None:
            r = client.post(
                f"/api/v1/identity/users/{uid}/roles",
                headers=ah,
                json={"role": role},
            )
            if r.status_code not in (200, 409):
                r.raise_for_status()

        def login(username: str, password: str) -> dict:
            r = client.post(
                "/api/v1/identity/auth/login",
                json={"username": username, "password": password},
            )
            r.raise_for_status()
            return r.json()

        dev_id = ensure_user("dev1", "dev1@test.com", "pass1234")
        ensure_user("dev2", "dev2@test.com", "pass1234")
        sup_id = ensure_user("support1", "support1@test.com", "pass1234")
        for i in range(1, 5):
            ensure_user(f"user{i}", f"user{i}@test.com", "pass1234")

        grant(dev_id, "DEVELOPER")
        grant(ensure_user("dev2", "dev2@test.com", "pass1234"), "DEVELOPER")
        grant(sup_id, "SUPPORT")

        dev = login("dev1", "pass1234")
        sup = login("support1", "pass1234")
        dh = {"Authorization": f"Bearer {dev['accessToken']}"}
        sh = {"Authorization": f"Bearer {sup['accessToken']}"}

        games = client.get("/api/v1/catalog/games", params={"q": "Space Rogue"})
        if games.status_code == 200 and games.json().get("total", 0) > 0:
            print("Space Rogue already published")
        else:
            game = client.post(
                "/api/v1/catalog/games",
                headers=dh,
                json={
                    "title": "Space Rogue",
                    "description": "a roguelike adventure",
                    "genre": "action",
                },
            )
            game.raise_for_status()
            gid = game.json()["gameId"]
            client.post(f"/api/v1/catalog/games/{gid}/review/start", headers=sh).raise_for_status()
            client.post(
                f"/api/v1/catalog/games/{gid}/review/approve",
                headers=sh,
                json={"suggestedPriceMinor": 500000},
            ).raise_for_status()
            client.post(
                f"/api/v1/catalog/games/{gid}/price",
                headers=dh,
                json={"priceMinor": 450000},
            ).raise_for_status()
            client.post(
                f"/api/v1/catalog/games/{gid}/publish", headers=sh
            ).raise_for_status()
            print(f"published game {gid}")

        # TODO(B2): items / TODO(B3): forum

    print("seed OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
