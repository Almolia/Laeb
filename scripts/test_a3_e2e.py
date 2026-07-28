"""Executable A3 acceptance test against the Docker Compose stack."""

import json
import os
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pika
import psycopg

BASE = os.getenv("WALLET_BASE_URL", "http://localhost:8005/api/v1/wallet")
DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL", "postgresql://wallet:wallet@localhost:5432/wallet"
)
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://guest:guest@localhost:5672/%2F")
JWT_SECRET = os.getenv("JWT_SECRET", "development-secret")


def token(user_id: uuid.UUID, roles: list[str]) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "username": f"test-{str(user_id)[:8]}",
            "roles": roles,
            "iat": now,
            "exp": now + timedelta(hours=1),
        },
        JWT_SECRET,
        algorithm="HS256",
    )


def expect(response: httpx.Response, status: int = 200) -> dict | list:
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


def wait_balance(client: httpx.Client, headers: dict, expected: int) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        value = expect(client.get(f"{BASE}/wallets/me", headers=headers))
        if value["balanceMinor"] == expected:
            return
        time.sleep(0.2)
    raise AssertionError(f"balance did not become {expected}")


def wait_event(channel, queue: str, trade_id: str) -> dict:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        method, _properties, body = channel.basic_get(queue=queue, auto_ack=True)
        if method:
            envelope = json.loads(body)
            if envelope["eventName"] == "trade.payment_settled":
                if envelope["payload"]["tradeId"] == trade_id:
                    return envelope["payload"]
        time.sleep(0.2)
    raise AssertionError(f"settlement event not received for {trade_id}")


def main() -> None:
    buyer, developer, seller, recipient = (
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
        uuid.uuid4(),
    )
    buyer_headers = {"Authorization": f"Bearer {token(buyer, ['BASE_USER'])}"}
    developer_headers = {"Authorization": f"Bearer {token(developer, ['DEVELOPER'])}"}
    seller_headers = {"Authorization": f"Bearer {token(seller, ['BASE_USER'])}"}
    recipient_headers = {"Authorization": f"Bearer {token(recipient, ['BASE_USER'])}"}
    admin_headers = {"Authorization": f"Bearer {token(uuid.uuid4(), ['ADMIN'])}"}

    with httpx.Client(timeout=10) as client:
        assert expect(client.get("http://localhost:8005/health"))["status"] == "ok"
        assert expect(client.get("http://localhost:8005/ready"))["status"] == "ready"
        assert client.get("http://localhost:8005/metrics").status_code == 200
        assert client.get(f"{BASE}/wallets/me").status_code == 401
        assert expect(client.get(f"{BASE}/wallets/me", headers=buyer_headers))["balanceMinor"] == 0

        credit_body = {
            "userId": str(buyer),
            "amountMinor": 500_000,
            "reason": "TEST_SEED",
            "refType": "TEST",
            "refId": str(uuid.uuid4()),
        }
        credit_key = str(uuid.uuid4())
        first_credit = expect(
            client.post(
                f"{BASE}/internal/credit",
                headers={"Idempotency-Key": credit_key},
                json=credit_body,
            )
        )
        replay_credit = expect(
            client.post(
                f"{BASE}/internal/credit",
                headers={"Idempotency-Key": credit_key},
                json=credit_body,
            )
        )
        assert first_credit == replay_credit
        changed = credit_body | {"amountMinor": 1}
        reused = expect(
            client.post(
                f"{BASE}/internal/credit",
                headers={"Idempotency-Key": credit_key},
                json=changed,
            ),
            409,
        )
        assert reused["error"]["code"] == "IDEMPOTENCY_KEY_REUSED"
        missing_key = expect(
            client.post(f"{BASE}/internal/credit", json=credit_body), 400
        )
        assert missing_key["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

        debit = expect(
            client.post(
                f"{BASE}/internal/debit",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json=credit_body | {"amountMinor": 100, "reason": "TEST_DEBIT"},
            )
        )
        assert debit["balanceMinor"] == 499_900
        restored = expect(
            client.post(
                f"{BASE}/internal/credit",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json=credit_body | {"amountMinor": 100, "reason": "TEST_RESTORE"},
            )
        )
        assert restored["balanceMinor"] == 500_000

        transferred = expect(
            client.post(
                f"{BASE}/internal/transfer",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={
                    "fromUserId": str(buyer),
                    "toUserId": str(recipient),
                    "amountMinor": 50,
                    "reason": "TEST_TRANSFER",
                    "refType": "TEST",
                    "refId": str(uuid.uuid4()),
                },
            )
        )
        assert transferred["txGroupId"]
        assert expect(client.get(f"{BASE}/wallets/me", headers=recipient_headers))["balanceMinor"] == 50
        expect(
            client.post(
                f"{BASE}/internal/transfer",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={
                    "fromUserId": str(recipient),
                    "toUserId": str(buyer),
                    "amountMinor": 50,
                    "reason": "TEST_TRANSFER_BACK",
                    "refType": "TEST",
                    "refId": str(uuid.uuid4()),
                },
            )
        )

        purchase_body = {
            "buyerId": str(buyer),
            "developerId": str(developer),
            "amountMinor": 500_000,
            "orderId": str(uuid.uuid4()),
        }
        purchase_key = str(uuid.uuid4())
        purchase = expect(
            client.post(
                f"{BASE}/internal/purchase-split",
                headers={"Idempotency-Key": purchase_key},
                json=purchase_body,
            )
        )
        purchase_replay = expect(
            client.post(
                f"{BASE}/internal/purchase-split",
                headers={"Idempotency-Key": purchase_key},
                json=purchase_body,
            )
        )
        assert purchase == purchase_replay
        assert purchase["buyerBalanceMinor"] == 0
        assert expect(client.get(f"{BASE}/wallets/me", headers=developer_headers))["balanceMinor"] == 350_000

        insufficient = expect(
            client.post(
                f"{BASE}/internal/purchase-split",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json=purchase_body | {"amountMinor": 1, "orderId": str(uuid.uuid4())},
            ),
            409,
        )
        assert insufficient["error"]["code"] == "INSUFFICIENT_FUNDS"

        zero = expect(
            client.post(
                f"{BASE}/internal/purchase-split",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json=purchase_body | {"amountMinor": 0, "orderId": str(uuid.uuid4())},
            )
        )
        assert zero["buyerBalanceMinor"] == 0

        reversal = expect(
            client.post(
                f"{BASE}/internal/reverse",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={"txGroupId": purchase["txGroupId"], "reason": "REFUND"},
            )
        )
        assert reversal["reversalTxGroupId"]
        wait_balance(client, buyer_headers, 500_000)
        second_reversal = expect(
            client.post(
                f"{BASE}/internal/reverse",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={"txGroupId": purchase["txGroupId"], "reason": "REFUND"},
            ),
            409,
        )
        assert second_reversal["error"]["code"] == "ALREADY_REVERSED"
        not_found = expect(
            client.post(
                f"{BASE}/internal/reverse",
                headers={"Idempotency-Key": str(uuid.uuid4())},
                json={"txGroupId": str(uuid.uuid4()), "reason": "REFUND"},
            ),
            404,
        )
        assert not_found["error"]["code"] == "TX_GROUP_NOT_FOUND"

        cards = expect(
            client.post(
                f"{BASE}/giftcards",
                headers=admin_headers,
                json={"amountMinor": 1200, "count": 1},
            ),
            201,
        )
        card_key = str(uuid.uuid4())
        card = expect(
            client.post(
                f"{BASE}/giftcards/redeem",
                headers=buyer_headers | {"Idempotency-Key": card_key},
                json={"code": cards["codes"][0]},
            )
        )
        assert card["amountMinor"] == 1200
        assert expect(
            client.post(
                f"{BASE}/giftcards/redeem",
                headers=buyer_headers | {"Idempotency-Key": card_key},
                json={"code": cards["codes"][0]},
            )
        ) == card
        used = expect(
            client.post(
                f"{BASE}/giftcards/redeem",
                headers=buyer_headers | {"Idempotency-Key": str(uuid.uuid4())},
                json={"code": cards["codes"][0]},
            ),
            409,
        )
        assert used["error"]["code"] == "GIFTCARD_ALREADY_REDEEMED"

        topup = expect(
            client.post(
                f"{BASE}/topups/initiate",
                headers=buyer_headers,
                json={"amountMinor": 800},
            )
        )
        assert topup["redirectUrl"].startswith("http://localhost:8020/")
        wait_balance(client, buyer_headers, 502_000)
        assert expect(client.get(f"{BASE}/wallets/me/ledger", headers=buyer_headers))

    connection = pika.BlockingConnection(pika.URLParameters(RABBITMQ_URL))
    channel = connection.channel()
    channel.exchange_declare(exchange="platform.events", exchange_type="topic", durable=True)
    queue = f"q.a3-e2e.{uuid.uuid4()}"
    channel.queue_declare(queue=queue, exclusive=True, auto_delete=True)
    channel.queue_bind(queue=queue, exchange="platform.events", routing_key="trade.payment_settled")

    success_trade = str(uuid.uuid4())
    success_event_id = str(uuid.uuid4())
    success_envelope = {
        "eventId": success_event_id,
        "eventName": "trade.matched",
        "occurredAt": datetime.now(timezone.utc).isoformat(),
        "correlationId": str(uuid.uuid4()),
        "producer": "a3-e2e",
        "version": 1,
        "payload": {
            "tradeId": success_trade,
            "itemId": str(uuid.uuid4()),
            "buyerId": str(buyer),
            "sellerId": str(seller),
            "priceMinor": 500,
            "quantity": 2,
        },
    }
    for _ in range(2):
        channel.basic_publish(
            exchange="platform.events",
            routing_key="trade.matched",
            body=json.dumps(success_envelope).encode(),
            properties=pika.BasicProperties(delivery_mode=2),
        )
    success_result = wait_event(channel, queue, success_trade)
    assert success_result == {"tradeId": success_trade, "ok": True, "reason": None}

    failed_trade = str(uuid.uuid4())
    failed_envelope = success_envelope | {
        "eventId": str(uuid.uuid4()),
        "payload": success_envelope["payload"] | {
            "tradeId": failed_trade,
            "priceMinor": 999_999_999,
        },
    }
    channel.basic_publish(
        exchange="platform.events",
        routing_key="trade.matched",
        body=json.dumps(failed_envelope).encode(),
        properties=pika.BasicProperties(delivery_mode=2),
    )
    failed_result = wait_event(channel, queue, failed_trade)
    assert failed_result["ok"] is False
    assert failed_result["reason"] == "INSUFFICIENT_FUNDS"
    connection.close()

    with psycopg.connect(DATABASE_URL) as database:
        unbalanced = database.execute(
            """
            SELECT tx_group_id FROM ledger_entries GROUP BY tx_group_id
            HAVING SUM(CASE WHEN direction='CREDIT' THEN amount_minor ELSE -amount_minor END) <> 0
            """
        ).fetchall()
        assert unbalanced == []
        seller_balance = database.execute(
            "SELECT balance_minor FROM accounts WHERE owner_type='USER' AND owner_id=%s",
            (seller,),
        ).fetchone()[0]
        assert seller_balance == 1000
        unpublished = database.execute(
            "SELECT count(*) FROM outbox WHERE published_at IS NULL"
        ).fetchone()[0]
        assert unpublished == 0

    for statement in (
        "UPDATE ledger_entries SET reason=reason WHERE id=(SELECT min(id) FROM ledger_entries)",
        "DELETE FROM ledger_entries WHERE id=(SELECT min(id) FROM ledger_entries)",
    ):
        with psycopg.connect(DATABASE_URL) as database:
            try:
                database.execute(statement)
            except psycopg.errors.RaiseException as exc:
                assert "append-only" in str(exc)
                database.rollback()
            else:
                raise AssertionError("append-only ledger accepted a mutation")

    print("A3 end-to-end acceptance: PASS")


if __name__ == "__main__":
    main()
