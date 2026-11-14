import json
import uuid

import pytest
from sqlalchemy import select

from app.infrastructure.messaging import RabbitMQ
from app.modules.visits.models.outbox_event import OutboxEvent
from app.modules.visits.services.outbox_publisher import OutboxPublisher


class FakeExchange:
    def __init__(self):
        self.messages = []
        self.should_fail = False

    async def publish(self, message, routing_key, mandatory=False):
        if self.should_fail:
            raise RuntimeError("RabbitMQ is unavailable")

        self.messages.append(
            {
                "message": message,
                "routing_key": routing_key,
                "mandatory": mandatory,
            }
        )


class FakeRabbitMQ:
    def __init__(self):
        self.exchange = FakeExchange()


async def create_outbox_event(session):
    event = OutboxEvent(
        event_type="VisitCompleted",
        aggregate_id=uuid.uuid4(),
        payload={
            "event_id": str(uuid.uuid4()),
            "event_type": "VisitCompleted",
            "visit_id": str(uuid.uuid4()),
        },
    )

    session.add(event)
    await session.commit()
    return event.id


@pytest.mark.asyncio
async def test_publish_pending_marks_event_as_published(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        event_id = await create_outbox_event(session)

    rabbitmq = FakeRabbitMQ()
    publisher = OutboxPublisher(
        session_factory=visits_session_factory,
        rabbitmq=rabbitmq,
    )

    published_count = await publisher.publish_pending()

    assert published_count == 1
    assert len(rabbitmq.exchange.messages) == 1

    published_message = rabbitmq.exchange.messages[0]

    assert published_message["routing_key"] == RabbitMQ.ROUTING_KEY
    assert published_message["mandatory"] is True

    message = published_message["message"]
    assert message.message_id == str(event_id)
    assert message.type == "VisitCompleted"
    assert json.loads(message.body)["event_type"] == "VisitCompleted"

    async with visits_session_factory() as session:
        event = await session.get(OutboxEvent, event_id)

        assert event.published_at is not None
        assert event.attempts == 1
        assert event.last_error is None


@pytest.mark.asyncio
async def test_failed_publish_keeps_event_unpublished(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        event_id = await create_outbox_event(session)

    rabbitmq = FakeRabbitMQ()
    rabbitmq.exchange.should_fail = True

    publisher = OutboxPublisher(
        session_factory=visits_session_factory,
        rabbitmq=rabbitmq,
    )

    published_count = await publisher.publish_pending()

    assert published_count == 0

    async with visits_session_factory() as session:
        event = await session.get(OutboxEvent, event_id)

        assert event.published_at is None
        assert event.attempts == 1
        assert "RabbitMQ is unavailable" in event.last_error


@pytest.mark.asyncio
async def test_failed_event_can_be_published_on_retry(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        event_id = await create_outbox_event(session)

    rabbitmq = FakeRabbitMQ()
    rabbitmq.exchange.should_fail = True

    publisher = OutboxPublisher(
        session_factory=visits_session_factory,
        rabbitmq=rabbitmq,
    )

    assert await publisher.publish_pending() == 0

    rabbitmq.exchange.should_fail = False

    assert await publisher.publish_pending() == 1

    async with visits_session_factory() as session:
        event = await session.get(OutboxEvent, event_id)

        assert event.published_at is not None
        assert event.attempts == 2
        assert event.last_error is None

    assert len(rabbitmq.exchange.messages) == 1
