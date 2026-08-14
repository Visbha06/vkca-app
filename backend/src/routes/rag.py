"""Authenticated, bounded HTTP verification boundary for RAG retrieval."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import get_settings
from src.database import get_db
from src.middleware.auth import AuthenticatedUser, get_current_user
from src.schemas.rag import (
    RagRetrievalErrorResponse,
    RagRetrievalRequest,
    RagRetrievalResponse,
)
from src.services.rag.embedding import (
    EmbeddingProvider,
    EmbeddingProviderError,
    create_embedding_provider,
)
from src.services.rag.retrieval import RagRetrievalService

router = APIRouter(prefix="/rag", tags=["rag"])


def get_rag_embedding_provider() -> EmbeddingProvider:
    """Create the configured provider at the service boundary, never at import."""

    return create_embedding_provider(get_settings())


def get_rag_retrieval_service(
    session: Annotated[AsyncSession, Depends(get_db)],
    provider: Annotated[EmbeddingProvider, Depends(get_rag_embedding_provider)],
) -> RagRetrievalService:
    """Construct one request-scoped retrieval service from bounded settings."""

    settings = get_settings()
    return RagRetrievalService(
        session,
        provider=provider,
        query_max_characters=settings.rag_query_max_characters,
        result_limit_default=settings.rag_result_limit_default,
        result_limit_max=settings.rag_result_limit_max,
        timeout_seconds=settings.rag_embedding_timeout_seconds,
    )


@router.get(
    "/retrieval",
    response_model=RagRetrievalResponse,
    operation_id="retrieve_authorized_rag_knowledge",
    responses={
        status.HTTP_401_UNAUTHORIZED: {"model": RagRetrievalErrorResponse},
        status.HTTP_422_UNPROCESSABLE_CONTENT: {"model": RagRetrievalErrorResponse},
        status.HTTP_503_SERVICE_UNAVAILABLE: {"model": RagRetrievalErrorResponse},
    },
)
async def retrieve_rag_knowledge(
    params: Annotated[RagRetrievalRequest, Query()],
    current_user: Annotated[AuthenticatedUser, Depends(get_current_user)],
    service: Annotated[RagRetrievalService, Depends(get_rag_retrieval_service)],
) -> RagRetrievalResponse:
    """Retrieve safe chunks using only server-derived current authorization."""

    user, _auth_session = current_user
    try:
        return await service.retrieve(user, params)
    except EmbeddingProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG retrieval is temporarily unavailable.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="RAG retrieval parameters are invalid.",
        ) from exc
