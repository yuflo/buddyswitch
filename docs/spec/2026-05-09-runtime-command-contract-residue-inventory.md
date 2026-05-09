# Runtime Command Contract Residue Inventory (2026-05-09)

Search command:

```bash
rg '(^|[^a-zA-Z0-9_./-])scripts/turn_runtime\.py (prepare|persist)' tools framework scripts tests README.md docs/spec
```

Rule:
- Active host-facing surfaces must not retain bare `scripts/turn_runtime.py prepare|persist` instructions.
- Active matches are allowed only in canonical executable form: `python3 scripts/turn_runtime.py ...`.
- Historical planning/spec notes may retain old bare-command references when they are not runtime, launcher, or validator inputs.

| File | Classification | Disposition | Notes |
|---|---|---|---|
| `README.md` | active runbook | rewritten | Canonical `python3 scripts/turn_runtime.py prepare/persist` only. |
| `framework/docs/architecture-overview.md` | active runtime doc | rewritten | Canonical command contract only. |
| `framework/docs/skill-runtime-shared-rules.md` | active runtime doc | rewritten | Canonical persist command only. |
| `framework/docs/turn-runtime-spec.md` | active runtime doc | rewritten | Canonical prepare/persist contract only. |
| `framework/contracts/pm.md` | active contract doc | rewritten | Canonical persist command only. |
| `framework/contracts/market.md` | active contract doc | rewritten | Canonical persist command only. |
| `framework/contracts/design.md` | active contract doc | rewritten | Canonical persist command only. |
| `framework/contracts/dev.md` | active contract doc | rewritten | Canonical persist command only. |
| `framework/contracts/test.md` | active contract doc | rewritten | Canonical persist command only. |
| `scripts/turn_runtime.py` | active runtime implementation | rewritten | Canonical command constants and structured feedback actions use `python3 ...`. |
| `scripts/runtime_agents.py` | active validator | rewritten | Requires canonical contract wording; rejects bare command references. |
| `tools/launcher/assets/buddies/pm/AGENTS.md` | active host-facing template | rewritten | Canonical prepare/persist guidance only. |
| `tools/launcher/assets/buddies/market/AGENTS.md` | active host-facing template | rewritten | Canonical prepare/persist guidance only. |
| `tools/launcher/assets/buddies/design/AGENTS.md` | active host-facing template | rewritten | Canonical prepare/persist guidance only. |
| `tools/launcher/assets/buddies/dev/AGENTS.md` | active host-facing template | rewritten | Canonical prepare/persist guidance only. |
| `tools/launcher/assets/buddies/test/AGENTS.md` | active host-facing template | rewritten | Canonical prepare/persist guidance only. |
| `tests/test_turn_runtime.py` | active verification | rewritten | Verifies runtime command hints and absence of old rerun wording. |
| `tests/test_runtime_agents.py` | active verification | rewritten | Verifies canonical template wording and rejects bare command residue. |
| `tests/test_repo_consistency.py` | active verification | rewritten | Active-surface guard blocks bare command references. |
| `tests/test_buddyswitch_launcher.py` | active verification | rewritten | Expects canonical AGENTS guidance after materialization. |
| `docs/spec/2026-05-09-runtime-command-contract-development-plan.md` | current plan record | historical-only retained | Planning log includes old-command problem statements; not host-facing runtime guidance. |
| `docs/spec/2026-05-09-runtime-command-contract-residue-inventory.md` | residue log | historical-only retained | This inventory intentionally quotes command strings for classification evidence only. |
| `docs/spec/2026-05-09-runtime-command-contract-test-plan.md` | current test-plan record | historical-only retained | Test-plan language references old failure mode; not runtime/launcher/validator input. |

Result: no active retained bare `scripts/turn_runtime.py prepare|persist` host-facing instruction remains.
