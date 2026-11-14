import uuid

import asyncio

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.modules.visits.models.outbox_event import OutboxEvent
from app.modules.visits.models.visit import Visit, VisitStatus
from app.modules.visits.schemas.visit import VisitCreate
from app.modules.visits.services.exceptions import (
    VisitCannotBeCompletedError,
    VisitNotFoundError,
)
from app.modules.visits.services.visit_service import VisitService


def make_visit_data() -> VisitCreate:
    start = datetime.now(UTC) + timedelta(days=1)

    return VisitCreate(
        start_date_time=start,
        end_date_time=start + timedelta(hours=1, minutes=30),
        description="Consultation",
        rate=Decimal("80.00"),
    )


@pytest.mark.asyncio
async def test_create_visit( visits_session_factory):
    async with visits_session_factory() as session:
        visit = await VisitService.create_visit(
            session,
            make_visit_data(),
        )

        assert visit.id is not None
        assert visit.status == VisitStatus.SCHEDULED
        assert visit.rate == Decimal("80.00")


@pytest.mark.asyncio
async def test_complete_visit_creates_outbox_event(visits_session_factory):
    async with visits_session_factory() as session:
        visit = await VisitService.create_visit(
            session,
            make_visit_data(),
        )
        visit_id = visit.id

    async with visits_session_factory() as session:
        completed_visit = await VisitService.complete_visit(
            session,
            visit_id,
        )

        assert completed_visit.status == VisitStatus.COMPLETED

    async with visits_session_factory() as session:
        result = await session.execute(
            select(OutboxEvent).where(
                OutboxEvent.aggregate_id == visit_id
            )
        )
        events = result.scalars().all()

        assert len(events) == 1
        assert events[0].event_type == "VisitCompleted"
        assert events[0].payload["visit_id"] == str(visit_id)


@pytest.mark.asyncio
async def test_completing_already_completed_visit_does_not_create_duplicate_event(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        visit = await VisitService.create_visit(
            session,
            make_visit_data(),
        )
        visit_id = visit.id

    async with visits_session_factory() as session:
        await VisitService.complete_visit(session, visit_id)

    async with visits_session_factory() as session:
        await VisitService.complete_visit(session, visit_id)

    async with visits_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.aggregate_id == visit_id)
        )

        assert result.scalar_one() == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [VisitStatus.CANCELED, VisitStatus.MISSED],
)
async def test_cannot_complete_visit_with_invalid_status(
    visits_session_factory,
    status,
):
    async with visits_session_factory() as session:
        visit = Visit(
            **make_visit_data().model_dump(),
            status=status,
        )
        session.add(visit)
        await session.commit()
        visit_id = visit.id

    async with visits_session_factory() as session:
        with pytest.raises(VisitCannotBeCompletedError):
            await VisitService.complete_visit(session, visit_id)

    async with visits_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.aggregate_id == visit_id)
        )

        assert result.scalar_one() == 0


@pytest.mark.asyncio
async def test_complete_nonexistent_visit_raises_not_found(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        with pytest.raises(VisitNotFoundError):
            await VisitService.complete_visit(session, uuid.uuid4())


@pytest.mark.asyncio
async def test_concurrent_completion_creates_only_one_outbox_event(
    visits_session_factory,
):
    async with visits_session_factory() as session:
        visit = await VisitService.create_visit(
            session,
            make_visit_data(),
        )
        visit_id = visit.id

    barrier = asyncio.Barrier(2)

    async def complete_visit():
        async with visits_session_factory() as session:
            await barrier.wait()
            return await VisitService.complete_visit(session, visit_id)

    results = await asyncio.gather(
        complete_visit(),
        complete_visit(),
    )

    assert all(
        result.status == VisitStatus.COMPLETED
        for result in results
    )

    async with visits_session_factory() as session:
        result = await session.execute(
            select(func.count())
            .select_from(OutboxEvent)
            .where(OutboxEvent.aggregate_id == visit_id)
        )

        assert result.scalar_one() == 1
