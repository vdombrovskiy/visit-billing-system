
import json
from datetime import UTC, datetime

import aio_pika
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.infrastructure.messaging import RabbitMQ
from app.modules.visits.models.outbox_event import OutboxEvent


class OutboxPublisher:
    BATCH_SIZE = 100

    ROUTING_KEYS = {
        "VisitCompleted": RabbitMQ.ROUTING_KEY,
    }

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        rabbitmq: RabbitMQ,
    ):
        self.session_factory = session_factory
        self.rabbitmq = rabbitmq

    async def publish_pending(self) -> int:
        if self.rabbitmq.exchange is None:
            raise RuntimeError("RabbitMQ is not connected")

        published_count = 0

        async with self.session_factory() as session:
            async with session.begin():
                result = await session.execute(
                    select(OutboxEvent)
                    .where(OutboxEvent.published_at.is_(None))
                    .order_by(OutboxEvent.created_at)
                    .limit(self.BATCH_SIZE)
                    .with_for_update(skip_locked=True)
                )

                events = result.scalars().all()

                for event in events:
                    try:
                        routing_key = self.ROUTING_KEYS[event.event_type]

                        message = aio_pika.Message(
                            body=json.dumps(event.payload).encode("utf-8"),
                            content_type="application/json",
                            message_id=str(event.id),
                            type=event.event_type,
                            delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                        )

                        await self.rabbitmq.exchange.publish(
                            message,
                            routing_key=routing_key,
                            mandatory=True,
                        )

                    except Exception as exc:
                        event.attempts += 1
                        event.last_error = str(exc)[:2000]
                        continue

                    event.published_at = datetime.now(UTC)
                    event.attempts += 1
                    event.last_error = None
                    published_count += 1

        return published_count
