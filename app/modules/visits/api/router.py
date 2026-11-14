from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.modules.visits.schemas.visit import VisitCreate, VisitResponse
from app.modules.visits.services.exceptions import (
    VisitCannotBeCompletedError,
    VisitNotFoundError,
)
from app.modules.visits.services.visit_service import VisitService


router = APIRouter(
    prefix="/api/visits",
    tags=["Visits"],
)

@router.post(
    "",
    response_model=VisitResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_visit(
    data: VisitCreate,
    session: AsyncSession = Depends(get_db),
) -> VisitResponse:
    return await VisitService.create_visit(session, data)

@router.post(
    "/{visit_id}/complete",
    response_model=VisitResponse,
)
async def complete_visit(
    visit_id: UUID,
    session: AsyncSession = Depends(get_db),
) -> VisitResponse:
    try:
        return await VisitService.complete_visit(session, visit_id)

    except VisitNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Visit not found",
        )

    except VisitCannotBeCompletedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Visit cannot be completed in its current status",
        )
