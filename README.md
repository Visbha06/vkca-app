# VKCA App

A full-stack cricket academy management platform for the **VK Cricket Academy**.

VKCA App provides a central system for managing academy users, players, teams, matches, performances, and cricket statistics. It combines a FastAPI backend with a responsive React frontend and a PostgreSQL database.

> **Project status:** Under active development.

## Features

### Authentication and security

* Email and password authentication
* JWT access tokens
* Rotating refresh-token sessions
* Role-based access control
* Protected frontend routes
* CSRF protection for authenticated mutations
* Login rate limiting
* Secure Argon2id password hashing
* Configurable password and session policies

### Player management

* Browse and search the player directory
* View detailed player profiles
* Add new players
* Edit existing player information
* Filter players by team
* Role-aware management controls

### Team management

* Browse academy teams
* Create and update teams
* View team details and rosters
* Assign players to teams
* Search, filter, and sort team records

### Cricket data

The backend contains API modules for:

* Matches
* Player performances
* Player and team statistics
* Users
* Players
* Teams

### Frontend experience

* Responsive application layout
* Collapsible navigation sidebar
* Authentication-aware routing
* Dashboard and academy navigation
* Player and team management interfaces
* Calendar, coaches, and settings routes
* Accessible forms, dialogs, tables, and navigation
* Automatic session refresh and expiry handling

## Technology Stack

### Frontend

* React 19
* TypeScript
* Vite
* React Router
* Tailwind CSS
* Vitest
* React Testing Library
* Playwright
* ESLint

### Backend

* Python 3.12+
* FastAPI
* SQLAlchemy
* PostgreSQL
* asyncpg
* Alembic
* Pydantic
* Pydantic Settings
* Argon2
* JSON Web Tokens
* pgvector
* Pytest
* Ruff
* mypy
* Bandit

### Infrastructure

* Docker Compose
* PostgreSQL 16 with pgvector
* Uvicorn

## Repository Structure

```text
vkca-app/
├── backend/
│   ├── src/
│   │   ├── middleware/       # API middleware and error handling
│   │   ├── migrations/       # Alembic database migrations
│   │   ├── models/           # SQLAlchemy database models
│   │   ├── repositories/     # Database access layer
│   │   ├── routes/           # FastAPI route modules
│   │   ├── schemas/          # Request and response schemas
│   │   ├── services/         # Application and security services
│   │   └── main.py           # FastAPI application entry point
│   ├── tests/                # Backend test suite
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── app/              # Application setup and routing
│   │   ├── features/         # Feature-oriented application modules
│   │   │   ├── auth/
│   │   │   ├── players/
│   │   │   ├── settings/
│   │   │   └── teams/
│   │   ├── layouts/          # Shared page layouts
│   │   ├── pages/            # Top-level application pages
│   │   └── shared/           # Shared API, components, and utilities
│   ├── e2e/                  # Playwright end-to-end tests
│   ├── package.json
│   └── vite.config.ts
├── specs/                    # Feature specifications and implementation plans
├── .env.example              # Example local environment configuration
├── docker-compose.yml        # Local PostgreSQL service
└── README.md
```

## Prerequisites

Install the following before running the application:

* Python 3.12 or newer
* [uv](https://docs.astral.sh/uv/)
* Node.js 24 or another version compatible with the locked frontend dependencies
* npm
* Docker and Docker Compose

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

Replace the placeholder values in `.env`, particularly the database password and JWT secret.

Generate a secure JWT secret with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

A local configuration can resemble:

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

Do not commit your `.env` file.

### 3. Start PostgreSQL

From the repository root:

```bash
docker compose up -d db
```

The default development configuration exposes PostgreSQL on port `5455`.

To verify that the container is running:

```bash
docker compose ps
```

### 4. Install backend dependencies

```bash
cd backend
uv sync --all-groups
```

### 5. Apply database migrations

From the `backend` directory:

```bash
uv run alembic upgrade head
```

### 6. Start the backend

```bash
uv run uvicorn src.main:app --reload
```

The backend will be available at:

```text
http://localhost:8000
```

Useful development endpoints:

```text
API documentation: http://localhost:8000/docs
OpenAPI schema:    http://localhost:8000/openapi.json
Health check:      http://localhost:8000/api/v1/health
```

### 7. Install frontend dependencies

Open another terminal:

```bash
cd frontend
npm install
```

### 8. Start the frontend

```bash
npm run dev
```

The frontend will normally be available at:

```text
http://localhost:5173
```

During development, the frontend uses `http://localhost:8000` as its default API origin.

To use another backend origin, set:

```env
VITE_API_BASE_URL=https://your-api.example.com
```

## Development Commands

### Backend

Run the backend test suite:

```bash
cd backend
uv run pytest
```

Run lint checks:

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

Run static type checking:

```bash
uv run mypy src
```

Run the Bandit security scanner:

```bash
uv run bandit -c pyproject.toml -r src
```

Create a new database migration:

```bash
uv run alembic revision --autogenerate -m "describe the change"
```

Apply all migrations:

```bash
uv run alembic upgrade head
```

### Frontend

Run the development server:

```bash
cd frontend
npm run dev
```

Create a production build:

```bash
npm run build
```

Run lint checks:

```bash
npm run lint
```

Run unit and component tests:

```bash
npm test
```

Run end-to-end tests:

```bash
npm run test:e2e
```

Preview the production build:

```bash
npm run preview
```

## API Overview

All application endpoints use the `/api/v1` prefix.

Major API groups include:

```text
/api/v1/auth
/api/v1/users
/api/v1/players
/api/v1/teams
/api/v1/matches
/api/v1/performances
/api/v1/stats
/api/v1/health
```

Refer to the generated Swagger documentation at `/docs` for the current request schemas, response models, and available operations.

## Authentication Model

The application uses a split-token authentication model:

* Short-lived access tokens authorize API requests.
* Refresh sessions allow access tokens to be renewed.
* Refresh credentials are sent using secure cookies.
* The frontend stores the access token in application memory.
* Mutating requests include CSRF protection.
* Expired sessions redirect users back to the login page.
* Authorization rules restrict operations according to the authenticated user’s role.

## Testing

The repository includes several levels of automated testing:

* Backend unit and API tests with Pytest
* Frontend unit and component tests with Vitest
* UI behavior tests with React Testing Library
* End-to-end browser tests with Playwright
* Backend linting and formatting with Ruff
* Frontend linting with ESLint
* Backend security checks with Bandit

Before submitting changes, run the relevant backend and frontend checks:

```bash
cd backend
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

```bash
cd frontend
npm run lint
npm test
npm run build
npm run test:e2e
```

## Database Management

PostgreSQL data is persisted in the Docker volume named `postgres_data`.

Stop the database without deleting its data:

```bash
docker compose down
```

Stop the database and delete its local data:

```bash
docker compose down -v
```

> Deleting the volume permanently removes the local development database.

## Contributing

1. Create a branch from `main`.
2. Make a focused set of changes.
3. Add or update relevant tests.
4. Run the backend and frontend quality checks.
5. Commit the changes with a descriptive message.
6. Open a pull request targeting `main`.

The project uses feature specifications and implementation plans under `specs/` to guide larger changes.

## Roadmap

Planned development areas include:

* Expanded match and training-session workflows
* Deeper player-performance analytics
* Coach and staff management
* Calendar integration
* Production deployment and CI/CD
* Academy-data search and AI-assisted insights

## Author

Developed by [Vishal Bhat](https://github.com/Visbha06).
