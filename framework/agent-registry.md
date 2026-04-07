# BuddySwitch v1 Agent Registry

This registry defines the only supported specialist agents for BuddySwitch v1.

Invocation model:
- User explicitly selects one agent via `switch <agent>: <task>`.
- No team lead role.
- No hidden workflow rerouting.
- No implicit parallel orchestration.

## Registered Agents

| Agent | Purpose | Contract | Default Artifact Path | Starter Skill |
| --- | --- | --- | --- | --- |
| `market` | demand and competitor research | `framework/contracts/market.md` | `artifacts/research/` | `research-scan` |
| `pm` | PRD and product scope definition | `framework/contracts/pm.md` | `artifacts/prd/` | `write-prd` |
| `design` | IA, flows, and interaction spec | `framework/contracts/design.md` | `artifacts/design/` | `ia-spec` |
| `dev` | implementation in project code | `framework/contracts/dev.md` | `artifacts/build/` | `implement-task` |
| `test` | validation and test reporting | `framework/contracts/test.md` | `artifacts/test/` | `smoke-test` |
