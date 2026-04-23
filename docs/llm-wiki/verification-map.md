# Verification Map

Status: derived
Last verified: 2026-04-23
Covers through commit: 3961f01b55d2fc1d3dc1c4441be4650fd3d2af3c
Canonical sources:
- AGENTS.md
- README.md
- framework/docs/architecture-overview.md
- framework/docs/switch-spec.md
- tools/launcher/assets/runtime-AGENTS.md
Do not infer:
- This file does not replace canonical docs.
- If canonical sources disagree, stop and resolve the conflict before refreshing.

## Verification Entries
| Canonical Claim | Verification Command | Evidence Location |
| --- | --- | --- |
| Repo wiki shape is structurally valid | python3 tools/codex-skills/repo-wiki-maintainer/scripts/lint_wiki.py --repo-root . | docs/llm-wiki/recent-important-changes.md |
| Repo wiki scripts stay covered by focused tests | python3 -m pytest tests/test_repo_wiki_config.py tests/test_repo_wiki_init.py tests/test_repo_wiki_refresh.py tests/test_repo_wiki_lint.py -q | tests/test_repo_wiki_refresh.py |
