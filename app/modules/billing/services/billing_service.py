from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.contracts.events import VisitCompletedEvent
from app.modules.billing.models.billing_record import BillingRecord
from app.modules.billing.models.processed_event import ProcessedEvent


class BillingService:
    @staticmethod
    async def process_visit_completed(
        session: AsyncSession,
        event: VisitCompletedEvent,
    ) -> bool:
        statement = (
            insert(ProcessedEvent)
            .values(
                event_id=event.event_id,
                event_type=event.event_type,
            )
            .on_conflict_do_nothing(
                index_elements=[ProcessedEvent.event_id],
            )
            .returning(ProcessedEvent.event_id)
        )

        result = await session.execute(statement)
        processed_event_id = result.scalar_one_or_none()

        if processed_event_id is None:
            return False

        total_seconds = (
            event.end_date_time - event.start_date_time
        ).total_seconds()

        duration_seconds = int(total_seconds)

        if duration_seconds <= 0:
            raise ValueError("Visit duration must be positive")

        amount = (
            event.rate * Decimal(duration_seconds) / Decimal(3600)
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        billing_record = BillingRecord(
            visit_id=event.visit_id,
            rate=event.rate,
            duration_seconds=duration_seconds,
            amount=amount,
        )

        session.add(billing_record)

        return True
