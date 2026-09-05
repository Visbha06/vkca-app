"""Build and persist replayable Innings read models."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from src.enums import ParticipationState, ScoringDismissalType
from src.models.scoring.innings import Innings
from src.models.scoring.over import InningsOver
from src.models.scoring.participant_summary import InningsParticipantSummary
from src.services.scoring.replay import ReplayState


@dataclass(frozen=True, slots=True)
class OverProjection:
    over_number: int
    bowler_participant_id: UUID
    legal_ball_count: int
    total_runs: int
    runs_conceded: int
    wickets: int
    is_complete: bool


@dataclass(frozen=True, slots=True)
class ParticipantProjection:
    participant_id: UUID
    participation_state: ParticipationState
    dismissal_type: ScoringDismissalType | None
    batting_runs: int
    balls_faced: int
    fours: int
    sixes: int
    bowling_legal_balls: int
    bowling_overs_completed: int
    bowling_balls_in_partial_over: int
    runs_conceded: int
    bowling_wickets: int
    wides: int
    no_balls: int
    fielding_dismissals: int


@dataclass(frozen=True, slots=True)
class InningsProjection:
    total_runs: int
    legal_balls: int
    wickets_lost: int
    striker_participant_id: UUID | None
    non_striker_participant_id: UUID | None
    current_bowler_participant_id: UUID | None
    target_runs: int | None
    state_snapshot: dict[str, object]
    overs: tuple[OverProjection, ...]
    participant_summaries: tuple[ParticipantProjection, ...]


def build_innings_projection(
    state: ReplayState,
    *,
    over_length_legal_balls: int,
) -> InningsProjection:
    """Convert pure replay output into deterministic persistence values."""

    overs = tuple(
        OverProjection(
            over_number=value.over_number,
            bowler_participant_id=value.bowler_participant_id,
            legal_ball_count=value.legal_ball_count,
            total_runs=value.total_runs,
            runs_conceded=value.runs_conceded,
            wickets=value.wickets,
            is_complete=value.is_complete,
        )
        for _, value in sorted(state.overs.items())
    )
    summaries = tuple(
        ParticipantProjection(
            participant_id=participant_id,
            participation_state=value.participation_state,
            dismissal_type=value.dismissal_type,
            batting_runs=value.batting_runs,
            balls_faced=value.balls_faced,
            fours=value.fours,
            sixes=value.sixes,
            bowling_legal_balls=value.bowling_legal_balls,
            bowling_overs_completed=(
                value.bowling_legal_balls // over_length_legal_balls
            ),
            bowling_balls_in_partial_over=(
                value.bowling_legal_balls % over_length_legal_balls
            ),
            runs_conceded=value.runs_conceded,
            bowling_wickets=value.bowling_wickets,
            wides=value.wides,
            no_balls=value.no_balls,
            fielding_dismissals=value.fielding_dismissals,
        )
        for participant_id, value in sorted(
            state.participants.items(), key=lambda item: str(item[0])
        )
    )
    snapshot: dict[str, object] = {
        "over_progress": {
            "over_length_legal_balls": over_length_legal_balls,
            "overs_completed": state.legal_balls // over_length_legal_balls,
            "balls_in_partial_over": state.legal_balls % over_length_legal_balls,
            "next_ball_in_over": state.legal_balls % over_length_legal_balls + 1,
        },
        "completed_bowler_participant_ids": [
            str(over.bowler_participant_id) for over in overs if over.is_complete
        ],
        "opening_selections": {
            "striker_participant_id": str(state.opening_striker_participant_id),
            "non_striker_participant_id": str(state.opening_non_striker_participant_id),
            "bowler_participant_id": str(state.opening_bowler_participant_id),
        },
        "blocking_state": state.blocking_state.as_dict(),
        "extras": dict(state.extras),
        "fall_of_wickets": list(state.fall_of_wickets),
        "target": {
            "target_runs": state.target_runs,
            "runs_required": (
                max(0, state.target_runs - state.total_runs)
                if state.target_runs is not None
                else None
            ),
        },
    }
    return InningsProjection(
        total_runs=state.total_runs,
        legal_balls=state.legal_balls,
        wickets_lost=state.wickets_lost,
        striker_participant_id=state.striker_participant_id,
        non_striker_participant_id=state.non_striker_participant_id,
        current_bowler_participant_id=state.current_bowler_participant_id,
        target_runs=state.target_runs,
        state_snapshot=snapshot,
        overs=overs,
        participant_summaries=summaries,
    )


async def persist_innings_projection(
    session: AsyncSession,
    innings: Innings,
    state: ReplayState,
    *,
    over_length_legal_balls: int,
) -> InningsProjection:
    """Replace rebuildable rows and update the Innings root in one transaction."""

    projection = build_innings_projection(
        state,
        over_length_legal_balls=over_length_legal_balls,
    )
    next_revision = innings.projection_revision + 1
    innings.lifecycle_state = state.lifecycle_state
    innings.striker_participant_id = projection.striker_participant_id
    innings.non_striker_participant_id = projection.non_striker_participant_id
    innings.current_bowler_participant_id = projection.current_bowler_participant_id
    innings.legal_balls = projection.legal_balls
    innings.total_runs = projection.total_runs
    innings.wickets_lost = projection.wickets_lost
    innings.target_runs = projection.target_runs
    innings.state_snapshot = projection.state_snapshot
    innings.projection_revision = next_revision

    await session.execute(
        delete(InningsOver).where(InningsOver.innings_id == innings.id)
    )
    await session.execute(
        delete(InningsParticipantSummary).where(
            InningsParticipantSummary.innings_id == innings.id
        )
    )
    session.add_all(
        [
            InningsOver(
                innings_id=innings.id,
                projection_revision=next_revision,
                **{
                    field: getattr(over, field)
                    for field in (
                        "over_number",
                        "bowler_participant_id",
                        "legal_ball_count",
                        "total_runs",
                        "runs_conceded",
                        "wickets",
                        "is_complete",
                    )
                },
            )
            for over in projection.overs
        ]
    )
    session.add_all(
        [
            InningsParticipantSummary(
                innings_id=innings.id,
                projection_revision=next_revision,
                **{
                    field: getattr(summary, field)
                    for field in (
                        "participant_id",
                        "participation_state",
                        "dismissal_type",
                        "batting_runs",
                        "balls_faced",
                        "fours",
                        "sixes",
                        "bowling_legal_balls",
                        "bowling_overs_completed",
                        "bowling_balls_in_partial_over",
                        "runs_conceded",
                        "bowling_wickets",
                        "wides",
                        "no_balls",
                        "fielding_dismissals",
                    )
                },
            )
            for summary in projection.participant_summaries
        ]
    )
    entry_by_participant = {
        entry.participant_id: entry for entry in innings.batting_entries
    }
    for summary in projection.participant_summaries:
        entry = entry_by_participant.get(summary.participant_id)
        if entry is not None:
            entry.participation_state = summary.participation_state
    return projection


build_projection = build_innings_projection


__all__ = [
    "InningsProjection",
    "OverProjection",
    "ParticipantProjection",
    "build_innings_projection",
    "build_projection",
    "persist_innings_projection",
]
