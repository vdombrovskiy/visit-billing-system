
from typing import TYPE_CHECKING

import aio_pika
from aio_pika import ExchangeType

from app.core.config import settings

if TYPE_CHECKING:
    from aio_pika import Channel, Exchange, Queue, RobustConnection


class RabbitMQ:
    EXCHANGE_NAME = "visit.events"
    QUEUE_NAME = "billing.visit-completed"
    ROUTING_KEY = "visit.completed"

    def __init__(self) -> None:
        self.connection: RobustConnection | None = None
        self.channel: Channel | None = None
        self.exchange: Exchange | None = None
        self.queue: Queue | None = None

    async def connect(self) -> None:
        if self.connection and not self.connection.is_closed:
            return

        self.connection = await aio_pika.connect_robust(
            settings.rabbitmq_url,
        )

        self.channel = await self.connection.channel(
            publisher_confirms=True,
            on_return_raises=True,
        )

        self.exchange = await self.channel.declare_exchange(
            self.EXCHANGE_NAME,
            ExchangeType.TOPIC,
            durable=True,
        )

        self.queue = await self.channel.declare_queue(
            self.QUEUE_NAME,
            durable=True,
        )

        await self.queue.bind(
            self.exchange,
            routing_key=self.ROUTING_KEY,
        )

    async def close(self):
        if self.connection and not self.connection.is_closed:
            await self.connection.close()

        self.connection = None
        self.channel = None
        self.exchange = None
        self.queue = None
