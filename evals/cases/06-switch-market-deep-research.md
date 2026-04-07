# Case 06: `switch market` Deep Research Protocol

## Intent

Validate that `switch market` follows browser-first deep research workflow with strong source traceability.

## Prompt

```text
switch market: Research 2026 demand signals for AI onboarding copilots. Use browser-first collection with search assist, include x.com and reddit by default, and write the report to artifacts/research/onboarding-copilot-demand.md
```

## Preconditions

- `framework/contracts/market.md` exists.
- `framework/templates/research-report.md` exists.
- `market` skill exists at `.agents/skills/market/research-scan/SKILL.md`.

## Manual Steps

1. Run the prompt in a BuddySwitch session.
2. Open generated research file under `artifacts/research/`.
3. Inspect sections and evidence traceability.
4. Verify channel coverage and round log.

## Pass Criteria

- Output includes all required market fields:
  - `research_question`
  - `research_strategy`
  - `channel_plan`
  - `iteration_log`
  - `evidence`
  - `source_traceability`
  - `patterns_and_insights`
  - `risks_and_caveats`
  - `conclusion`
- `channel_plan` includes both `x.com` and `reddit` unless the prompt explicitly excludes them.
- `iteration_log` round count matches chosen tier:
  - quick = 2
  - standard = 4
  - deep = 6
- Each key conclusion is mapped to source IDs in `source_traceability`.
- Evidence entries include:
  - `url`
  - `source_type`
  - `accessed_at`
  - `claim_excerpt`
- Durable output is written to `artifacts/research/`.

## Scenario Checks

- Login-required source:
  - run should enter login checkpoint and ask user confirmation before continuing.
- Blocked source:
  - run should record blockage, use fallback sources, and mark evidence quality downgrade.

## Fail Signals

- Missing one or more required output fields.
- Missing x.com or reddit without explicit exclusion.
- No source mapping from conclusions to evidence.
- Login-required source used without checkpoint confirmation.
- Blocking handled silently without disclosure.
