import asyncio
import logging

from pydantic import ValidationError

from app.core.database import async_session_factory
from app.contracts.events import VisitCompletedEvent
from app.infrastructure.messaging import RabbitMQ
from app.modules.billing.services.billing_service import BillingService

logger = logging.getLogger(__name__)


class VisitCompletedConsumer:
    def __init__(self):
        self.rabbitmq = RabbitMQ()

    async def handle_message(self, message):
        try:
            event = VisitCompletedEvent.model_validate_json(message.body)

            if event.event_type != "VisitCompleted":
                raise ValueError(
                    f"Unsupported event type: {event.event_type}"
                )

        except (ValidationError, ValueError):
            logger.exception("Invalid VisitCompleted message")
            await message.reject(requeue=False)
            return

        try:
            async with async_session_factory() as session:
                async with session.begin():
                    processed = await BillingService.process_visit_completed(
                        session,
                        event,
                    )

            await message.ack()

            if processed:
                logger.info(
                    "Processed VisitCompleted event %s for visit %s",
                    event.event_id,
                    event.visit_id,
                )
            else:
                logger.info(
                    "Ignoring duplicate event %s",
                    event.event_id,
                )

        except Exception:
            logger.exception(
                "Failed to process VisitCompleted event %s",
                event.event_id,
            )
            await message.nack(requeue=True)

    async def run_forever(self):
        await self.rabbitmq.connect()

        if self.rabbitmq.channel is None or self.rabbitmq.queue is None:
            raise RuntimeError("RabbitMQ connection is not initialized")

        await self.rabbitmq.channel.set_qos(prefetch_count=10)

        consumer_tag = await self.rabbitmq.queue.consume(
            self.handle_message,
        )

        logger.info("VisitCompleted consumer started")

        try:
            await asyncio.Future()
        finally:
            await self.rabbitmq.queue.cancel(consumer_tag)
            await self.rabbitmq.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(VisitCompletedConsumer().run_forever())
