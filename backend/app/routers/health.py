from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from ..db import DatabaseSession
from ..errors import AppError, ErrorResponse

router = APIRouter(prefix="/health", tags=["health"])


class HealthResponse(BaseModel):
    status: Literal["ok"]


@router.get("", summary="Check process liveness")
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@router.get("/db", summary="Check database readiness", responses={503: {"model": ErrorResponse}})
def database_health(session: DatabaseSession) -> HealthResponse:
    try:
        session.execute(text("SELECT 1")).scalar_one()
    except SQLAlchemyError:
        raise AppError(503, "database_unavailable", "Database is unavailable.") from None
    return HealthResponse(status="ok")
