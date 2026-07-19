  <!--
    Sync Impact Report
    ==================
    Version change: 1.2.0 → 1.3.0 (MINOR — materially expanded guidance under
    VIII. UX Completeness in Specs + wording clarification under V. Testing
    Discipline)
    Modified principles:
      - V. Testing Discipline — narrowed Quickstart validation scope to backend
        operations only
      - VIII. UX Completeness in Specs — added mandatory frontend design
        references (PRODUCT.md + DESIGN.md)
    Added sections: N/A
    Removed sections: N/A
    Templates requiring updates:
      - .specify/templates/plan-template.md: ✅ aligned (no change needed)
      - .specify/templates/spec-template.md: ✅ aligned (no change needed)
      - .specify/templates/tasks-template.md: ✅ aligned (quickstart task already
        scoped to backend path)
    Follow-up TODOs: None
  -->

# VKCA App Constitution

## Core Principles

### I. Clean Code

All code MUST be readable, maintainable, and self-documenting.

- Functions and components MUST have a single responsibility.
- Naming MUST be descriptive and consistent across the codebase.
- Dead code, commented-out blocks, and unused imports MUST be removed before
  merging.
- Code review feedback addressing readability or structure MUST be resolved
  before approval.

### II. Simple UX

User interfaces MUST be intuitive and require no explanation.

- Every screen MUST have a clear primary action.
- Workflows MUST minimize steps — if a common task takes more than three
  clicks or inputs, it is a design smell.
- Avoid premature feature additions; default to the simplest interaction that
  solves the user's need.

### III. Responsive Design

All user-facing components MUST adapt to viewport sizes from 320px (mobile)
to 2560px (desktop).

- Layouts MUST use standard Tailwind CSS spacing scales and breakpoint
  prefixes (`sm:`, `md:`, `lg:`, `xl:`, `2xl:`).
- Hardcoded pixel values (`px`, absolute `rem` not derived from the scale) are
  FORBIDDEN in component stylesheets and Tailwind arbitrary values.
- Components MUST be tested at mobile and desktop breakpoints.

### IV. Minimal Dependencies

Backend dependencies MUST be managed with `uv add` and `uv remove`.

- Dependency groups (e.g., `dev`, `test`) MUST be respected — production
  dependencies SHALL NOT leak into dev groups and vice versa.
- Every new dependency MUST justify its inclusion: a comment in
  `pyproject.toml` or the PR description explaining what problem it solves
  and why existing dependencies are insufficient.
- Prefer standard library and existing project dependencies over new
  additions.

### V. Testing Discipline

- **Unit tests are MANDATORY** for all new backend and frontend logic. Every
  public function, API endpoint handler, and React component with state or
  user interaction MUST have corresponding unit tests.
- **Integration tests are OPTIONAL** — write them only when the spec
  explicitly requires cross-module or cross-service verification.
- **One E2E test per spec**: Every feature spec MUST include at least one
  end-to-end test using Playwright, covering the primary user journey.
- **Mocking**: Use `pytest-mock` for backend tests. Mocks MUST isolate the
  unit under test from external services, databases, and network calls. Tests
  MUST be runnable locally without an active Internet connection or external
  service dependencies.
- **Test isolation**: Each test MUST set up its own state and clean up after
  itself. No test SHALL depend on the side effects of another test.
- **Quickstart validation for backend**: Every backend feature spec planned via
  `/speckit-plan` generates a `quickstart.md`. The associated quickstart test
  MUST live in `backend/tests/integration/quickstart/` and MUST be named
  `test_<spec_num>_quickstart_flow.py` (e.g., `test_001_quickstart_flow.py`).
  The test MUST validate the steps described in `quickstart.md` end-to-end.

### VI. MCP Server Priority

When exploring code structure or searching for literal strings, prioritize
MCP servers over raw shell commands:

- Use `codebase-memory-mcp` for understanding code structure, module
  relationships, and architectural patterns.
- Use `mcp-ripgrep` for literal string lookups, symbol searches, and pattern
  matching across the codebase.

Fall back to direct shell tools only when the MCP server cannot satisfy the
query.

### VII. Database Schema Migrations

Every database schema change (new tables, altered columns, index
modifications, constraint changes) MUST include a migration script.

- Migration scripts MUST be versioned, reversible where possible, and applied
  to the database before the corresponding application code is deployed.
- Manual schema edits outside the migration framework are FORBIDDEN.
- Migrations MUST be tested against a local PostgreSQL instance (Docker)
  before merging.

### VIII. UX Completeness in Specs

Feature specifications MUST include information on UI appearance and behavior
for all user-facing elements:

- Layout descriptions, interaction states (loading, empty, error, success),
  responsive behavior, and accessibility considerations.
- The `/clarify` and `/analyze` workflows MUST flag any missing UI details.
- Specs without sufficient UX detail SHALL NOT proceed to implementation.
- **Frontend design references**: When designing the frontend, the agent MUST
  refer to `PRODUCT.md` and `DESIGN.md` in the project root for brand
  personality, design principles, color palettes, typography, component
  patterns, and do's/don'ts. Frontend implementation that contradicts these
  design documents SHALL NOT be accepted.

### IX. Optimistic Concurrency Control

All code MUST be written with concurrency in mind.

- Database operations MUST use optimistic locking (version columns,
  timestamps, or equivalent) where multiple clients may write to the same
  resource.
- API endpoints MUST return appropriate conflict responses (HTTP 409) when a
  write cannot proceed due to a version mismatch.
- Frontend state management MUST handle stale data and conflict resolution
  gracefully.
- Assume concurrent access by default — single-user assumptions MUST be
  explicitly documented and justified.

### X. Strongly-Typed API Boundaries

Frontend TypeScript models MUST strictly mirror the Pydantic schemas exposed
by the FastAPI backend.

- Hardcoded inline objects (e.g., `{ id: number; name: string }` written
  directly in component props) are FORBIDDEN — extract them into shared type
  definitions.
- The `any` type is FORBIDDEN in React components and API client code. Use
  `unknown` with type guards when the shape is genuinely unknown.
- API response types MUST be derived from the backend's OpenAPI schema or
  manually kept in sync with a documented process.

### XI. Frontend State & Component Discipline

React components MUST be small and modular.

- A single component file SHALL NOT exceed 200 lines without justification.
- Components with complex state or side effects MUST be split into container
  (logic) and presentational (rendering) components.
- Tailwind CSS spacing scales (`p-2`, `m-4`, `gap-6`, etc.) MUST be used for
  all layout and spacing.
- Hardcoded pixel values (including arbitrary Tailwind values like
  `w-[17px]`) are FORBIDDEN. Use the standard scale or extend the theme
  configuration for project-specific values.

### XII. Documentation

Every new feature MUST include its own documentation markdown file in `docs/`.

- The document MUST be a concise version of the feature spec, capturing the
  feature's purpose, key user flows, API surface (if any), and any
  configuration or environment changes.
- Documentation MUST be written after implementation is complete and verified
  — it reflects what was built, not what was planned.
- The file MUST be named after the feature (e.g., `docs/user-auth.md`,
  `docs/search-indexing.md`).
- Documentation MUST be kept up to date when the feature is significantly
  modified in subsequent work.

## Technical Standards

**Technology Stack**: React 18+ with TypeScript (frontend), Python 3.12+ with
FastAPI (backend), PostgreSQL with vector extension (database, Docker-hosted).

**Dependency Management**: Backend uses `uv` with `pyproject.toml`. Frontend
uses `npm` with `package.json`. Both MUST pin exact versions for production
dependencies.

**Code Quality Gates**:

- Linting MUST pass (ESLint for frontend, Ruff for backend).
- Type checking MUST pass (TypeScript `strict` mode, mypy or pyright for
  backend where annotated).
- All unit tests MUST pass.
- At least one E2E Playwright test MUST pass for the spec under
  implementation.

## Governance

This constitution supersedes all other development practices, conventions,
and guidelines for the VKCA App project. When this constitution conflicts
with another document, the constitution prevails.

**Amendment Procedure**: Amendments require a PR that updates this file, with
a rationale in the PR description. Breaking changes (principle removal or
redefinition) require team discussion and explicit approval. Non-breaking
clarifications may be merged with standard review.

**Versioning**: This constitution follows semantic versioning
(MAJOR.MINOR.PATCH):

- MAJOR: Backward-incompatible governance or principle
  removals/redefinitions.
- MINOR: New principle or section added, or materially expanded guidance.
- PATCH: Clarifications, wording, typo fixes, non-semantic refinements.

**Compliance**: All PRs and code reviews MUST verify compliance with
applicable principles. The Constitution Check gate in each implementation
plan MUST reference this document. Complexity or principle violations MUST be
documented and justified in the plan's Complexity Tracking table.

**Version**: 1.3.0 | **Ratified**: 2026-07-05 | **Last Amended**: 2026-07-19
