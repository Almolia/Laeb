import json
import logging
import time
import uuid
from datetime import datetime, timezone

import pika
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.infrastructure.models import OutboxMessage, ProcessedEvent
from shared_kernel.config import get_settings
from shared_kernel.context import correlation_id
from shared_kernel.db import session_factory

log = logging.getLogger(__name__)


def enqueue(session, event_name: str, payload: dict, producer: str = "wallet") -> None:
    session.add(
        OutboxMessage(
            event_name=event_name,
            payload=payload,
            producer=producer,
            correlation_id=correlation_id.get(),
        )
    )


def event_envelope(row: OutboxMessage) -> dict:
    return {
        "eventId": str(row.id),
        "eventName": row.event_name,
        "occurredAt": row.created_at.astimezone(timezone.utc).isoformat(),
        "correlationId": row.correlation_id,
        "producer": row.producer,
        "version": 1,
        "payload": row.payload,
    }


def _connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))


def declare_topology(channel) -> None:
    settings = get_settings()
    channel.exchange_declare(
        exchange=settings.event_exchange, exchange_type="topic", durable=True
    )
    channel.queue_declare(queue="q.wallet", durable=True)
    channel.queue_bind(
        queue="q.wallet", exchange=settings.event_exchange, routing_key="trade.matched"
    )
    channel.basic_qos(prefetch_count=10)


def publish_pending_once() -> int:
    connection = _connection()
    try:
        channel = connection.channel()
        declare_topology(channel)
        channel.confirm_delivery()
        with session_factory()() as session:
            rows = session.execute(
                select(OutboxMessage)
                .where(OutboxMessage.published_at.is_(None))
                .order_by(OutboxMessage.created_at)
                .limit(100)
                .with_for_update(skip_locked=True)
            ).scalars().all()
            published = 0
            for row in rows:
                channel.basic_publish(
                    exchange=get_settings().event_exchange,
                    routing_key=row.event_name,
                    body=json.dumps(event_envelope(row), default=str).encode(),
                    properties=pika.BasicProperties(
                        content_type="application/json", delivery_mode=2
                    ),
                    mandatory=True,
                )
                row.published_at = datetime.now(timezone.utc)
                published += 1
            session.commit()
            return published
    finally:
        connection.close()


def claim_event(session, event_id: uuid.UUID) -> bool:
    result = session.execute(
        insert(ProcessedEvent)
        .values(event_id=event_id)
        .on_conflict_do_nothing(index_elements=["event_id"])
    )
    return result.rowcount == 1


def run_publisher() -> None:
    settings = get_settings()
    while True:
        try:
            count = publish_pending_once()
            if count:
                log.info("published outbox messages=%s", count)
        except Exception:
            log.exception("outbox publisher cycle failed")
        time.sleep(settings.outbox_poll_seconds)
