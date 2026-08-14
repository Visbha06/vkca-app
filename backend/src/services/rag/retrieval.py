"""Authorization-constrained pgvector retrieval with a safe typed result."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import ColumnElement, and_, any_, exists, false, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from src.enums import UserRole
from src.models.player import Player
from src.models.rag_chunk import RagChunk
from src.models.rag_document import RagDocument
from src.models.user import User
from src.schemas.rag import (
    RagRetrievalProvenance,
    RagRetrievalRequest,
    RagRetrievalResponse,
    RagRetrievalResult,
)
from src.services.rag.canonical import normalize_text
from src.services.rag.contracts import EmbeddingProfile
from src.services.rag.embedding import (
    EmbeddingBatcher,
    EmbeddingCompatibilityError,
    EmbeddingProvider,
)
from src.services.rag.scope import RagAccessScope, RagAccessScopeResolver

PLAYER_PROFILE_TYPES = frozenset({"player_profile"})
TEAM_TYPES = frozenset({"team"})
MATCH_TYPES = frozenset({"match"})
PERFORMANCE_TYPES = frozenset(
    {
        "match_batting_performance",
        "match_bowling_performance",
        "match_fielding_performance",
    }
)
STATISTICS_TYPES = frozenset(
    {
        "player_batting_stats",
        "player_bowling_stats",
    }
)
CALENDAR_TYPES = frozenset({"calendar_occurrence"})
PLAYER_SCOPED_TYPES = PLAYER_PROFILE_TYPES | PERFORMANCE_TYPES | STATISTICS_TYPES
REGISTERED_RETRIEVAL_TYPES = (
    PLAYER_SCOPED_TYPES | TEAM_TYPES | MATCH_TYPES | CALENDAR_TYPES
)


class AccessScopeResolver(Protocol):
    async def resolve(self, user: User) -> RagAccessScope: ...


class SourceRegistry(Protocol):
    @property
    def source_types(self) -> tuple[str, ...]: ...


def _overlap(column, values: Sequence[object]) -> ColumnElement[bool]:
    return column.overlap(list(values)) if values else false()


def build_authorization_predicate(
    scope: RagAccessScope,
    *,
    registered_source_types: Sequence[str] | None = None,
) -> ColumnElement[bool]:
    """Build the complete role/source visibility matrix as a SQL predicate."""

    if scope.denies_all:
        return false()
    allowed_types = frozenset(registered_source_types or REGISTERED_RETRIEVAL_TYPES)
    if not allowed_types:
        return false()
    if scope.can_read_all_registered_sources:
        active_player = exists(
            select(Player.id).where(
                Player.is_active.is_(True),
                Player.id == any_(RagChunk.player_ids),
            )
        )
        return and_(
            RagChunk.source_type.in_(allowed_types),
            or_(
                ~RagChunk.source_type.in_(PLAYER_SCOPED_TYPES),
                active_player,
            ),
        )

    player_overlap = _overlap(RagChunk.player_ids, scope.active_player_ids)
    team_overlap = _overlap(RagChunk.team_ids, scope.team_ids)
    age_group_overlap = _overlap(RagChunk.age_groups, scope.age_groups)
    calendar = and_(
        RagChunk.source_type.in_(CALENDAR_TYPES),
        or_(RagChunk.is_all_academy.is_(True), age_group_overlap),
    )
    if scope.role is UserRole.ASSISTANT_COACH:
        return and_(
            RagChunk.source_type.in_(allowed_types),
            or_(
                and_(
                    RagChunk.source_type.in_(PLAYER_PROFILE_TYPES | STATISTICS_TYPES),
                    player_overlap,
                ),
                and_(
                    RagChunk.source_type.in_(PERFORMANCE_TYPES),
                    player_overlap,
                    team_overlap,
                ),
                and_(
                    RagChunk.source_type.in_(TEAM_TYPES | MATCH_TYPES),
                    team_overlap,
                ),
                calendar,
            ),
        )
    if scope.role is UserRole.PLAYER and scope.linked_player_id is not None:
        own_player = RagChunk.player_ids.overlap([scope.linked_player_id])
        return and_(
            RagChunk.source_type.in_(allowed_types),
            or_(
                and_(
                    RagChunk.source_type.in_(PLAYER_PROFILE_TYPES | STATISTICS_TYPES),
                    own_player,
                ),
                and_(
                    RagChunk.source_type.in_(PERFORMANCE_TYPES),
                    own_player,
                    team_overlap,
                ),
                and_(
                    RagChunk.source_type.in_(TEAM_TYPES | MATCH_TYPES),
                    team_overlap,
                ),
                calendar,
            ),
        )
    return false()


def build_retrieval_statement(
    scope: RagAccessScope,
    *,
    query_vector: Sequence[float],
    profile: EmbeddingProfile,
    limit: int,
    registered_source_types: Sequence[str] | None = None,
) -> Select[tuple[object, ...]]:
    """Select safe fields from only authorized candidates before cosine ordering."""

    if limit <= 0:
        raise ValueError("retrieval limit must be positive")
    if len(query_vector) != profile.dimension:
        raise ValueError("query vector dimension is incompatible")
    score = RagChunk.embedding.cosine_distance(list(query_vector)).label("score")
    return (
        select(
            RagChunk.id.label("chunk_id"),
            RagChunk.document_id.label("document_id"),
            RagChunk.source_type.label("source_type"),
            RagChunk.source_key.label("source_key"),
            RagChunk.semantic_text.label("semantic_text"),
            RagDocument.source_entity_id.label("source_entity_id"),
            score,
        )
        .join(RagDocument, RagDocument.id == RagChunk.document_id)
        .where(
            RagChunk.is_searchable.is_(True),
            RagDocument.is_searchable.is_(True),
            RagChunk.provider_name == profile.provider_name,
            RagChunk.model_name == profile.model_name,
            RagChunk.embedding_dimension == profile.dimension,
            build_authorization_predicate(
                scope,
                registered_source_types=registered_source_types,
            ),
        )
        .order_by(score, RagChunk.id)
        .limit(limit)
    )


class RagRetrievalService:
    """Resolve current scope, embed one query, and execute one candidate query."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: EmbeddingProvider,
        query_max_characters: int,
        result_limit_default: int,
        result_limit_max: int,
        timeout_seconds: float,
        scope_resolver: AccessScopeResolver | None = None,
        registry: SourceRegistry | None = None,
    ) -> None:
        if query_max_characters <= 0:
            raise ValueError("query maximum must be positive")
        if result_limit_default <= 0 or result_limit_max <= 0:
            raise ValueError("retrieval result limits must be positive")
        if result_limit_default > result_limit_max:
            raise ValueError("default retrieval limit cannot exceed maximum")
        self.session = session
        self.provider = provider
        self.query_max_characters = query_max_characters
        self.result_limit_default = result_limit_default
        self.result_limit_max = result_limit_max
        self.scope_resolver = scope_resolver or RagAccessScopeResolver(session)
        if registry is None:
            from src.services.rag.registry import source_registry

            registry = source_registry
        self.registered_source_types = registry.source_types
        self.batcher = EmbeddingBatcher(batch_size=1, timeout_seconds=timeout_seconds)

    async def retrieve(
        self,
        user: User,
        request: RagRetrievalRequest,
    ) -> RagRetrievalResponse:
        """Return bounded safe rows after current relational authorization."""

        query = normalize_text(request.query)
        if not query or len(query) > self.query_max_characters:
            raise ValueError("retrieval query exceeds its configured bound")
        limit = request.limit or self.result_limit_default
        if limit <= 0 or limit > self.result_limit_max:
            raise ValueError("retrieval limit exceeds its configured bound")

        scope = await self.scope_resolver.resolve(user)
        if scope.denies_all:
            return RagRetrievalResponse(
                results=[],
                returned_count=0,
                limit=limit,
            )
        incompatible_profile = bool(
            await self.session.scalar(
                select(
                    exists().where(
                        RagChunk.is_searchable.is_(True),
                        or_(
                            RagChunk.provider_name
                            != self.provider.profile.provider_name,
                            RagChunk.model_name != self.provider.profile.model_name,
                            RagChunk.embedding_dimension
                            != self.provider.profile.dimension,
                        ),
                    )
                )
            )
        )
        if incompatible_profile:
            raise EmbeddingCompatibilityError(
                "The searchable index uses an incompatible embedding profile; "
                "run a targeted or full rebuild."
            )
        query_embedding = await self.batcher.embed_query(
            self.provider,
            query,
            profile=self.provider.profile,
        )
        statement = build_retrieval_statement(
            scope,
            query_vector=query_embedding.values,
            profile=self.provider.profile,
            limit=limit,
            registered_source_types=self.registered_source_types,
        )
        rows = (await self.session.execute(statement)).all()
        results = [
            RagRetrievalResult(
                chunk_id=row[0],
                document_id=row[1],
                source_type=row[2],
                source_key=row[3],
                text=row[4],
                score=float(row[6]),
                provenance=RagRetrievalProvenance(
                    source_type=row[2],
                    source_entity_id=row[5],
                ),
            )
            for row in rows[:limit]
        ]
        return RagRetrievalResponse(
            results=results,
            returned_count=len(results),
            limit=limit,
        )
