# Match Scoring Quickstart

This is the acceptance journey for the required backend test:
`backend/tests/integration/quickstart/test_014_quickstart_flow.py`.

The journey is one shared 25-step flow parameterized over two fixtures: a
canonical `T20` internal Match and a canonical `T20` external Match. Execute
the same steps for both variants; do not choose only one. The internal fixture has two academy sides.
The external fixture has one academy side and one match-scoped opposition side.
The flow uses authenticated ASGI requests, an isolated Docker PostgreSQL test
fixture, and local fakes for background/RAG integrations. It must run without
Internet access and must not require a scorer UI.

## Prerequisites and commands

From the repository root, prepare the backend test database and verify the
feature migration:

    cd backend
    VKCA_ENV=test uv run alembic upgrade head
    VKCA_ENV=test uv run alembic check

Run the parameterized 25-step quickstart for both Match variants:

    VKCA_ENV=test uv run pytest tests/integration/quickstart/test_014_quickstart_flow.py -q

Run focused backend unit and integration coverage:

    VKCA_ENV=test uv run pytest tests/unit/test_scoring_rules.py tests/unit/test_scoring_replay.py tests/unit/test_scoring_authorization.py tests/unit/test_scoring_projections.py tests/unit/test_scoring_commands.py tests/unit/test_scoring_bowler_commands.py tests/unit/test_scoring_correction_commands.py tests/unit/test_scoring_completion_commands.py tests/unit/test_scoring_public_handlers.py tests/unit/test_scoring_data_quality.py tests/integration/test_match_scoring_migration.py tests/integration/test_match_scoring_api.py tests/integration/test_match_scoring_occ.py tests/integration/test_match_scoring_audit.py tests/integration/test_match_scoring_background.py tests/integration/test_match_scoring_compatibility.py -q

Run the frontend/static-analysis and request-level browser boundary from the
repository root:

    cd ../frontend
    npm run lint
    npx tsc -p tsconfig.app.json --noEmit --pretty false
    npx tsc -p tsconfig.node.json --noEmit --strict --pretty false
    npm run test:e2e -- e2e/match-scoring-domain-flow.spec.ts --project=chromium

The app TypeScript configuration has `strict: true` and includes `e2e`, so the
app check validates the Playwright test file. The explicit `--strict` override
also makes the Node configuration check strict while validating
`vite.config.ts`, `vitest.config.ts`, and `playwright.config.ts`. The browser
journey uses the existing authenticated request-level pattern and does not
require new scorer screens.

The shared 25-step journey remains canonical `T20` coverage. Focused backend
policy tests additionally configure one-day with a 240-ball innings limit and
verify its derived 48-ball quota, rejection of missing/non-divisible limits or
client-supplied quotas, and Test next-bowler exclusion after every completed
over. Neither focused fixture assumes a fixed one-day innings length or permits
a Test bowler to take consecutive overs.

## Required 25-step acceptance flow

Run each step once for the internal fixture and once for the external fixture.
Both fixtures use the locked `T20` capability and the two-side innings sequence
`[A, B]`; the sequence is stored/serialized with the configured side codes,
while the API, domain, policy, and persisted format identifier is `T20`.

1. Apply migration 016 and verify it is at the database head.
2. Seed two academy Teams and their Players using isolated fixtures.
3. Create the internal Match fixture and the external Match fixture.
4. Configure the internal Match with two academy sides and the external Match
   with one academy side plus one external opponent side.
5. Configure each fixed playing XI/Match squad and verify the participant
   identity rules: academy Players are direct references; opposition entries
   contain only Match-scoped scoring identity fields.
6. Lock the canonical `T20` capability and verify 120 legal balls per innings,
   six-ball overs, 24 legal balls per bowler, ten wickets, two innings in
   `[A, B]` order, automatic target mode, one-wicket-per-delivery validation,
   and the listed completion/result codes.
7. Start innings 1 with explicit striker, non-striker, and bowler participant
   IDs.
8. Record an ordinary legal delivery with ordinary runs.
9. Record a legal boundary and verify bat runs, balls faced, and boundary
   derivation.
10. Record a five-run batter outcome and verify the total is derived without a
    boundary classification.
11. Record a multiple-run wide and verify it is illegal and does not consume a
    legal ball or bowler quota.
12. Record a no-ball with additional permitted runs and verify the one-run
    no-ball penalty is represented separately.
13. Record one caught wicket with exactly one ordered `catcher` in `fielders[]`,
    verify any exposed primary-fielder pointer is derived from that first row,
    then submit a duplicate/conflicting wicket shape and verify the whole
    request is rejected without a partial event.
14. Exercise both retired-hurt branches across the two parameterized fixtures:
    on the internal fixture, record `retired_hurt`, verify no team wicket,
    verify delivery append is blocked while the batting vacancy exists, and
    select an eligible unused next batter so the innings remains `in_progress`
    with two active batters, and verify `blocking_state.kind` changes from
    `awaiting_next_batter` to `none`; on the external fixture, record `retired_hurt`,
    verify no team wicket, and commit `retired_hurt_return` so the same
    MatchParticipant becomes active again, the innings remains `in_progress`,
    and no new identity or wicket is created.
15. Complete an over using legal deliveries and verify over state and strike
    transition.
16. Query the next-bowler suggestion and verify quota, previous-over
    preference, and eligibility reasons are deterministic.
17. Continue innings 1 with legal, illegal, extra, and fielding events as
    needed to exercise the read model.
18. Complete innings 1 through the `T20` `all_out` or `legal_ball_limit` path.
19. Read the derived target for innings 2 and verify it equals innings 1's
    completed total plus one.
20. Start innings 2 with the derived target and explicit opening selections.
21. Complete the chase by reaching the target and verify automatic innings and
    Match completion with win-by-wickets details.
22. Read each scorecard and verify totals, extras, wickets, overs, fall of
    wickets, participant summaries, target, result, capability, projection
    revision, and canonical `blocking_state` are derived from active delivery
    history.
23. After Match completion, correct one earlier second-innings delivery with
    an explicit reason and expected Match/Innings/revision versions, choosing a
    valid replacement that preserves target reach; verify the transactional
    `correction_reprocessing` phase is not externally visible, the Match remains
    `completed`, immutable provenance is preserved, and deterministic replay
    rebuilds the active state. Separate correction tests cover the valid
    non-terminal `in_progress` outcome.
24. Submit two concurrent writes using one stale innings version and verify
    exactly one succeeds, the other returns 409, and no duplicate active
    sequence exists.
25. As Head Coach, inspect Data Quality, background/RAG fakes, and audit
    records: ordinary delivery entry performed no provider/queue work;
    completion/correction work is bounded and coalesced; scoring findings are
    visible but read-only; Assistant Coach and Player requests for findings are
    rejected with 403; only allowlisted scoring commands have expected audit
    events; and the
    external run created or exposed no User, Player, Team membership,
    career-stat, token, or raw unrestricted payload.

## Internal and external variant differences

The scoring, replay, capability, completion, and result assertions are shared.
Only identity and authorization fixtures differ:

- Internal: both sides reference distinct academy Teams, all selected
  participants reference existing academy Players, and current Team scope is
  checked for the relevant academy sides.
- External: exactly one side references an academy Team; opposition participants
  and fielders use Match-scoped identities only. No opposition User, academy
  Player, Team membership, authentication field, or career-stat row is created,
  and the external side never grants authorization.

## Expected acceptance signals

- Every accepted derived total and summary equals an independent fold of active
  delivery revisions and anchored transition events.
- A current innings/scorecard read uses the persisted projection and meets the
  SC-002 benchmark protocol: one cold diagnostic read, five warm-ups, 30 warm
  reads, and at least 29 individual warm reads completing in one second or less
  for the 1,000-attempt fixture.
- A stale command returns the existing structured conflict response and leaves
  delivery, projection, audit, and outbox state unchanged.
- Correcting an earlier attempt preserves all old revisions, supersedes the
  prior active revision with one appended replacement, and produces a
  replay-equivalent active state. A completed Match correction either remains
  `completed` or, when the corrected history is compatible but non-terminal,
  becomes `in_progress` with result `pending`; an incompatible later transition
  leaves the affected Innings `reconciliation_required`. The internal
  reprocessing phase is never a committed response state, and arbitrary undo is
  not an endpoint in this feature.
- Match-level abandonment is not used as an innings completion step. Its
  dedicated completion tests set Match `abandoned`/`no_result`, leave the
  current Innings pending or in progress without an innings completion event,
  and expose `blocking_state.kind = match_abandoned`.
- Legacy unscored Matches remain readable through existing performance paths;
  scored Matches reject conflicting direct aggregate writes.
- Head-Coach-only Data Quality scoring findings report mismatches,
  duplicate/conflicting active state, invalid identities/lifecycle,
  reconciliation-required state, and legacy divergence without repairing
  scoring projections or writing scoring-audit/outbox records; Assistant
  Coaches and Players cannot view or re-run them, and existing non-scoring
  remediation remains a separate Head-Coach-only path.
- External participants exist only under Match-scoped participant tables.
- The journey passes with local services/fakes and no network dependency.
