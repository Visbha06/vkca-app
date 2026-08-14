"""Head Coach-only service for explicit Player account association."""

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import AuditActionType, AuditEntityType, UserRole
from src.models.player import Player
from src.models.user import User
from src.schemas.player_account import (
    PaginatedPlayerAccountResponse,
    PlayerAccountAssociationResponse,
    PlayerAccountLinkRequest,
    PlayerAccountLookupQuery,
    PlayerAccountReassignRequest,
    PlayerAccountSnapshot,
    PlayerAccountUnlinkRequest,
)
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
    BusinessAuditService,
)
from src.services.occ import check_and_increment_version


class PlayerAccountAuthorizationError(Exception):
    """Raised when a non-Head Coach reaches the service boundary."""


class PlayerAccountNotFoundError(Exception):
    """Raised when a requested Player or User does not exist."""


class PlayerAccountConflictError(Exception):
    """Raised when current association state conflicts with a mutation."""


class PlayerAccountValidationError(Exception):
    """Raised when an account is not eligible for Player association."""


class PlayerAccountService:
    """Query and mutate one-to-one Player account links atomically."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    @staticmethod
    def _require_head_coach(actor: AuditActorContext) -> None:
        if actor.role is not UserRole.HEAD_COACH:
            raise PlayerAccountAuthorizationError("Head Coach access is required.")

    @staticmethod
    def _snapshot(user: User) -> PlayerAccountSnapshot:
        return PlayerAccountSnapshot(
            id=user.id,
            display_name=f"{user.first_name} {user.last_name}".strip(),
            email=user.email,
            role=UserRole.PLAYER,
            is_active=user.is_active,
        )

    @staticmethod
    def _target(player: Player) -> AuditTargetContext:
        return AuditTargetContext(
            entity_type=AuditEntityType.PLAYER,
            entity_id=player.id,
            label=f"{player.first_name} {player.last_name}".strip(),
        )

    async def _get_player(self, player_id: UUID) -> Player:
        player = await self.session.get(Player, player_id)
        if player is None:
            raise PlayerAccountNotFoundError("Player not found.")
        return player

    async def _get_player_account(self, user_id: UUID) -> User:
        user = await self.session.get(User, user_id)
        if user is None:
            raise PlayerAccountNotFoundError("Player account not found.")
        if user.role != UserRole.PLAYER:
            raise PlayerAccountValidationError(
                "Only a User with the player role can be linked."
            )
        return user

    async def _require_unlinked_account(
        self,
        user_id: UUID,
        *,
        player_id: UUID,
    ) -> None:
        linked_player_id = await self.session.scalar(
            select(Player.id).where(Player.user_id == user_id)
        )
        if linked_player_id is not None and linked_player_id != player_id:
            raise PlayerAccountConflictError(
                "The Player account is already linked to another profile."
            )

    async def list_eligible_accounts(
        self,
        query: PlayerAccountLookupQuery,
        *,
        actor: AuditActorContext,
    ) -> PaginatedPlayerAccountResponse:
        """Return one bounded page of unlinked Player-role accounts."""

        self._require_head_coach(actor)
        filters = [
            User.role == UserRole.PLAYER,
            ~exists(select(Player.id).where(Player.user_id == User.id)),
        ]
        if query.search is not None:
            escaped = (
                query.search.replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            pattern = f"%{escaped}%"
            filters.append(
                or_(
                    User.first_name.ilike(pattern, escape="\\"),
                    User.last_name.ilike(pattern, escape="\\"),
                    User.email.ilike(pattern, escape="\\"),
                    func.concat(User.first_name, " ", User.last_name).ilike(
                        pattern,
                        escape="\\",
                    ),
                )
            )

        total_users = int(
            await self.session.scalar(select(func.count(User.id)).where(*filters)) or 0
        )
        statement = (
            select(User)
            .where(*filters)
            .order_by(User.last_name, User.first_name, User.email, User.id)
            .offset((query.page - 1) * query.page_size)
            .limit(query.page_size)
        )
        rows = (await self.session.execute(statement)).all()
        users = [row[0] for row in rows]
        return PaginatedPlayerAccountResponse(
            users=[self._snapshot(user) for user in users],
            page=query.page,
            page_size=query.page_size,
            total_users=total_users,
            total_pages=(total_users + query.page_size - 1) // query.page_size,
        )

    async def get_association(
        self,
        player_id: UUID,
        *,
        actor: AuditActorContext,
    ) -> PlayerAccountAssociationResponse:
        """Return the protected safe snapshot for one Player profile."""

        self._require_head_coach(actor)
        player = await self._get_player(player_id)
        account = (
            None
            if player.user_id is None
            else self._snapshot(await self._get_player_account(player.user_id))
        )
        return PlayerAccountAssociationResponse(
            player_id=player.id,
            account=account,
            player_version_number=player.version_number,
        )

    async def link_account(
        self,
        player_id: UUID,
        payload: PlayerAccountLinkRequest,
        *,
        actor: AuditActorContext,
    ) -> PlayerAccountAssociationResponse:
        """Link one currently unassociated Player account."""

        self._require_head_coach(actor)
        try:
            player = await self._get_player(player_id)
            if player.user_id is not None:
                raise PlayerAccountConflictError(
                    "The Player profile is already linked to an account."
                )
            account = await self._get_player_account(payload.user_id)
            await self._require_unlinked_account(account.id, player_id=player.id)
            player.version_number = await check_and_increment_version(
                self.session,
                Player,
                player.id,
                payload.version_number,
            )
            player.user_id = account.id
            await BusinessAuditService(self.session).record(
                actor=actor,
                action_type=AuditActionType.PLAYER_ACCOUNT_LINKED,
                target=self._target(player),
                metadata={"account_user_id": account.id},
            )
            await self.session.commit()
            return PlayerAccountAssociationResponse(
                player_id=player.id,
                account=self._snapshot(account),
                player_version_number=player.version_number,
            )
        except IntegrityError as exc:
            await self.session.rollback()
            raise PlayerAccountConflictError(
                "The account or Player profile was linked by another request."
            ) from exc
        except Exception:
            await self.session.rollback()
            raise

    async def unlink_account(
        self,
        player_id: UUID,
        payload: PlayerAccountUnlinkRequest,
        *,
        actor: AuditActorContext,
    ) -> PlayerAccountAssociationResponse:
        """Remove an existing association without deleting either record."""

        self._require_head_coach(actor)
        try:
            player = await self._get_player(player_id)
            previous_account_id = player.user_id
            if previous_account_id is None:
                raise PlayerAccountConflictError(
                    "The Player profile has no linked account."
                )
            player.version_number = await check_and_increment_version(
                self.session,
                Player,
                player.id,
                payload.version_number,
            )
            player.user_id = None
            await BusinessAuditService(self.session).record(
                actor=actor,
                action_type=AuditActionType.PLAYER_ACCOUNT_UNLINKED,
                target=self._target(player),
                metadata={"previous_account_user_id": previous_account_id},
            )
            await self.session.commit()
            return PlayerAccountAssociationResponse(
                player_id=player.id,
                account=None,
                player_version_number=player.version_number,
            )
        except Exception:
            await self.session.rollback()
            raise

    async def reassign_account(
        self,
        player_id: UUID,
        payload: PlayerAccountReassignRequest,
        *,
        actor: AuditActorContext,
    ) -> PlayerAccountAssociationResponse:
        """Replace the exact expected account as one audited correction."""

        self._require_head_coach(actor)
        try:
            player = await self._get_player(player_id)
            if player.user_id != payload.expected_user_id:
                raise PlayerAccountConflictError(
                    "The linked account changed. Reload the Player before retrying."
                )
            account = await self._get_player_account(payload.new_user_id)
            await self._require_unlinked_account(account.id, player_id=player.id)
            player.version_number = await check_and_increment_version(
                self.session,
                Player,
                player.id,
                payload.version_number,
            )
            player.user_id = account.id
            await BusinessAuditService(self.session).record(
                actor=actor,
                action_type=AuditActionType.PLAYER_ACCOUNT_REASSIGNED,
                target=self._target(player),
                metadata={
                    "previous_account_user_id": payload.expected_user_id,
                    "account_user_id": account.id,
                },
            )
            await self.session.commit()
            return PlayerAccountAssociationResponse(
                player_id=player.id,
                account=self._snapshot(account),
                player_version_number=player.version_number,
            )
        except IntegrityError as exc:
            await self.session.rollback()
            raise PlayerAccountConflictError(
                "The account or Player profile was linked by another request."
            ) from exc
        except Exception:
            await self.session.rollback()
            raise
