from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.contracts.events import VisitCompletedEvent
from app.modules.billing.models.billing_record import BillingRecord
from app.modules.billing.models.processed_event import ProcessedEvent
from app.modules.billing.services.billing_service import BillingService


def make_visit_completed_event():
    start = datetime(2026, 11, 14, 10, 0, tzinfo=UTC)
    end = datetime(2026, 11, 14, 11, 30, tzinfo=UTC)

    return VisitCompletedEvent(
        event_id=uuid4(),
        event_type="VisitCompleted",
        occurred_at=datetime.now(UTC),
        visit_id=uuid4(),
        start_date_time=start,
        end_date_time=end,
        rate=Decimal("80.00"),
    )


@pytest.mark.asyncio
async def test_process_visit_completed_creates_billing_record(
    billing_session_factory,
):
    event = make_visit_completed_event()

    async with billing_session_factory() as session:
        async with session.begin():
            processed = await BillingService.process_visit_completed(
                session,
                event,
            )

        assert processed is True

        result = await session.execute(
            select(BillingRecord).where(
                BillingRecord.visit_id == event.visit_id
            )
        )
        billing_record = result.scalar_one()

        assert billing_record.rate == Decimal("80.00")
        assert billing_record.duration_seconds == 5400
        assert billing_record.amount == Decimal("120.00")

        processed_event = await session.get(
            ProcessedEvent,
            event.event_id,
        )

        assert processed_event is not None


@pytest.mark.asyncio
async def test_duplicate_event_does_not_create_duplicate_billing_record(
    billing_session_factory,
):
    event = make_visit_completed_event()

    async with billing_session_factory() as session:
        async with session.begin():
            first_result = await BillingService.process_visit_completed(
                session,
                event,
            )

        async with session.begin():
            second_result = await BillingService.process_visit_completed(
                session,
                event,
            )

        assert first_result is True
        assert second_result is False

        result = await session.execute(
            select(func.count())
            .select_from(BillingRecord)
            .where(BillingRecord.visit_id == event.visit_id)
        )

        assert result.scalar_one() == 1

        result = await session.execute(
            select(func.count())
            .select_from(ProcessedEvent)
            .where(ProcessedEvent.event_id == event.event_id)
        )

        assert result.scalar_one() == 1


@pytest.mark.asyncio
async def test_failed_transaction_rolls_back_billing_and_processed_event(
    billing_session_factory,
):
    event = make_visit_completed_event()

    async with billing_session_factory() as session:
        with pytest.raises(RuntimeError):
            async with session.begin():
                await BillingService.process_visit_completed(
                    session,
                    event,
                )

                # Simulate a failure after the service has done its work.
                raise RuntimeError("Simulated failure")

        assert await session.get(ProcessedEvent, event.event_id) is None

        result = await session.execute(
            select(func.count())
            .select_from(BillingRecord)
            .where(BillingRecord.visit_id == event.visit_id)
        )

        assert result.scalar_one() == 0
