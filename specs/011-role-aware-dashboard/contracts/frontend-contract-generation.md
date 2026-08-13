# Frontend Contract Generation

The feature adds a repeatable contract-only OpenAPI export and generated
TypeScript check, following the existing Data Quality workflow.

## Commands

From `frontend/`:

```bash
npm run generate:role-aware-dashboard-types
npm run check:role-aware-dashboard-types
```

The generator invokes the backend export script with `uv run`, passes the
temporary OpenAPI document to the installed `openapi-typescript` binary, and
writes/checks:

```text
frontend/src/features/dashboard/api/generated.ts
```

The generated namespace includes the dashboard, Player account-linking, and
Match participant schemas used by feature API modules. The Player Directory
and dashboard code import those generated `components` types; they may add
feature-local presentation types only for UI state, not duplicate API shapes.

## Export source

`backend/scripts/export_role_aware_dashboard_openapi.py` builds a contract app
for the new operations and prefers registered production route operations when
available, matching `export_data_quality_openapi.py`. The export includes
operation IDs, request/response unions, enums, error envelopes, and the
participant discriminator so drift is visible in generated output.

## CI expectation

Run the check command with frontend tests/build. A mismatch fails the check and
requires regenerating the committed artifact. No runtime dependency or manual
copy of generated response fields is permitted.
