from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_admin
from app.database import get_db_session
from app.models.user import User
from app.schemas import ChatResponse, Query
from app.services.search_service import search_repository

router = APIRouter(prefix="/search", tags=["search"])

DatabaseSession = Annotated[AsyncSession, Depends(get_db_session)]
CurrentAdmin = Annotated[User, Depends(get_current_admin)]


@router.post("/query", response_model=ChatResponse)
async def search(
    body: Query,
    session: DatabaseSession,
    admin: CurrentAdmin,
) -> ChatResponse:
    try:
        return await search_repository(
            session,
            owner_id=admin.id,
            question=body.question,
            repository_id=body.repository_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Repository not found") from exc
