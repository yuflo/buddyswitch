---
name: repo-wiki-maintainer
description: Maintain a thin repo-tracked wiki for fresh coding-agent orientation. Use when initializing, refreshing, or linting docs/llm-wiki without changing canonical docs.
---

# Repo Wiki Maintainer

## Use when
- The user wants to initialize, refresh, or lint the repo wiki.

## Maintenance Actions
- `wiki-init`
- `wiki-refresh`
- `wiki-lint`

## Bootstrap Contract
- `wiki-init` is the first-run bootstrap action and may create `.llm-wiki.toml` when missing.
- `wiki-refresh` requires `.llm-wiki.toml` to exist.
- `wiki-lint` requires `.llm-wiki.toml` to exist.

## Maintenance-Only Mode
- This skill is maintenance-only and must avoid explain/query behavior.

## Allowed Write Surface
- `docs/llm-wiki/**`
- `.llm-wiki.toml`

## Do not use when
- The user wants general repo explanation or unrelated implementation work.

## Guardrails
- For `wiki-refresh` and `wiki-lint`, read `.llm-wiki.toml` first.
- Keep writes limited to approved wiki maintenance targets.
- Stop on canonical conflicts instead of guessing.

## Runtime Boundary
- This package is source-only for Codex installation.
- It is not part of BuddySwitch runtime skill registration.
- Do not add this skill to `buddyswitch/manifest.toml`.

## References
- `references/workflow.md`
- `references/page-schemas.md`
- `references/repo-config.md`
- `references/lint-rules.md`
