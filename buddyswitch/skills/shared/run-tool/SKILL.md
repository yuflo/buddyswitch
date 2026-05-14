---
name: run-tool
description: Use when you need to validate or commit run results through runtime-owned env tools without hidden state repair.
---

# run-tool

## Purpose
- Validate run result payload coherence before commit.
- Persist one auditable run result through `run.commit`.
- Keep commit audit-only: no hidden task/track/artifact/handoff repair.

## Command Surface
- `python3 scripts/env/client.py run validate-result --context <context-json> --result <result-json>`
- `python3 scripts/env/client.py run commit --context <context-json> --result <result-json>`
- `python3 scripts/env/client.py run get-receipt --run-id <run-id>`

## Guardrails
- `run.validate_result` should pass before `run.commit`.
- Retired mutation fields (for example `state_effects` and embedded `artifacts`) are rejected.
- Keep associations explicit through task/track/artifact/handoff tools before commit.

## Verification
- Contribute to one buddy-run commit.
- Do not call persist from inside the skill.
- Confirm response JSON is `ok=true`.
- Use receipt ids for follow-up actions; do not read/write raw runtime state paths directly.
