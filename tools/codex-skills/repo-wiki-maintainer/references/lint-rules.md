# Lint Rules

## Deterministic Checks
- Required maintained files exist.
- Required sections exist in each maintained file.
- Canonical source references resolve.
- Entry ordering is stable and reproducible.

## Heading Contract Checks
- Validate exact top-level heading tokens declared in `references/page-schemas.md` under `## Required Top-Level Headings`.
- Treat missing or renamed required headings as `error`.

## Failure Levels
### error
- Missing required config or files.
- Canonical conflicts.
- Invalid section layout for required schemas.

### warn
- Stale timestamps.
- Optional section drift.
- Non-blocking formatting issues.

## Blocking Rules
- Any `error` fails lint.
- `warn` reports but does not block by default.
