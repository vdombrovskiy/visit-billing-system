
import uuid
from datetime import datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    Index,
    Integer,
    Numeric,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.billing.models.base import BillingBase


class BillingRecordStatus(str, Enum):
    CREATED = "Created"
    REVERSED = "Reversed"


class BillingRecord(BillingBase):
    __tablename__ = "billing_records"

    __table_args__ = (
        CheckConstraint(
            "rate >= 0",
            name="ck_billing_records_rate_non_negative",
        ),
        CheckConstraint(
            "duration_seconds > 0",
            name="ck_billing_records_duration_positive",
        ),
        CheckConstraint(
            "amount >= 0",
            name="ck_billing_records_amount_non_negative",
        ),
        Index(
            "uq_billing_records_active_visit",
            "visit_id",
            unique=True,
            postgresql_where=text("status = 'Created'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    visit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        nullable=False,
    )
    rate: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
    )
    duration_seconds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2),
        nullable=False,
    )
    status: Mapped[BillingRecordStatus] = mapped_column(
        SQLAlchemyEnum(
            BillingRecordStatus,
            name="billing_record_status",
            values_callable=lambda enum: [item.value for item in enum],
        ),
        nullable=False,
        default=BillingRecordStatus.CREATED,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
