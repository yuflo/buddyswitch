# LLM Wiki

Status: derived
Last verified: 2026-04-23
Covers through commit: 28fb29a340e7bdb1ebc71e273ff5041acc65e60f
Canonical sources:
- AGENTS.md
- README.md
- framework/docs/architecture-overview.md
- framework/docs/switch-spec.md
- tools/launcher/assets/runtime-AGENTS.md
Do not infer:
- This file does not replace canonical docs.
- If canonical sources disagree, stop and resolve the conflict before refreshing.

## Canonical Sources
- AGENTS.md
- README.md
- framework/docs/architecture-overview.md
- framework/docs/switch-spec.md
- tools/launcher/assets/runtime-AGENTS.md

## Reading Order
- AGENTS.md
- README.md
- framework/docs/architecture-overview.md
- framework/docs/switch-spec.md
- tools/launcher/assets/runtime-AGENTS.md

## Architecture Map
- `projects/app/`: primary application code.
- `framework/docs/`: canonical behavior and system contracts.
- `tools/launcher/assets/runtime-AGENTS.md`: launcher-managed runtime contract.
- `docs/llm-wiki/`: derived orientation layer only.

## Update Workflow
1. Update canonical sources first.
2. Re-run `wiki-refresh` to rewrite this derived layer.
3. Re-run `wiki-lint` before trusting the refreshed wiki.
