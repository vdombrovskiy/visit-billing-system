from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.contracts.events import VisitCompletedEvent
from app.modules.billing.consumers import visit_completed_consumer
from app.modules.billing.consumers.visit_completed_consumer import (
    VisitCompletedConsumer,
)
from app.modules.billing.models.billing_record import BillingRecord
from app.modules.billing.models.processed_event import ProcessedEvent


class FakeMessage:
    def __init__(self, body: bytes):
        self.body = body
        self.acked = False
        self.rejected = False
        self.nacked = False
        self.requeue = None

    async def ack(self):
        self.acked = True

    async def reject(self, requeue=False):
        self.rejected = True
        self.requeue = requeue

    async def nack(self, requeue=False):
        self.nacked = True
        self.requeue = requeue


def make_event(
    start_date_time=None,
    end_date_time=None,
):
    return VisitCompletedEvent(
        event_id=uuid4(),
        event_type="VisitCompleted",
        occurred_at=datetime.now(UTC),
        visit_id=uuid4(),
        start_date_time=start_date_time
        or datetime(2026, 11, 14, 10, 0, tzinfo=UTC),
        end_date_time=end_date_time
        or datetime(2026, 11, 14, 11, 30, tzinfo=UTC),
        rate=Decimal("80.00"),
    )


@pytest.fixture
def consumer(billing_session_factory, monkeypatch):
    monkeypatch.setattr(
        visit_completed_consumer,
        "async_session_factory",
        billing_session_factory,
    )
    return VisitCompletedConsumer()


@pytest.mark.asyncio
async def test_successfully_processes_message_and_acknowledges(
    consumer,
    billing_session_factory,
):
    event = make_event()
    message = FakeMessage(event.model_dump_json().encode())

    await consumer.handle_message(message)

    assert message.acked is True
    assert message.rejected is False
    assert message.nacked is False

    async with billing_session_factory() as session:
        billing_record = await session.scalar(
            select(BillingRecord).where(
                BillingRecord.visit_id == event.visit_id
            )
        )
        processed_event = await session.get(
            ProcessedEvent,
            event.event_id,
        )

        assert billing_record is not None
        assert billing_record.amount == Decimal("120.00")
        assert processed_event is not None


@pytest.mark.asyncio
async def test_duplicate_message_is_acknowledged_without_duplicate_billing(
    consumer,
    billing_session_factory,
):
    event = make_event()
    message = FakeMessage(event.model_dump_json().encode())

    await consumer.handle_message(message)
    await consumer.handle_message(message)

    assert message.acked is True
    assert message.rejected is False
    assert message.nacked is False

    async with billing_session_factory() as session:
        billing_count = await session.scalar(
            select(func.count())
            .select_from(BillingRecord)
            .where(BillingRecord.visit_id == event.visit_id)
        )

        processed_count = await session.scalar(
            select(func.count())
            .select_from(ProcessedEvent)
            .where(ProcessedEvent.event_id == event.event_id)
        )

        assert billing_count == 1
        assert processed_count == 1


@pytest.mark.asyncio
async def test_invalid_message_is_rejected_without_requeue(
    consumer,
):
    message = FakeMessage(b"this is not valid JSON")

    await consumer.handle_message(message)

    assert message.acked is False
    assert message.rejected is True
    assert message.requeue is False
    assert message.nacked is False


@pytest.mark.asyncio
async def test_processing_failure_rolls_back_and_requests_redelivery(
    consumer,
    billing_session_factory,
):
    event = make_event(
        start_date_time=datetime(2026, 11, 14, 11, 0, tzinfo=UTC),
        end_date_time=datetime(2026, 11, 14, 10, 0, tzinfo=UTC),
    )
    message = FakeMessage(event.model_dump_json().encode())

    await consumer.handle_message(message)

    assert message.acked is False
    assert message.rejected is False
    assert message.nacked is True
    assert message.requeue is True

    async with billing_session_factory() as session:
        processed_event = await session.get(
            ProcessedEvent,
            event.event_id,
        )

        billing_count = await session.scalar(
            select(func.count())
            .select_from(BillingRecord)
            .where(BillingRecord.visit_id == event.visit_id)
        )

        assert processed_event is None
        assert billing_count == 0
