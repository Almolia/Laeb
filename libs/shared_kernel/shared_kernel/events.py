import json
import logging
import uuid
from datetime import datetime, timezone

import pika
from pydantic import BaseModel, Field

from .config import settings
from .logging import correlation_id

log = logging.getLogger(__name__)


class EventEnvelope(BaseModel):
    eventId: str = Field(default_factory=lambda: str(uuid.uuid4()))
    eventName: str
    occurredAt: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    correlationId: str = Field(default_factory=lambda: correlation_id.get())
    producer: str = ""
    version: int = 1
    payload: dict


def _connection():
    return pika.BlockingConnection(pika.URLParameters(settings.rabbitmq_url))


def declare_topology(channel) -> None:
    channel.exchange_declare(
        exchange=settings.event_exchange,
        exchange_type="topic",
        durable=True,
    )


def publish(envelope: EventEnvelope) -> None:
    conn = _connection()
    try:
        ch = conn.channel()
        declare_topology(ch)
        ch.basic_publish(
            exchange=settings.event_exchange,
            routing_key=envelope.eventName,
            body=envelope.model_dump_json().encode(),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json",
            ),
        )
    finally:
        conn.close()


def consume(queue: str, routing_keys: list[str], handler) -> None:
    """Blocking consumer loop. Call from worker.py. handler(EventEnvelope) -> None.
    Raising from the handler nacks WITHOUT requeue -> message is dropped after logging.
    Idempotency is the handler's job (see inbox.py)."""
    conn = _connection()
    ch = conn.channel()
    declare_topology(ch)
    ch.queue_declare(queue=queue, durable=True)
    for rk in routing_keys:
        ch.queue_bind(queue=queue, exchange=settings.event_exchange, routing_key=rk)
    ch.basic_qos(prefetch_count=10)

    def _on_message(chan, method, _props, body):
        try:
            env = EventEnvelope(**json.loads(body))
            correlation_id.set(env.correlationId)
            handler(env)
            chan.basic_ack(method.delivery_tag)
        except Exception:
            log.exception("event handling failed; dropping message")
            chan.basic_nack(method.delivery_tag, requeue=False)

    ch.basic_consume(queue=queue, on_message_callback=_on_message)
    log.info("consuming queue=%s keys=%s", queue, routing_keys)
    ch.start_consuming()
