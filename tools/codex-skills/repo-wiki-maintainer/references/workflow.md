# Workflow

This skill package is source-only for Codex installation and is not part of BuddySwitch runtime skill registration.

## Read Order
- For `wiki-refresh` and `wiki-lint`, load `.llm-wiki.toml`.
- Read configured canonical sources.
- Read maintained wiki files.

## wiki-init
- First-run bootstrap action.
- May create `.llm-wiki.toml` when missing.
- Create wiki skeleton files only.
- Refuse destructive overwrite by default.

## wiki-refresh
- Require `.llm-wiki.toml` to exist; fail when missing.
- Update maintained wiki files from canonical sources only.
- Preserve deterministic ordering.

## wiki-lint
- Require `.llm-wiki.toml` to exist; fail when missing.
- Validate required sections, formatting, and source references.
- Emit deterministic errors and warnings.

## Stop Conditions
- Canonical conflict detected.
- Required config fields are missing.
- Writes fall outside approved wiki scope.
