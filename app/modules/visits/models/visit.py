import uuid
from enum import Enum

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    Numeric,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.visits.models.base import VisitsBase


class VisitStatus(str, Enum):
    SCHEDULED = "Scheduled"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    CANCELED = "Canceled"
    MISSED = "Missed"


class Visit(VisitsBase):
    __tablename__ = "visits"

    __table_args__ = (
        CheckConstraint(
            "end_date_time > start_date_time",
            name="ck_visits_end_after_start",
        ),
        CheckConstraint(
            "rate >= 0",
            name="ck_visits_rate_non_negative",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    start_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    end_date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    status: Mapped[VisitStatus] = mapped_column(
        SQLAlchemyEnum(VisitStatus, name="visit_status"),
        nullable=False,
        default=VisitStatus.SCHEDULED,
    )
