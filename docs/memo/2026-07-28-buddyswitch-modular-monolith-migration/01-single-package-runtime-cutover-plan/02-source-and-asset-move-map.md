# S1.2 Source and Asset Move Map

## Outcome

> Every current executable/runtime source and asset has one package location;
> imports and resource lookup use package names/resources; no source is copied
> or left at its old executable path.

## Baseline disposition coverage

At evidence baseline `9e527141ef9c6ca705015fcecfa0b2a6fe1c3fc3`,
all 228 tracked files in the current runtime roots match one disposition:

| Current class | Tracked files |
|---|---:|
| `scripts/env/**` | 68 |
| `scripts/runtime_kernel/**` | 9 |
| `scripts/runtime_store/**` | 1 |
| top-level `scripts/*` | 10 |
| `tools/launcher/*.py` | 45 |
| `tools/launcher/*.sh` | 7 |
| `tools/launcher/assets/**` | 19 |
| `tools/__init__.py` | 1 |
| `buddyswitch/skills/**` | 47 |
| `buddyswitch/env-profiles/**` | 5 |
| `buddyswitch/manifest.toml` | 1 |
| `framework/contracts/**` | 7 |
| `framework/config/**` | 2 |
| `framework/schemas/**` | 5 |
| `framework/agent-registry.md` | 1 |
| **Total / unmatched** | **228 / 0** |

The S1 source refresh repeats this partition against `git ls-files`. Any
unmatched file stops READY review.

## Exact directory moves

| Current source | S1 package target | S1 disposition |
|---|---|---|
| `scripts/env/**` | `src/buddyswitch/env/**` | move, rewrite imports to `buddyswitch.env` |
| `scripts/runtime_kernel/**` | `src/buddyswitch/runtime_kernel/**` | move, package module entry |
| `scripts/runtime_store/__init__.py` | none | delete; package is empty and has no consumer |
| `tools/__init__.py` | none | delete; the retired root package has no current consumer after launcher movement |
| `tools/launcher/*.py` | `src/buddyswitch/launcher/*.py` | move, rewrite imports |
| `tools/launcher/*.sh` | `src/buddyswitch/launcher/shell/*.sh` | move as explicit package executable assets |
| `tools/launcher/assets/**` | `src/buddyswitch/launcher/assets/**` | move as package data |
| `buddyswitch/skills/**` | `src/buddyswitch/skills/**` | move as current packaged Skill truth |
| `buddyswitch/env-profiles/**` | `src/buddyswitch/catalog/env-profiles/**` | move as current catalog data |
| `buddyswitch/manifest.toml` | `src/buddyswitch/catalog/manifest.toml` | move as current catalog truth until S6 |
| `framework/contracts/**` | `src/buddyswitch/contracts/**` | move as package data until owner stages |
| `framework/schemas/**` | `src/buddyswitch/contracts/schemas/**` | move as current Role result schemas until S6 |
| `framework/config/**` | `src/buddyswitch/config/**` | move as package data until Artifact stage |
| `framework/agent-registry.md` | none | delete; duplicates manifest truth and teaches retired paths |

## Exact top-level script mapping

| Current source | S1 package target | Note |
|---|---|---|
| `scripts/artifact_selection.py` | `src/buddyswitch/runtime_support/artifact_selection.py` | current owner; Artifact stage moves it |
| `scripts/browser_evidence.py` | `src/buddyswitch/runtime_support/browser_evidence.py` | current capability CLI |
| `scripts/env_cleanup.py` | `src/buddyswitch/runtime_support/env_cleanup.py` | current cross-product cleanup |
| `scripts/env_manifest.py` | `src/buddyswitch/runtime_support/env_manifest.py` | current catalog API |
| `scripts/env_profiles.py` | `src/buddyswitch/runtime_support/env_profiles.py` | current profile API |
| `scripts/output_schema.py` | `tests/support/output_schema.py` | test-only validator; never package runtime |
| `scripts/runtime_skills.py` | `src/buddyswitch/runtime_support/runtime_skills.py` | current selected Skill projector |
| `scripts/turn_runtime.py` | `src/buddyswitch/runtime_support/turn_runtime.py` | package diagnostics entry |

## Retired facades, not moved

| Current source | Required replacement |
|---|---|
| `scripts/env_legacy_store.py` | tests use exact repository/domain support; runtime imports absent; negative retired-schema guards remain with current owners |
| `scripts/env_store.py` | current rejection behavior moves to exact owner/negative tests only; no general runtime store facade |

If trace finds a live non-test consumer, stop and assign its actual semantic
owner. Do not move either facade under a new name.

## Import/resource rules

- imports are absolute `buddyswitch...` or explicit same-package relatives;
- no top-level `env`, `runtime_kernel`, `env_manifest`, `turn_runtime` import;
- resource lookup uses `importlib.resources` or an exact installed-resource
  locator;
- `buddyswitch.launcher` package data includes `assets/**/LICENSE*` in
  addition to the already frozen explicit file classes; the four current
  third-party license resources are runtime-distribution contents and
  participate in activation correspondence;
- no `Path(__file__).parents[n]` repository discovery;
- no `sys.path` mutation;
- no source checkout path in runtime config.

## Tests

Update root tests/fakes/support to import installed package modules. Test-only
builders that need product fixtures live under `tests/support/**`; they are not
runtime facades.

Add exact scans for:

```text
sys.path.insert
PYTHONPATH source roots
from env / import env
from runtime_kernel / import runtime_kernel
env_legacy_store
checkout .py execution by production processes
```

Negative guard strings are allowed only in named absence tests.

The source refresh records the exact file manifest below each directory move,
but does not reopen these dispositions.

## Checkpoint proof

- isolated installed-package unit/integration tests for moved imports;
- package resource reads for manifest/profile/contract/Skill/Web assets;
- no old source file remains after the stage candidate;
- distribution manifest matches the package content contract.
