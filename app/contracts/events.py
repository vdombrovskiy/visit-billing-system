import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class VisitCompletedEvent(BaseModel):
    event_id: uuid.UUID
    event_type: str = "VisitCompleted"
    occurred_at: datetime

    visit_id: uuid.UUID
    start_date_time: datetime
    end_date_time: datetime
    rate: Decimal
