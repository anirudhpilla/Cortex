from functools import lru_cache

from langchain_ollama import OllamaEmbeddings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings


@lru_cache
def get_embeddings() -> OllamaEmbeddings:
    settings = get_settings()
    return OllamaEmbeddings(
        model=settings.ollama_embed_model,
        base_url=settings.ollama_base_url,
    )


HYBRID_SEARCH_SQL = text("""
WITH query_terms AS (
    SELECT plainto_tsquery('simple', :query) AS tsq
),
vector_candidates AS (
    SELECT
        c.id,
        ROW_NUMBER() OVER (
            ORDER BY c.embedding <=> CAST(:embedding AS vector)
        ) AS rank
    FROM document_chunks c
    JOIN indexed_files f ON f.id = c.file_id
    JOIN repositories r ON r.id = f.repository_id
    WHERE r.owner_id = :owner_id
      AND (:repository_id IS NULL OR r.id = :repository_id)
      AND c.embedding_model = :embedding_model
    ORDER BY c.embedding <=> CAST(:embedding AS vector)
    LIMIT :candidate_k
),
text_candidates AS (
    SELECT
        c.id,
        ROW_NUMBER() OVER (
            ORDER BY ts_rank_cd(c.search_vector, q.tsq) DESC
        ) AS rank
    FROM document_chunks c
    JOIN indexed_files f ON f.id = c.file_id
    JOIN repositories r ON r.id = f.repository_id
    CROSS JOIN query_terms q
    WHERE r.owner_id = :owner_id
      AND (:repository_id IS NULL OR r.id = :repository_id)
      AND c.search_vector @@ q.tsq
    ORDER BY ts_rank_cd(c.search_vector, q.tsq) DESC
    LIMIT :candidate_k
),
fused AS (
    SELECT id, SUM(score) AS score
    FROM (
        SELECT id, 1.0 / (60 + rank) AS score FROM vector_candidates
        UNION ALL
        SELECT id, 1.0 / (60 + rank) AS score FROM text_candidates
    ) ranked
    GROUP BY id
)
SELECT
    c.id,
    c.content,
    c.start_index,
    c.end_index,
    c.page_number,
    f.path,
    f.repository_id,
    fused.score
FROM fused
JOIN document_chunks c ON c.id = fused.id
JOIN indexed_files f ON f.id = c.file_id
JOIN repositories r ON r.id = f.repository_id
WHERE r.owner_id = :owner_id
  AND (:repository_id IS NULL OR r.id = :repository_id)
ORDER BY fused.score DESC
LIMIT :result_k
""")


async def retrieve(
    session: AsyncSession,
    question: str,
    *,
    owner_id: int,
    repository_id: int | None = None,
) -> list[dict]:
    settings = get_settings()

    if repository_id is not None:
        from sqlalchemy import select

        from app.models.search import Repository

        repository = await session.scalar(
            select(Repository.id).where(
                Repository.id == repository_id,
                Repository.owner_id == owner_id,
            )
        )
        if repository is None:
            raise ValueError("Repository not found")

    embeddings = await get_embeddings().aembed_query(question)

    if len(embeddings) != settings.embedding_dimensions:
        raise RuntimeError("Query embedding dimension mismatch")

    vector_literal = "[" + ",".join(str(float(x)) for x in embeddings) + "]"

    result = await session.execute(
        HYBRID_SEARCH_SQL,
        {
            "embedding": vector_literal,
            "query": question,
            "owner_id": owner_id,
            "repository_id": repository_id,
            "embedding_model": settings.embedding_model_version,
            "candidate_k": settings.candidate_k,
            "result_k": settings.retrieval_k,
        },
    )

    return [dict(row) for row in result.mappings().all()]
