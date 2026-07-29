# S1 C6 Current-Guidance and Residue Scope Manifest

> Scope owner: coordinating hub
> Source: `S1-C6-SOURCE-SNAPSHOT.md`
> Rule: no unclassified write

## 1. C6 acceptance slice

```text
current executable owner
  -> current source/installed-package path
    -> root and docs/arch guidance
      -> structural absence guard
        -> frozen repository-wide proof
```

C6 changes no product behavior. It makes current guidance truthful, makes the
truth mechanically durable, classifies the remaining old terms, and runs the
one final acceptance gate.

## 2. Exact writable files

### PROOF

```text
tests/unit/architecture/test_package_contract.py
```

Add exactly one current-guidance topology test. Do not introduce a new linter,
test runner, document schema, scanner module or evidence ledger.

### CURRENT DOC

```text
README.md
AGENTS.md
docs/arch/daemon-service-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/task-sys-architecture.md
```

### EXECUTOR STATE

```text
docs/memo/2026-07-28-buddyswitch-modular-monolith-migration/
  01-single-package-runtime-cutover-plan/S1-C6-EXECUTION-STATE.md
```

No other file is writable.

## 3. Exact replacement map

| File | Retired live guidance | Required current truth |
|---|---|---|
| `README.md` | source `tools/launcher/env.sh`; invoke `scripts/env/client.py`; canonical owners below `scripts/**` and `framework/contracts/**` | public status through `./buddyswitch-codex env status`; canonical source owners below `src/buddyswitch/**`; `pyproject.toml` remains package owner |
| `AGENTS.md` | `buddyswitch/manifest.toml` | `src/buddyswitch/catalog/manifest.toml` |
| `AGENTS.md` | `tools/launcher/assets/roles/<role>/AGENTS.md` | `src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md` |
| `docs/arch/daemon-service-architecture.md` | `tools/launcher/instance_daemon.py` | `src/buddyswitch/launcher/instance_daemon.py` |
| `docs/arch/demand-sys-architecture.md` | `scripts/env/domain/demand_sys.py` | `src/buddyswitch/env/domain/demand_sys.py` |
| `docs/arch/demand-sys-architecture.md` | `scripts/env/repos/demands.py` | `src/buddyswitch/env/repos/demands.py` |
| `docs/arch/task-sys-architecture.md` | `scripts/env/domain/task_sys.py` | `src/buddyswitch/env/domain/task_sys.py` |
| `docs/arch/task-sys-architecture.md` | `tools/launcher/task_goal_handler.py` | `src/buddyswitch/launcher/task_goal_handler.py` |

The README canonical-owner list must name these exact current sources:

```text
pyproject.toml
src/buddyswitch/catalog/manifest.toml
src/buddyswitch/env/tool_runtime/definition.py
src/buddyswitch/env/tool_runtime/context.py
src/buddyswitch/env/tool_runtime/results.py
src/buddyswitch/env/tool_runtime/registry.py
src/buddyswitch/env/tools/<tool>/tool.py
src/buddyswitch/env/tools/<tool>/_impl.py
src/buddyswitch/runtime_kernel/protocol.py
src/buddyswitch/runtime_kernel/dispatcher.py
src/buddyswitch/contracts/prepare-turn-context.json
src/buddyswitch/contracts/{pm,design,dev,market,test}.md
src/buddyswitch/launcher/assets/roles/<role>/AGENTS.md
tests/
```

Do not change the described product semantics around these paths.

## 4. Structural guard

Add
`test_current_guidance_names_only_current_installed_package_owners` to
`tests/unit/architecture/test_package_contract.py`.

The test scans exactly:

```text
README.md
AGENTS.md
docs/arch/*.md
src/buddyswitch/launcher/assets/roles/*/AGENTS.md
src/buddyswitch/skills/**/SKILL.md
```

It rejects these retired live-guidance tokens:

```text
scripts/env/
scripts/runtime_kernel/
tools/launcher/
framework/contracts/
buddyswitch/manifest.toml
buddyswitch/env-profiles/
env_legacy_store
sys.path.insert
spec_from_file_location
--repo-root
PYTHONPATH
```

It also asserts the required current paths from section 3 in their owning
documents. Keep the assertion local to the existing package architecture
contract; do not copy runtime selection or package membership rules.

Against the frozen source, this new test must first fail with exactly 19 stale
token occurrences:

```text
README.md: 12
AGENTS.md: 2
docs/arch/daemon-service-architecture.md: 1
docs/arch/demand-sys-architecture.md: 2
docs/arch/task-sys-architecture.md: 2
```

After the exact replacements, it must pass with zero stale current-guidance
matches.

## 5. Preserve without editing

```text
docs/arch/web-interface-call-architecture.md
src/buddyswitch/**
pyproject.toml
buddyswitch-codex
buddyswitch-test
all Role AGENTS
all packaged Skills
all CLI/help/error text
all tests except tests/unit/architecture/test_package_contract.py
projects/app/**
canonical and private runtime state
all migration memos except S1-C6-EXECUTION-STATE.md
git index, branch, worktree configuration and remote
```

The Role/Skill and executable surfaces are already clean. Editing them would
reopen accepted C2–C5 scope.

## 6. Residue classification before C6

### Forbidden live current guidance

The 19 occurrences in section 4 are the complete current-guidance residue and
belong to R-PKG-016/R-DOC-001.

### Exact negative absence guards

These active tests intentionally name old roots or loaders to prove absence:

```text
tests/unit/architecture/test_package_contract.py
tests/unit/launcher/test_actor_environment.py
tests/unit/actor/test_runtime_skills.py
tests/integration/env_tool/test_host_decision_surface.py
tests/integration/env_tool/test_search.py
tests/process/cli/test_env_client_payload.py
tests/process/cli/test_env_native_mcp_projection.py
tests/process/cli/test_env_layer_boundaries.py
tests/process/launcher/test_public_cli.py
tests/process/services/test_runtime_broker_lifecycle.py
tests/system/instance_lifecycle/test_environment_build_safety.py
```

They remain current proof and must not be rewritten merely to make a global
text search empty.

### Valid current unrelated text

```text
buddyswitch-test
  unsets PYTHONPATH so tests use the activated installed package

tests/runner.py and tests/support/**
  remove inherited PYTHONPATH as test isolation

tests/process/package/test_distribution_install.py
  names installed wheel path buddyswitch/skills/**, not the retired checkout
  root

src/buddyswitch/skills/dev/select-local-verification/SKILL.md
  says local project scripts/configs generically; it names no retired
  BuddySwitch implementation path
```

### Historical memo

`docs/memo/**` may preserve retired names and failed-plan history. It is
excluded from current-guidance absence claims.

## 7. Boundary-contract matrix

| Claim class | C6 proof |
|---|---|
| Positive | Every named current source exists; current docs name it; focused architecture tests pass |
| Negative | Old physical roots contain no file/symlink; active guidance has zero retired token; production source has no retired loader/path |
| Correspondence | Every path taught by current docs is an exact existing current owner; runtime source/install byte correspondence is reused from accepted C1/C2–C5 and reverified |
| Mutation | The added architecture test fails on the frozen stale guidance and passes only after the five exact documents change |
| Cleanup | Public runner cleans its run root/resources; C6 creates no runtime state; final process/socket/lock/temp scan is empty |

No package mechanism, state migration, public contract or semantic owner is
introduced. A representative framework/tool preflight is inapplicable because
the selected mechanism is a plain assertion in an existing test file over
tracked text and existing paths.

## 8. Owned and deferred residue

C6 may propose closure of:

```text
R-PKG-016
R-DOC-001
```

C6 does not close R-DOC-004. Root manifest/Role paths will be current after
C6, but S6 still owns their later RoleHost replacement. That future owner does
not excuse stale S1 paths now.

All component, foundation and Role residue remains assigned to S2–S6.
