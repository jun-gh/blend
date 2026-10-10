"""Health check endpoints."""

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    version: str


@router.get("/", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Liveness probe - returns 200 OK when service is running."""
    return HealthResponse(status="ok", version=__version__)
