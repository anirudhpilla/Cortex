from sqlalchemy.ext.asyncio import AsyncSession

from app.agent import answer_question
from app.models.search import Repository
from app.retrieval import retrieve
from app.schemas import ChatResponse, Source


async def search_repository(
    session: AsyncSession,
    *,
    owner_id: int,
    question: str,
    repository_id: int | None = None,
) -> ChatResponse:
    rows = await retrieve(
        session,
        question,
        owner_id=owner_id,
        repository_id=repository_id,
    )

    sources = [
        Source(
            id=row["id"],
            path=row["path"],
            text=row["content"],
            repository_id=row["repository_id"],
            start_index=row.get("start_index"),
            end_index=row.get("end_index"),
            page_number=row.get("page_number"),
        )
        for row in rows
    ]

    answer, provider = await answer_question(
        question=question,
        sources=sources,
    )

    selected_ids = set(answer.source_ids)

    return ChatResponse(
        answer=answer.answer,
        source_ids=answer.source_ids,
        insufficient_context=answer.insufficient_context,
        sources=[source for source in sources if source.id in selected_ids],
        provider=provider,
    )
