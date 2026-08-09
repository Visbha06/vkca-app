"""Application service for atomic team and roster operations."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import AuditActionType, AuditEntityType
from src.models.player import Player
from src.models.team import Team
from src.models.team_player import TeamPlayer
from src.schemas.team import (
    PaginatedTeamResponse,
    TeamCreate,
    TeamResponse,
    TeamRosterPlayerResponse,
    TeamRosterResponse,
    TeamUpdate,
)
from src.services.business_audit_service import (
    AuditActorContext,
    AuditTargetContext,
    BusinessAuditService,
)
from src.services.occ import check_and_increment_version


class TeamNotFoundError(Exception):
    """Raised when a requested team does not exist."""

    def __init__(self) -> None:
        super().__init__("Team not found.")


class PlayerNotFoundError(Exception):
    """Raised when a requested player does not exist."""

    def __init__(self) -> None:
        super().__init__("Player not found.")


class TeamValidationError(Exception):
    """Raised when a complete roster fails domain validation."""


class TeamNameConflictError(Exception):
    """Raised when a normalized name already exists in an age group."""

    def __init__(self) -> None:
        super().__init__(
            "A team with this name already exists in the selected age group."
        )


class TeamMembershipAlreadyExistsError(Exception):
    """Raised when a player is already on the requested team."""

    def __init__(self) -> None:
        super().__init__("Player is already a member of this team.")


class TeamRemediationConflictError(Exception):
    """Raised when a roster remediation target changed after evaluation."""


class TeamService:
    """Query and mutate teams while preserving complete roster consistency."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def _validate_roster_players(self, player_ids: list[UUID]) -> None:
        """Require 7–15 distinct, existing, active players."""

        if not 7 <= len(player_ids) <= 15:
            raise TeamValidationError("A team roster must contain 7 to 15 players.")
        if len(set(player_ids)) != len(player_ids):
            raise TeamValidationError("A team roster cannot contain duplicate players.")

        statement = select(Player.id, Player.is_active).where(Player.id.in_(player_ids))
        rows = (await self.session.execute(statement)).all()
        players_by_id = {player_id: is_active for player_id, is_active in rows}
        missing_ids = [
            player_id for player_id in player_ids if player_id not in players_by_id
        ]
        if missing_ids:
            raise PlayerNotFoundError
        if any(not players_by_id[player_id] for player_id in player_ids):
            raise TeamValidationError(
                "Only active players can be selected for a team roster."
            )

    async def _ensure_unique_name(
        self,
        name: str,
        age_group: str,
        *,
        exclude_team_id: UUID | None = None,
    ) -> None:
        """Reject normalized name collisions within one age group."""

        statement = select(Team.id).where(
            func.lower(func.trim(Team.name)) == func.lower(func.trim(name)),
            Team.age_group == age_group,
        )
        if exclude_team_id is not None:
            statement = statement.where(Team.id != exclude_team_id)
        if await self.session.scalar(statement.limit(1)) is not None:
            raise TeamNameConflictError

    @staticmethod
    def _team_response(team: Team, player_count: int) -> TeamResponse:
        return TeamResponse.model_validate(team).model_copy(
            update={"player_count": player_count}
        )

    async def create_team(
        self,
        payload: TeamCreate,
        *,
        actor: AuditActorContext | None = None,
    ) -> TeamResponse:
        """Create team details and the complete ordered roster atomically."""

        try:
            await self._validate_roster_players(payload.player_ids)
            await self._ensure_unique_name(payload.name, payload.age_group)

            team = Team(
                name=payload.name.strip(),
                age_group=payload.age_group,
            )
            self.session.add(team)
            await self.session.flush()
            self.session.add_all(
                [
                    TeamPlayer(
                        team_id=team.id,
                        player_id=player_id,
                        roster_order=index,
                    )
                    for index, player_id in enumerate(payload.player_ids, start=1)
                ]
            )
            await self.session.flush()
            if actor is not None:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=AuditActionType.TEAM_CREATED,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.TEAM,
                        entity_id=team.id,
                        label=team.name,
                    ),
                    metadata={
                        "age_group": team.age_group,
                        "roster_count": len(payload.player_ids),
                    },
                )
            await self.session.refresh(team)
            response = self._team_response(team, len(payload.player_ids))
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def update_team(
        self,
        team_id: UUID,
        payload: TeamUpdate,
        *,
        actor: AuditActorContext | None = None,
    ) -> TeamResponse:
        """Replace team details and its ordered roster in one OCC transaction."""

        try:
            team = await self.session.get(Team, team_id)
            if team is None:
                raise TeamNotFoundError

            previous_name = team.name
            previous_age_group = team.age_group
            previous_player_ids: list[UUID] = []
            if actor is not None:
                previous_player_ids = list(
                    (
                        await self.session.scalars(
                            select(TeamPlayer.player_id)
                            .where(TeamPlayer.team_id == team_id)
                            .order_by(
                                TeamPlayer.roster_order.asc(),
                                TeamPlayer.player_id.asc(),
                            )
                        )
                    ).all()
                )

            next_version = await check_and_increment_version(
                self.session,
                Team,
                team_id,
                payload.version_number,
            )
            await self._validate_roster_players(payload.player_ids)
            await self._ensure_unique_name(
                payload.name,
                payload.age_group,
                exclude_team_id=team_id,
            )

            team.name = payload.name.strip()
            team.age_group = payload.age_group
            team.version_number = next_version
            await self.session.execute(
                delete(TeamPlayer).where(TeamPlayer.team_id == team_id)
            )
            self.session.add_all(
                [
                    TeamPlayer(
                        team_id=team_id,
                        player_id=player_id,
                        roster_order=index,
                    )
                    for index, player_id in enumerate(payload.player_ids, start=1)
                ]
            )
            await self.session.flush()
            if actor is not None:
                action_type, audit_metadata = self._classify_team_update(
                    previous_name=previous_name,
                    previous_age_group=previous_age_group,
                    previous_player_ids=previous_player_ids,
                    next_name=team.name,
                    next_age_group=team.age_group,
                    next_player_ids=payload.player_ids,
                )
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=action_type,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.TEAM,
                        entity_id=team.id,
                        label=team.name,
                    ),
                    metadata=audit_metadata,
                )
            await self.session.refresh(team)
            response = self._team_response(team, len(payload.player_ids))
            await self.session.commit()
            return response
        except Exception:
            await self.session.rollback()
            raise

    async def list_teams(
        self,
        *,
        page: int = 1,
        page_size: int = 12,
    ) -> PaginatedTeamResponse:
        """Return teams and roster counts in stable paginated order."""

        if page < 1:
            raise ValueError("page must be greater than or equal to 1")
        if not 1 <= page_size <= 100:
            raise ValueError("page_size must be between 1 and 100")

        total_teams = int(await self.session.scalar(select(func.count(Team.id))) or 0)
        statement = (
            select(Team, func.count(TeamPlayer.player_id).label("player_count"))
            .outerjoin(TeamPlayer, TeamPlayer.team_id == Team.id)
            .group_by(Team.id)
            .order_by(Team.name, Team.age_group, Team.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = (await self.session.execute(statement)).all()
        teams = [
            TeamResponse.model_validate(team).model_copy(
                update={"player_count": int(player_count)}
            )
            for team, player_count in rows
        ]
        return PaginatedTeamResponse(
            teams=teams,
            page=page,
            page_size=page_size,
            total_teams=total_teams,
            total_pages=(total_teams + page_size - 1) // page_size,
        )

    async def get_team_roster(self, team_id: UUID) -> TeamRosterResponse:
        """Return all roster members, ordered by their persisted position."""

        if await self.session.get(Team, team_id) is None:
            raise TeamNotFoundError

        statement = (
            select(
                TeamPlayer.player_id,
                Player.first_name,
                Player.last_name,
                Player.is_active,
                TeamPlayer.roster_order,
            )
            .join(Player, Player.id == TeamPlayer.player_id)
            .where(TeamPlayer.team_id == team_id)
            .order_by(TeamPlayer.roster_order.asc(), TeamPlayer.player_id.asc())
        )
        players = [
            TeamRosterPlayerResponse(
                player_id=player_id,
                first_name=first_name,
                last_name=last_name,
                is_active=is_active,
                roster_order=roster_order,
            )
            for player_id, first_name, last_name, is_active, roster_order in (
                await self.session.execute(statement)
            ).all()
        ]
        return TeamRosterResponse(team_id=team_id, players=players)

    async def add_player_to_team(
        self,
        team_id: UUID,
        player_id: UUID,
        *,
        actor: AuditActorContext | None = None,
    ) -> TeamPlayer:
        """Add an existing player to an existing team once."""

        team = await self.session.get(Team, team_id)
        if team is None:
            raise TeamNotFoundError
        if await self.session.get(Player, player_id) is None:
            raise PlayerNotFoundError

        membership_key = {"team_id": team_id, "player_id": player_id}
        if await self.session.get(TeamPlayer, membership_key) is not None:
            raise TeamMembershipAlreadyExistsError

        last_position = int(
            await self.session.scalar(
                select(func.max(TeamPlayer.roster_order)).where(
                    TeamPlayer.team_id == team_id
                )
            )
            or 0
        )
        membership = TeamPlayer(
            **membership_key,
            roster_order=last_position + 1,
        )
        self.session.add(membership)
        try:
            await self.session.flush()
            if actor is not None:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=AuditActionType.ROSTER_ADDED,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.TEAM,
                        entity_id=team.id,
                        label=team.name,
                    ),
                    metadata={
                        "player_id": player_id,
                        "new_roster_position": membership.roster_order,
                    },
                )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise TeamMembershipAlreadyExistsError from exc
        except Exception:
            await self.session.rollback()
            raise
        await self.session.refresh(membership)
        return membership

    async def normalize_roster_order(
        self,
        team_id: UUID,
        *,
        expected_team_version: int,
        actor: AuditActorContext | None = None,
    ) -> None:
        """Normalize one valid active roster without replacing memberships."""

        try:
            team = await self.session.get(Team, team_id)
            if team is None:
                raise TeamNotFoundError

            result = await self.session.scalars(
                select(TeamPlayer)
                .where(TeamPlayer.team_id == team_id)
                .order_by(
                    TeamPlayer.roster_order.asc(),
                    TeamPlayer.player_id.asc(),
                )
            )
            memberships = list(result.all())
            player_ids = [membership.player_id for membership in memberships]
            await self._validate_roster_players(player_ids)

            expected_positions = list(range(1, len(memberships) + 1))
            if [membership.roster_order for membership in memberships] == (
                expected_positions
            ):
                raise TeamRemediationConflictError(
                    "The roster order is already normalized. Refresh the findings."
                )

            changed_player_ids = [
                membership.player_id
                for membership, position in zip(
                    memberships,
                    expected_positions,
                    strict=True,
                )
                if membership.roster_order != position
            ]
            team.version_number = await check_and_increment_version(
                self.session,
                Team,
                team_id,
                expected_team_version,
            )
            for membership, position in zip(
                memberships,
                expected_positions,
                strict=True,
            ):
                membership.roster_order = position
            await self.session.flush()

            if actor is not None:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=AuditActionType.ROSTER_REORDERED,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.TEAM,
                        entity_id=team.id,
                        label=team.name,
                    ),
                    metadata={
                        "affected_player_ids": changed_player_ids,
                        "affected_count": len(changed_player_ids),
                        "changed_positions": changed_player_ids,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    async def remove_inactive_player(
        self,
        team_id: UUID,
        player_id: UUID,
        *,
        expected_team_version: int,
        actor: AuditActorContext | None = None,
    ) -> None:
        """Remove exactly one current inactive roster membership."""

        try:
            team = await self.session.get(Team, team_id)
            if team is None:
                raise TeamNotFoundError
            player = await self.session.get(Player, player_id)
            if player is None:
                raise PlayerNotFoundError
            membership = await self.session.get(
                TeamPlayer,
                {"team_id": team_id, "player_id": player_id},
            )
            if membership is None:
                raise TeamRemediationConflictError(
                    "The selected roster membership changed. Refresh the findings."
                )
            if player.is_active:
                raise TeamRemediationConflictError(
                    "The selected player is no longer inactive. Refresh the findings."
                )

            remaining_result = await self.session.scalars(
                select(TeamPlayer.player_id)
                .where(
                    TeamPlayer.team_id == team_id,
                    TeamPlayer.player_id != player_id,
                )
                .order_by(
                    TeamPlayer.roster_order.asc(),
                    TeamPlayer.player_id.asc(),
                )
            )
            remaining_player_ids = list(remaining_result.all())
            await self._validate_roster_players(remaining_player_ids)

            team.version_number = await check_and_increment_version(
                self.session,
                Team,
                team_id,
                expected_team_version,
            )
            await self.session.execute(
                delete(TeamPlayer).where(
                    TeamPlayer.team_id == team_id,
                    TeamPlayer.player_id == player_id,
                )
            )
            await self.session.flush()
            if actor is not None:
                await BusinessAuditService(self.session).record(
                    actor=actor,
                    action_type=AuditActionType.ROSTER_REMOVED,
                    target=AuditTargetContext(
                        entity_type=AuditEntityType.TEAM,
                        entity_id=team.id,
                        label=team.name,
                    ),
                    metadata={
                        "player_id": player_id,
                        "prior_roster_position": membership.roster_order,
                    },
                )
            await self.session.commit()
        except Exception:
            await self.session.rollback()
            raise

    @staticmethod
    def _classify_team_update(
        *,
        previous_name: str,
        previous_age_group: str,
        previous_player_ids: list[UUID],
        next_name: str,
        next_age_group: str,
        next_player_ids: list[UUID],
    ) -> tuple[AuditActionType, dict[str, object]]:
        """Choose one external action and compact metadata for a replacement."""

        changed_fields = []
        if previous_name != next_name:
            changed_fields.append("name")
        if previous_age_group != next_age_group:
            changed_fields.append("age_group")

        previous_set = set(previous_player_ids)
        next_set = set(next_player_ids)
        added = [
            player_id for player_id in next_player_ids if player_id not in previous_set
        ]
        removed = [
            player_id for player_id in previous_player_ids if player_id not in next_set
        ]
        reordered = [
            player_id
            for player_id in next_player_ids
            if player_id in previous_set
            and previous_player_ids.index(player_id) != next_player_ids.index(player_id)
        ]
        roster_changed = previous_player_ids != next_player_ids

        if not changed_fields and len(added) == 1 and not removed:
            added_id = added[0]
            return AuditActionType.ROSTER_ADDED, {
                "player_id": added_id,
                "new_roster_position": next_player_ids.index(added_id) + 1,
            }
        if not changed_fields and len(removed) == 1 and not added:
            removed_id = removed[0]
            return AuditActionType.ROSTER_REMOVED, {
                "player_id": removed_id,
                "prior_roster_position": previous_player_ids.index(removed_id) + 1,
            }
        if not changed_fields and not added and not removed and reordered:
            return AuditActionType.ROSTER_REORDERED, {
                "affected_player_ids": reordered,
                "affected_count": len(reordered),
                "changed_positions": reordered,
            }

        if roster_changed:
            changed_fields.append("roster")
        return AuditActionType.TEAM_UPDATED, {
            "changed_fields": changed_fields,
            "roster_replaced": roster_changed,
            "roster_count": len(next_player_ids),
            "added_player_ids": added,
            "removed_player_ids": removed,
            "reordered_player_ids": reordered,
        }
