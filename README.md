# VKCA App

A full-stack cricket academy management platform for **VK Cricket Academy**, built to centralize academy operations, player development, team administration, scheduling, and coaching workflows.

VKCA App combines a modern React frontend with a FastAPI backend, PostgreSQL database, and durable Redis/ARQ background processing. The application is designed around role-aware workflows for Head Coaches, Assistant Coaches, and Players, with an emphasis on accessibility, security, responsive interaction, and reliable academy data.

> **Project status:** 🚧 Under active development

---

## Features

### Authentication & Security

- Email and password authentication
- Short-lived JWT access tokens
- Rotating refresh-token sessions
- Role-based access control
- Protected frontend routes
- CSRF protection for authenticated mutations
- Login rate limiting
- Argon2id password hashing
- Configurable password and session policies
- Session revocation for deactivated users
- Authentication and security audit handling

### Player Management

- Browse and search the player directory
- View detailed player profiles
- Add new players
- Edit existing player information
- Filter players by team
- Role-aware management controls
- Responsive player-management workflows
- Accessible forms and modal interactions

### Team Management

- Browse academy teams
- Search, filter, and sort team records
- Create and update teams
- View team details and rosters
- Assign and remove players from teams
- Role-aware team administration
- Optimistic concurrency protection for conflicting updates

### Coaches Portal

- Browse Head Coach and Assistant Coach accounts
- Filter coaches by account status
- View coach profiles and team assignments
- Add new Assistant Coach accounts
- Generate one-time temporary passwords for new coaches
- Activate and deactivate coach accounts
- Revoke sessions when a coach is deactivated
- Assign coaches to academy teams
- Role-based management controls
- Responsive coach cards and accessible detail dialogs

### Academy Calendar

- Custom responsive monthly calendar
- Current-day and Today schedule views
- Practice, Game, and Miscellaneous event types
- Age-group and All Academy event scopes
- Create, edit, and delete events
- Weekly and yearly recurring events
- Edit or delete individual recurring occurrences
- Manage entire recurring series
- Recurrence exceptions for moved or deleted occurrences
- Optimistic concurrency protection
- Pacific-time academy date handling
- Role-aware event management
- Keyboard-accessible calendar navigation
- Loading, empty, error, and conflict recovery states

### Business Audit Log

- Append-only academy business activity history
- Records successful administrative and domain changes
- Tracks actor, action, entity, summary, and timestamp snapshots
- Filter by:
  - Actor
  - Category
  - Action
  - Entity
  - Date range
- Paginated audit history
- Expandable event details
- Historical snapshots remain readable after entities change
- Head Coach-only access
- Recent academy activity integration
- Separate from authentication/security audit data
- Sanitized metadata with no secrets, credentials, or raw payloads

### Cricket Data API

The backend also contains domain foundations for:

- Matches
- Player performances
- Player statistics
- Team statistics
- Users
- Players
- Teams

These APIs provide the foundation for future match-management and performance-analysis interfaces.

---

## Technology Stack

### Frontend

- **React 19**
- **TypeScript 6**
- **React Router 8**
- **Vite 8**
- **Tailwind CSS 4**
- Vitest
- React Testing Library
- Playwright
- ESLint

### Backend

- **Python 3.12+**
- **FastAPI**
- **SQLAlchemy 2**
- **PostgreSQL**
- asyncpg
- Alembic
- Pydantic
- Pydantic Settings
- Argon2
- JSON Web Tokens
- pgvector
- ARQ
- Pytest
- Ruff
- mypy
- Bandit

### Infrastructure & Tooling

- Docker Compose
- PostgreSQL 16 with pgvector
- Redis 7
- Uvicorn
- `uv` for Python dependency management
- Spec-driven development with feature specifications under `specs/`

---

## Architecture

VKCA App uses a feature-oriented full-stack architecture.

```text
Browser
   │
   ▼
React + TypeScript
   │
   │ REST / JSON
   ▼
FastAPI
   │
   ├── Routes
   ├── Services
   ├── Repositories
   ├── SQLAlchemy ───────────────► PostgreSQL
   │                                  │
   │                         durable outbox intent
   │                                  ▼
   └────────────────────────────► Redis / ARQ
                                      │
                                      ▼
                              dedicated worker
                                      │
                                      └────► registered services
```

The frontend groups domain behavior into feature modules, while the backend separates routing, business logic, persistence, validation, and database models.

---

## Repository Structure

```text
vkca-app/
├── backend/
│   ├── src/
│   │   ├── middleware/       # API middleware and request handling
│   │   ├── migrations/       # Alembic migrations
│   │   ├── models/           # SQLAlchemy models
│   │   ├── repositories/     # Database access layer
│   │   ├── routes/           # FastAPI route modules
│   │   ├── schemas/          # Request/response schemas
│   │   ├── services/         # Application and domain services
│   │   └── main.py           # FastAPI application
│   ├── tests/                # Backend tests
│   ├── alembic.ini
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── app/              # Router and application setup
│   │   ├── assets/           # Images and static assets
│   │   ├── features/
│   │   │   ├── audit/        # Business Audit Log
│   │   │   ├── auth/         # Authentication
│   │   │   ├── calendar/     # Academy calendar
│   │   │   ├── coaches/      # Coaches Portal
│   │   │   ├── players/      # Player management
│   │   │   ├── settings/     # Account/settings features
│   │   │   └── teams/        # Team management
│   │   ├── layouts/          # Application layouts
│   │   ├── pages/            # Top-level route wrappers/pages
│   │   ├── shared/           # Shared APIs, components and utilities
│   │   └── styles/           # Global styling
│   ├── e2e/                  # Playwright end-to-end tests
│   └── package.json
│
├── specs/                    # Feature specifications and plans
├── docs/                     # Supporting project documentation
├── scripts/                  # Development scripts
├── sast-reports/             # Security-analysis output
├── DESIGN.md                 # Product design guidance
├── PRODUCT.md                # Product principles and goals
├── .env.example
├── docker-compose.yml
└── README.md
```

---

## Implemented Feature Specifications

Development is organized around specification-driven feature increments.

```text
001  Cricket Backend API
002  Authentication & API Security
003  Frontend Application Shell
004  Frontend Authentication & Accounts
005  Players Interface
006  Teams Interface
007  Coaches Portal
008  Calendar Interface
009  Business Audit Log
```

Each feature directory under `specs/` contains planning and implementation artifacts used to guide development.

---

## Roles & Permissions

### Head Coach

Full academy-management access, including:

- Players
- Teams
- Coaches
- Calendar
- Business Audit Log
- Account and administrative workflows

### Assistant Coach

Operational coaching access, including:

- Player and team workflows
- Coaches Portal visibility
- Calendar viewing and event management

Administrative actions remain restricted where appropriate.

### Player

Primarily read-oriented access to academy information relevant to players.

Sensitive administrative surfaces such as the Business Audit Log and coach administration are not exposed to Player accounts.

Backend authorization remains authoritative even when controls are hidden in the frontend.

---

## Prerequisites

Install:

- Python **3.12+**
- [`uv`](https://docs.astral.sh/uv/)
- Node.js **24** or another version compatible with the locked frontend dependencies
- npm
- Docker
- Docker Compose

---

## Local Development

### 1. Clone the repository

```bash
git clone https://github.com/Visbha06/vkca-app.git
cd vkca-app
```

### 2. Configure environment variables

Copy the example environment file:

```bash
cp .env.example .env
```

Replace the placeholder database credentials and JWT secret.

Generate a secure JWT secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Example:

```env
DATABASE_URL=postgresql+asyncpg://postgres:your-password@localhost:5455/academy_db

DB_USER=postgres
DB_PASSWORD=your-password
DB_NAME=academy_db
DB_PORT=5455

JWT_SECRET=your-generated-secret
JWT_ALGORITHM=HS256

ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=30
REFRESH_INACTIVITY_DAYS=7

PASSWORD_MIN_LENGTH=12
PASSWORD_MAX_LENGTH=128
```

> Never commit `.env`.

### 3. Start PostgreSQL and Redis

From the repository root:

```bash
docker compose up -d db redis
```

Verify it is running:

```bash
docker compose ps
```

The default local configuration exposes PostgreSQL on port `5455` and Redis on
port `6379`. PostgreSQL is authoritative; Redis is a disposable execution
broker for committed background-work references.

### 4. Install backend dependencies

```bash
cd backend
uv sync --all-groups
```

### 5. Apply database migrations

```bash
uv run alembic upgrade head
```

### 6. Start the backend

```bash
uv run uvicorn src.main:app --reload
```

The API is available at:

```text
http://localhost:8000
```

Useful endpoints:

```text
Swagger UI:      http://localhost:8000/docs
OpenAPI schema:  http://localhost:8000/openapi.json
Health check:    http://localhost:8000/api/v1/health
```

### 7. Start the background worker

In another terminal, from `backend/`:

```bash
uv run python -m scripts.background_worker
```

The worker consumes only explicitly registered jobs. Domain mutations commit
their minimal work intent to PostgreSQL first, so Redis or provider downtime
delays derived-data freshness without rolling back academy data. To run the
worker in Docker instead, use this from the repository root:

```bash
docker compose up -d db redis worker
```

### 8. Install frontend dependencies

In another terminal:

```bash
cd frontend
npm install
```

### 9. Start the frontend

```bash
npm run dev
```

The application normally runs at:

```text
http://localhost:5173
```

The development frontend uses:

```text
http://localhost:8000
```

as its default backend API origin.

To override it:

```env
VITE_API_BASE_URL=https://your-api.example.com
```

---

## API Overview

Application endpoints use the `/api/v1` prefix.

Major API areas include:

```text
/api/v1/auth
/api/v1/users
/api/v1/players
/api/v1/teams
/api/v1/coaches
/api/v1/calendar
/api/v1/business-audit
/api/v1/matches
/api/v1/performances
/api/v1/stats
/api/v1/health
```

See the generated Swagger documentation at `/docs` for current schemas and operations.

---

## Authentication Model

VKCA App uses a split-token session model:

1. The user authenticates with email and password.
2. The backend issues a short-lived access token.
3. Refresh credentials maintain the longer-lived authenticated session.
4. The frontend keeps the access token in application memory.
5. Refresh credentials use secure cookie handling.
6. Authenticated mutations include CSRF protection.
7. Refresh sessions rotate during renewal.
8. Expired or revoked sessions return users to authentication.
9. Role authorization is enforced by the backend.

Passwords are hashed with **Argon2id** and are never stored in plaintext.

---

## Testing & Quality

### Backend

Run the backend test suite:

```bash
cd backend
uv run pytest
```

Lint:

```bash
uv run ruff check .
```

Check formatting:

```bash
uv run ruff format --check .
```

Apply formatting:

```bash
uv run ruff format .
```

Type checking:

```bash
uv run mypy src
```

Security scanning:

```bash
uv run bandit -c pyproject.toml -r src
```

### Frontend

```bash
cd frontend
```

Lint:

```bash
npm run lint
```

Unit and component tests:

```bash
npm test
```

Production build:

```bash
npm run build
```

End-to-end tests:

```bash
npm run test:e2e
```

Preview the production build:

```bash
npm run preview
```

---

## Database Migrations

Create a migration:

```bash
cd backend
uv run alembic revision --autogenerate -m "describe the change"
```

Apply migrations:

```bash
uv run alembic upgrade head
```

PostgreSQL data is persisted through the Docker volume:

```text
postgres_data
```

Stop services without deleting database data:

```bash
docker compose down
```

Delete the local database volume:

```bash
docker compose down -v
```

> **Warning:** `docker compose down -v` permanently deletes the local development database.

---

## Background Processing

Inspect, dispatch, recover, or retry durable work from `backend/` with bounded
operator commands:

```bash
uv run python -m scripts.background_jobs status --limit 50
uv run python -m scripts.background_jobs dispatch --limit 50
uv run python -m scripts.background_jobs recover --limit 50
uv run python -m scripts.background_jobs retry --work-id <uuid>
```

Approved RAG reconciliation triggers use stable registered source references:

```bash
uv run python -m scripts.background_jobs trigger-rag \
  --source-type player_profile --source-key <stable-source-key>
uv run python -m scripts.background_jobs trigger-rag --safety
```

These commands emit sanitized operational projections and never accept
arbitrary job payloads. The existing `scripts.rag_index` CLI remains available
for independent full, targeted, incremental, repair, and status recovery.
Architecture, retry behavior, configuration, extension guidance, and the
verified local workflow are documented in
[`docs/background-jobs.md`](docs/background-jobs.md).

---

## Design & Accessibility

The application targets **WCAG 2.1 AA** and emphasizes:

- Complete keyboard operation
- Visible focus states
- Accessible dialogs and forms
- Semantic page structure
- Screen-reader-compatible status feedback
- Reduced-motion support
- Responsive mobile layouts
- Touch-friendly controls
- Readable contrast
- Status communication that does not rely on color alone

The interface intentionally avoids decorative dashboard patterns that interfere with common academy workflows. The goal is a direct, operational experience centered on player development and day-to-day coaching work.

See:

- `DESIGN.md`
- `PRODUCT.md`

for additional design and product guidance.

---

## Development Workflow

Larger features follow a specification-driven workflow:

```text
Feature idea
    ↓
Specification
    ↓
Implementation plan
    ↓
Task breakdown
    ↓
Development
    ↓
Testing & validation
    ↓
UI/UX and security audit
    ↓
Pull request
```

Feature documentation is stored in `specs/`.

---

## Roadmap

Upcoming areas include:

- Match-management frontend workflows
- Player performance entry and analysis
- Rich player and team statistics
- Expanded dashboard analytics
- Training and development insights
- Production deployment
- CI/CD automation
- Academy-data search
- AI-assisted academy insights using the existing vector-capable data stack

---

## Contributing

1. Create a branch from `main`.
2. Keep changes focused.
3. Add or update relevant tests.
4. Run applicable frontend and backend checks.
5. Commit with a descriptive message.
6. Open a pull request targeting `main`.

For substantial features, create or update the corresponding specification under `specs/`.

---

## Author

Developed by [Vishal Bhat](https://github.com/Visbha06).
