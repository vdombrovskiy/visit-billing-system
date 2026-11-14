from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.billing.models.base import BillingBase


class ProcessedEvent(BillingBase):
    __tablename__ = "processed_events"

    event_id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
    )
    event_type: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
