import logging
import threading

from app.application.trade import settle_trade
from shared_kernel.db import session_factory
from shared_kernel.events import consume
from shared_kernel.inbox import claim
from shared_kernel.outbox import run_publisher

log = logging.getLogger(__name__)


def handle_trade_matched(envelope) -> None:
    with session_factory()() as session:
        if not claim(session, envelope.eventId):
            return
        settle_trade(session, envelope.payload)
        session.commit()


def consume_events() -> None:
    consume("q.wallet", ["trade.matched"], handle_trade_matched)


def main() -> None:
    publisher = threading.Thread(target=run_publisher, daemon=True, name="outbox-publisher")
    publisher.start()
    consume_events()


if __name__ == "__main__":
    main()
