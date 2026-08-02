# Cricket Team Management Backend API

The cricket backend is a FastAPI service for maintaining player profiles, user
accounts, teams and rosters, matches, match performances, and format-specific
career statistics. PostgreSQL is the system of record, and all endpoints are
served below `/api/v1`.

## Core workflows

1. Create players, teams, users, and matches through their collection
   endpoints.
2. Add an existing active player to a team with
   `POST /teams/{team_id}/players/{player_id}`. Duplicate membership returns
   HTTP 409.
3. Submit one match's player performances as a batch with
   `POST /matches/{match_id}/performances`. Batting, bowling, and fielding are
   independently optional for each player, but at least one group is required.
4. Read a player's accumulated batting or bowling statistics, optionally
   filtered by match format.
5. Update a player with its current `version_number`. A stale update returns
   HTTP 409 and writes a conflict entry to `data_sync_logs`.

Performance batches are atomic: all referenced players and the match are
validated before any performance is persisted. The three performance tables
and affected batting/bowling aggregate rows commit together. Any validation or
database failure rolls back the entire batch.

Each performance batch may contain 1–30 distinct players. The limit represents
two complete 15-player academy rosters and is enforced during request
validation, before database work begins. Batting, bowling, and fielding notes
are each limited to 1,000 characters.

## API surface

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Check API availability |
| POST, GET | `/players` | Create and list active players |
| GET, PUT | `/players/{player_id}` | Retrieve or version-update one player |
| POST, GET | `/users` | Create and list user accounts |
| POST, GET | `/teams` | Create and list teams |
| POST | `/teams/{team_id}/players/{player_id}` | Add a player to a roster |
| POST, GET | `/matches` | Create and list matches |
| POST | `/matches/{match_id}/performances` | Submit an atomic performance batch |
| GET | `/players/{player_id}/stats/batting` | Read batting aggregates |
| GET | `/players/{player_id}/stats/bowling` | Read bowling aggregates |

All entity responses include server-generated UTC `created_at` and
`updated_at` timestamps plus a `version_number`. Request schemas ignore
client-supplied timestamps. Player lists exclude inactive profiles, while a
direct player lookup and historical statistics remain available.

## Configuration and local operation

Set `DATABASE_URL` in `backend/.env`; the expected form is shown in
`backend/.env.example`. The repository's `docker-compose.yml` starts the
PostgreSQL 16 pgvector image configured by root-level `DB_USER`, `DB_PASSWORD`,
`DB_NAME`, and `DB_PORT` values.

From `backend/`, apply migrations and start the API:

```bash
uv run alembic upgrade head
uv run uvicorn src.main:app --reload
```

Run quality and verification gates with:

```bash
uv run ruff check .
uv run --group test pytest
```

The full request sequence and expected responses are documented in
`specs/001-cricket-backend-api/quickstart.md`.
