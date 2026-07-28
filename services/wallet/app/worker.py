import json
import logging
import threading

import pika

from app.application.trade import settle_trade
from app.infrastructure.outbox import claim_event, declare_topology, run_publisher
from shared_kernel.config import get_settings
from shared_kernel.context import correlation_id
from shared_kernel.db import session_factory

log = logging.getLogger(__name__)


def consume_events() -> None:
    connection = pika.BlockingConnection(pika.URLParameters(get_settings().rabbitmq_url))
    channel = connection.channel()
    declare_topology(channel)

    def on_message(ch, method, _properties, body):
        envelope = json.loads(body)
        token = correlation_id.set(envelope.get("correlationId", "-"))
        try:
            with session_factory()() as session:
                event_id = envelope["eventId"]
                import uuid

                if not claim_event(session, uuid.UUID(event_id)):
                    session.commit()
                    ch.basic_ack(method.delivery_tag)
                    return
                if envelope["eventName"] == "trade.matched":
                    settle_trade(session, envelope["payload"])
                session.commit()
            ch.basic_ack(method.delivery_tag)
        except Exception:
            log.exception("event handling failed; message will be retried")
            ch.basic_nack(method.delivery_tag, requeue=True)
        finally:
            correlation_id.reset(token)

    channel.basic_consume(queue="q.wallet", on_message_callback=on_message)
    channel.start_consuming()


def main() -> None:
    publisher = threading.Thread(target=run_publisher, daemon=True, name="outbox-publisher")
    publisher.start()
    consume_events()


if __name__ == "__main__":
    main()
