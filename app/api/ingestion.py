from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin
from app.database import get_db_session
from app.ingestion import ingest_repository
from app.models.user import User

router = APIRouter(prefix="/ingestion", tags=["ingestion"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]


class IngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    repository_id: int = Field(gt=0)


@router.post("/run", status_code=status.HTTP_200_OK)
async def run_ingestion(
    body: IngestionRequest,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> dict[str, int]:
    try:
        return await ingest_repository(
            session=session,
            repository_id=body.repository_id,
            owner_id=admin.id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        ) from exc
