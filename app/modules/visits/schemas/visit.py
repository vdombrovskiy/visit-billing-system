import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.modules.visits.models.visit import VisitStatus


class VisitCreate(BaseModel):
    start_date_time: datetime
    end_date_time: datetime
    description: str = Field(min_length=1)
    rate: Decimal = Field(ge=0, max_digits=10, decimal_places=2)

    @model_validator(mode="after")
    def validate_visit_period(self):
        if self.start_date_time.utcoffset() is None:
            raise ValueError("start_date_time must include a timezone")

        if self.end_date_time.utcoffset() is None:
            raise ValueError("end_date_time must include a timezone")

        if self.end_date_time <= self.start_date_time:
            raise ValueError("end_date_time must be after start_date_time")

        return self


class VisitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    start_date_time: datetime
    end_date_time: datetime
    description: str
    rate: Decimal
    status: VisitStatus
