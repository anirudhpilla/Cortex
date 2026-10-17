import hashlib
import logging
import os
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.search import DocumentChunk, IndexedFile, Repository
from app.retrieval import get_embeddings

logger = logging.getLogger(__name__)

SUPPORTED_EXTENSIONS = {
    ".md",
    ".mdx",
    ".txt",
    ".rst",
    ".pdf",
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".java",
    ".go",
    ".rs",
    ".c",
    ".h",
    ".cpp",
    ".hpp",
    ".cs",
    ".rb",
    ".php",
    ".kt",
    ".swift",
    ".sql",
    ".sh",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".html",
    ".css",
    ".scss",
    ".xml",
}

IGNORED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    "dist",
    "build",
    ".next",
    ".idea",
    ".vscode",
}


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def chunk_id(
    repository_id: int,
    path: str,
    index: int,
    content: str,
) -> str:
    return sha256_text(f"{repository_id}\0{path}\0{index}\0{content}")


def read_file(path: Path, relative_path: str) -> list[Document]:
    if path.suffix.lower() == ".pdf":
        documents = PyPDFLoader(str(path)).load()

        for page_number, document in enumerate(documents, start=1):
            document.metadata["source"] = relative_path
            document.metadata["page_number"] = page_number

        return documents

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        logger.warning("Unable to read file: %s", relative_path)
        raise

    if not content.strip():
        return []

    return [
        Document(
            page_content=content,
            metadata={"source": relative_path},
        )
    ]


def resolve_repository_file(root: Path, path: Path) -> Path | None:
    """Resolve a regular file and reject paths escaping the repository."""
    try:
        resolved_root = root.resolve(strict=True)

        # Reject symlinks rather than following them.
        if path.is_symlink():
            return None

        resolved_path = path.resolve(strict=True)
        resolved_path.relative_to(resolved_root)

        if not resolved_path.is_file():
            return None

        return resolved_path

    except (OSError, ValueError, RuntimeError):
        return None


async def index_file(
    session: AsyncSession,
    repository: Repository,
    path: Path,
    relative_path: str,
) -> bool:
    settings = get_settings()

    if path.stat().st_size > settings.max_file_bytes:
        logger.warning("Skipping oversized file: %s", relative_path)
        return False

    documents = read_file(path, relative_path)
    if not documents:
        return False

    full_text = "\n\n".join(d.page_content for d in documents)
    content_hash = sha256_text(full_text)

    existing = await session.scalar(
        select(IndexedFile).where(
            IndexedFile.repository_id == repository.id,
            IndexedFile.path == relative_path,
        )
    )

    if existing and existing.content_hash == content_hash:
        return False

    if not documents:
        async with session.begin_nested():
            if existing is not None:
                await session.execute(
                    delete(DocumentChunk).where(DocumentChunk.file_id == existing.id)
                )
                existing.content_hash = sha256_text("")
        return existing is not None

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
        separators=[
            "\nclass ",
            "\nasync def ",
            "\ndef ",
            "\nfunction ",
            "\n\n",
            "\n",
            " ",
            "",
        ],
    )

    chunks = splitter.split_documents(documents)
    if not chunks:
        return False

    embeddings = get_embeddings()
    vectors = await embeddings.aembed_documents(
        [chunk.page_content for chunk in chunks]
    )

    if len(chunks) != len(vectors):
        raise ValueError("Embedding count does not match chunk count")

    if any(len(vector) != settings.embedding_dimensions for vector in vectors):
        raise ValueError("Embedding dimension mismatch")

    # Reuse the file record so its ID stays stable.
    async with session.begin_nested():
        if existing is None:
            existing = IndexedFile(
                repository_id=repository.id,
                path=relative_path,
                content_hash=content_hash,
            )
            session.add(existing)
            await session.flush()
        else:
            existing.content_hash = content_hash
            await session.flush()

        await session.execute(
            delete(DocumentChunk).where(DocumentChunk.file_id == existing.id)
        )

        for index, (chunk, vector) in enumerate(zip(chunks, vectors)):
            start_index = chunk.metadata.get("start_index")
            page_number = chunk.metadata.get("page_number")

            session.add(
                DocumentChunk(
                    id=chunk_id(
                        repository.id,
                        relative_path,
                        index,
                        chunk.page_content,
                    ),
                    file_id=existing.id,
                    chunk_index=index,
                    content=chunk.page_content,
                    embedding=vector,
                    search_vector=func.to_tsvector(
                        "simple",
                        chunk.page_content,
                    ),
                    start_index=start_index,
                    end_index=(
                        start_index + len(chunk.page_content)
                        if start_index is not None
                        else None
                    ),
                    page_number=page_number,
                    embedding_model=settings.embedding_model_version,
                )
            )

        await session.flush()

        await session.execute(select(func.set_config("search_path", "public", True)))

        # Populate the PostgreSQL full-text search representation.
        await session.execute(
            __import__("sqlalchemy")
            .update(DocumentChunk)
            .where(DocumentChunk.file_id == existing.id)
            .values(
                search_vector=func.to_tsvector(
                    "simple",
                    DocumentChunk.content,
                )
            )
        )

    return True


async def ingest_repository(
    session: AsyncSession,
    repository_id: int,
    owner_id: int,
) -> dict[str, int]:
    settings = get_settings()

    repository = await session.scalar(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.owner_id == owner_id,
        )
    )

    if repository is None:
        raise ValueError("Repository not found")

    # Resolve and validate the repository root.
    try:
        root = Path(repository.root_path).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError("Repository directory does not exist") from exc

    if not root.is_dir():
        raise ValueError("Repository directory does not exist")

    # Restrict repository roots to the configured base directory.
    try:
        base_path = Path(settings.repository_base_path).resolve(strict=True)
        root.relative_to(base_path)
    except (OSError, ValueError, RuntimeError) as exc:
        raise ValueError("Repository root is outside the permitted directory") from exc

    indexed = 0
    skipped = 0
    failed = 0
    discovered_files = 0
    total_bytes = 0
    seen_paths: set[str] = set()

    # followlinks=False prevents traversal through directory symlinks.
    for directory, dirs, filenames in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current_dir = Path(directory)

        # Prune ignored directories and symlinked directories.
        dirs[:] = [
            name
            for name in dirs
            if name not in IGNORED_DIRS and not (current_dir / name).is_symlink()
        ]

        for filename in filenames:
            candidate = current_dir / filename

            if candidate.is_symlink():
                skipped += 1
                continue

            if candidate.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue

            resolved_path = resolve_repository_file(root, candidate)

            if resolved_path is None:
                logger.warning("Skipping unsafe or inaccessible repository path")
                skipped += 1
                continue

            discovered_files += 1

            if discovered_files > settings.max_repository_files:
                raise ValueError("Repository file-count limit exceeded")

            try:
                file_size = resolved_path.stat().st_size
            except OSError:
                logger.exception("Unable to stat repository file")
                failed += 1
                continue

            if file_size > settings.max_file_bytes:
                logger.warning("Skipping oversized repository file")
                skipped += 1
                continue

            total_bytes += file_size

            if total_bytes > settings.max_repository_bytes:
                raise ValueError("Repository byte limit exceeded")

            relative_path = resolved_path.relative_to(root).as_posix()
            seen_paths.add(relative_path)

            try:
                changed = await index_file(
                    session=session,
                    repository=repository,
                    path=resolved_path,
                    relative_path=relative_path,
                )

                if changed:
                    indexed += 1
                else:
                    skipped += 1

                # Commit each file to limit transaction size.
                await session.commit()

            except Exception:
                await session.rollback()
                failed += 1

                logger.exception(
                    "Failed to index repository file",
                    extra={
                        "repository_id": repository_id,
                        "relative_path": relative_path,
                    },
                )

    # Remove database records for files no longer present on disk.
    existing_paths = set(
        (
            await session.scalars(
                select(IndexedFile.path).where(
                    IndexedFile.repository_id == repository_id
                )
            )
        ).all()
    )

    stale_paths = existing_paths - seen_paths

    if stale_paths:
        await session.execute(
            delete(IndexedFile).where(
                IndexedFile.repository_id == repository_id,
                IndexedFile.path.in_(stale_paths),
            )
        )
        await session.commit()

    return {
        "indexed_files": indexed,
        "unchanged_or_skipped": skipped,
        "failed_files": failed,
        "removed_files": len(stale_paths),
    }
