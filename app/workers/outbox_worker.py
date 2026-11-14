import asyncio
import logging

from app.core.database import async_session_factory
from app.infrastructure.messaging import RabbitMQ
from app.modules.visits.services.outbox_publisher import OutboxPublisher

logger = logging.getLogger(__name__)

POLL_INTERVAL_SECONDS = 2


async def run_worker():
    rabbitmq = RabbitMQ()

    try:
        await rabbitmq.connect()
        logger.info("Outbox worker connected to RabbitMQ")

        publisher = OutboxPublisher(
            session_factory=async_session_factory,
            rabbitmq=rabbitmq,
        )

        while True:
            try:
                published_count = await publisher.publish_pending()

                if published_count:
                    logger.info(
                        "Published %s outbox events",
                        published_count,
                    )

            except asyncio.CancelledError:
                raise

            except Exception:
                logger.exception("Outbox publishing cycle failed")

            await asyncio.sleep(POLL_INTERVAL_SECONDS)

    finally:
        await rabbitmq.close()
        logger.info("Outbox worker stopped")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_worker())
