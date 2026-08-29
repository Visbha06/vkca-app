# Match Scoring Quickstart

This is the acceptance journey for the required backend test:
backend/tests/integration/quickstart/test_014_quickstart_flow.py

It uses the existing isolated PostgreSQL test fixture, authenticated ASGI
requests, and local fakes for background/RAG integrations. It must run
without Internet access and must not require a scorer UI.

## Prerequisites and commands

From the repository root, prepare the test database and verify the migration:

    VKCA_ENV=test uv run alembic upgrade head
    VKCA_ENV=test uv run alembic check

Run the exact quickstart:

    VKCA_ENV=test uv run pytest backend/tests/integration/quickstart/test_014_quickstart_flow.py -q

Run focused coverage:

    VKCA_ENV=test uv run pytest backend/tests/unit/test_scoring_rules.py backend/tests/unit/test_scoring_replay.py backend/tests/unit/test_scoring_authorization.py backend/tests/unit/test_scoring_projections.py backend/tests/integration/test_match_scoring_migration.py backend/tests/integration/test_match_scoring_api.py backend/tests/integration/test_match_scoring_occ.py backend/tests/integration/test_match_scoring_audit.py backend/tests/integration/test_match_scoring_background.py backend/tests/integration/test_match_scoring_compatibility.py -q

Run the request-level browser boundary:

    npm run test:e2e -- match-scoring-domain-flow.spec.ts

The Playwright journey may use an authenticated fetch sequence against the
configured local API. It does not require new scorer screens.

## Required 25-step acceptance flow

1. Apply the scoring-domain migration and verify revision 016 is at head.
2. Seed two academy Teams and their Players using the integration fixtures.
3. Create an external Match with one academy side and one external opponent,
   or create an internal Match with two distinct academy Teams.
4. Configure the fixed playing XI or Match squad through the scoring
   configuration command.
5. Configure and verify the intended batting order is fixed and unique.
6. Start the first innings with explicit striker, non-striker, and bowler
   participant IDs.
7. Record an ordinary legal delivery with ordinary runs.
8. Record a legal boundary and verify bat runs and balls faced.
9. Record a five-run batter outcome and verify the total is derived.
10. Record a multiple-run wide and verify it is illegal and does not consume
    a legal ball.
11. Record a no-ball with additional runs and verify the one-run no-ball
    penalty is represented separately.
12. Record a wicket with the required fielder participant involvement.
13. Select the next batter through the explicit transition command.
14. Complete an over using legal deliveries and verify over state and strike
    transition.
15. Query the next-bowler suggestion and verify quota and previous-over
    eligibility are deterministic.
16. Continue the innings with legal, illegal, extra, and fielding events as
    needed to exercise the read model.
17. Complete the first innings through the permitted automatic or manual
    completion path.
18. Read the derived target for the next innings.
19. Start the chase with the derived target and explicit opening selections.
20. Complete the Match through the server-derived result/completion command.
21. Read the scorecard and verify totals, extras, wickets, overs, fall of
    wickets, participant summaries, target, and result are derived from active
    delivery history.
22. Correct one earlier delivery with an explicit reason and expected active
    revision.
23. Verify the immutable revision history, replayed strike/over/wicket state,
    summaries, target/chase state, and result are correct and equivalent to a
    clean replay of the final active history.
24. Submit two concurrent writes using one stale innings version and verify
    exactly one succeeds, the other returns 409, and no duplicate active
    sequence exists.
25. Inspect background/RAG fakes and audit records: ordinary delivery entry
    performed no provider/queue work, completion/correction work is bounded
    and coalesced, meaningful commands have the expected audit events, and no
    external User, Player, Team membership, career-stat, token, or raw
    unrestricted payload was created or exposed.

## Expected acceptance signals

- Every accepted derived total and summary equals an independent fold of active
  delivery revisions.
- A current innings/scorecard read uses the persisted projection and stays
  within the local one-second target for the 1000-attempt performance case.
- A stale command returns the existing structured conflict response and leaves
  delivery, projection, audit, and outbox state unchanged.
- Correcting an earlier attempt preserves all old revisions and produces a
  replay-equivalent active state.
- Legacy unscored Matches remain readable through existing performance paths;
  scored Matches reject conflicting direct aggregate writes.
- External participants exist only under the Match-scoped participant tables.
- The journey passes with local services/fakes and no network dependency.
