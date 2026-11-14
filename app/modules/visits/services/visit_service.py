import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.events import VisitCompletedEvent
from app.modules.visits.models.outbox_event import OutboxEvent
from app.modules.visits.models.visit import Visit, VisitStatus
from app.modules.visits.schemas.visit import VisitCreate
from app.modules.visits.services.exceptions import (
    VisitCannotBeCompletedError,
    VisitNotFoundError,
)


class VisitService:

    @staticmethod
    async def create_visit(
        session: AsyncSession,
        data: VisitCreate,
    ) -> Visit:
        visit = Visit(**data.model_dump())

        session.add(visit)
        await session.commit()
        await session.refresh(visit)

        return visit

    @staticmethod
    async def complete_visit(
        session: AsyncSession,
        visit_id: uuid.UUID,
    ) -> Visit:
        async with session.begin():
            result = await session.execute(
                select(Visit)
                .where(Visit.id == visit_id)
                .with_for_update()
            )

            visit = result.scalar_one_or_none()

            if visit is None:
                raise VisitNotFoundError()

            if visit.status == VisitStatus.COMPLETED:
                return visit

            if visit.status not in (
                VisitStatus.SCHEDULED,
                VisitStatus.IN_PROGRESS,
            ):
                raise VisitCannotBeCompletedError()

            visit.status = VisitStatus.COMPLETED

            event_id = uuid.uuid4()

            event = VisitCompletedEvent(
                event_id=event_id,
                occurred_at=datetime.now(UTC),
                visit_id=visit.id,
                start_date_time=visit.start_date_time,
                end_date_time=visit.end_date_time,
                rate=visit.rate,
            )

            outbox_event = OutboxEvent(
                id=event_id,
                event_type=event.event_type,
                aggregate_id=visit.id,
                payload=event.model_dump(mode="json"),
            )

            session.add(outbox_event)

        return visit
