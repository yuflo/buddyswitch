# S1 E1 Baseline and Package-Boundary Repair Implementation Plan

> Current disposition: STOPPED / SUPERSEDED after F-033 closure and expanded
> F-034 discovery. Do not continue this plan.

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restore a trustworthy C2 preservation baseline and make C1 exclude
physically co-located non-runtime subtrees from both the wheel and activation
source identity.

**Architecture:** Keep the current Demand Tool definition as the sole semantic
owner and repair only stale projections in tests. Keep `pyproject.toml` as the
sole distribution-content owner; activation applies the same explicit
non-runtime subtree boundary without introducing a second build system,
fallback, or source loader.

**Tech Stack:** Python 3.13, setuptools/PEP 517, wheel, pytest through the
single `./buddyswitch-test` runner.

---

### Task 1: Align stale Demand contract proofs

**Files:**

- Modify: `tests/unit/architecture/test_tool_runtime_contract.py`
- Modify: `tests/unit/env_tool/test_semantic_contract.py`

- [ ] **Step 1: Reuse the source-equivalent RED**

Use hub run `c6e52cb80ffd4f33ba0b19caa83e5249`. Do not manufacture a new
production change or weaken another assertion.

- [ ] **Step 2: Replace only the stale exact action projections**

Use this exact Demand action set in both files:

```python
{"list", "get", "resolve_inbound", "complete"}
```

In `_EXPECTED_FREE_ACTIONS`, remove:

```python
"demand_sys.create"
"demand_sys.revise"
"demand_sys.cancel"
```

and add:

```python
"demand_sys.resolve_inbound"
```

Change the exact replay/idempotency write-action loop to:

```python
for action in ("resolve_inbound", "complete"):
```

- [ ] **Step 3: Run the exact GREEN**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_tool_runtime_contract.py \
  tests/unit/env_tool/test_semantic_contract.py
```

Expected: both files pass; the run root is removed.

### Task 2: Add RED proof for co-located non-runtime subtrees

**Files:**

- Modify: `tests/support/package_runtime.py`
- Modify: `tests/unit/architecture/test_package_contract.py`
- Modify: `tests/process/package/test_distribution_install.py`
- Modify: `tests/process/package/test_runtime_activation.py`

- [ ] **Step 1: Let the process-test helper prepare an isolated source copy**

Add a test-only callback without changing production:

```python
from collections.abc import Callable

SourcePreparer = Callable[[Path], None]
NON_RUNTIME_PROBE_PARTS = ("tests", "docs", "projects")


def add_nested_nonruntime_probe(source_root: Path) -> None:
    package_root = source_root / "src" / "buddyswitch"
    module_root = package_root / "modules"
    probe_root = module_root / "probe"
    for package in (module_root, probe_root):
        package.mkdir(parents=True, exist_ok=True)
        (package / "__init__.py").write_text(
            "PROBE_PACKAGE = True\n",
            encoding="utf-8",
        )
    for part in NON_RUNTIME_PROBE_PARTS:
        forbidden_root = probe_root / part
        forbidden_root.mkdir()
        (forbidden_root / "__init__.py").write_text(
            "NON_RUNTIME_PROBE = True\n",
            encoding="utf-8",
        )
        (forbidden_root / "probe.py").write_text(
            "NON_RUNTIME_VALUE = 1\n",
            encoding="utf-8",
        )


def install_clean_runtime(
    work_root: Path,
    *,
    prepare_source: SourcePreparer | None = None,
) -> InstalledRuntime:
    source_root = work_root / "source"
    source_root.mkdir(parents=True)
    shutil.copy2(REPO_ROOT / "pyproject.toml", source_root / "pyproject.toml")
    shutil.copytree(REPO_ROOT / "src", source_root / "src", symlinks=True)
    if prepare_source is not None:
        prepare_source(source_root)
```

The callback runs after copying `pyproject.toml` and `src`, before building the
wheel. Keep the existing wheel build, venv creation, installation and return
body immediately after this insertion.

- [ ] **Step 2: Add a real wheel exclusion test**

In the isolated copied source, create nested Python packages/files below:

```text
src/buddyswitch/modules/probe/tests/**
src/buddyswitch/modules/probe/docs/**
src/buddyswitch/modules/probe/projects/**
```

Build through `install_clean_runtime(..., prepare_source=...)`, inspect the
wheel, and assert no path has a `tests`, `docs`, or `projects` segment below
`buddyswitch/`. Assert the ordinary
`buddyswitch/modules/probe/__init__.py` remains present so the proof cannot
pass by dropping the whole module.

```python
def test_nested_nonruntime_subtrees_are_absent_from_distribution(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_nested_nonruntime_probe,
    )
    with zipfile.ZipFile(installed.wheel) as archive:
        names = sorted(archive.namelist())

    assert "buddyswitch/modules/probe/__init__.py" in names
    assert not [
        name
        for name in names
        if {"tests", "docs", "projects"}.intersection(Path(name).parts)
    ]
```

- [ ] **Step 3: Add activation exclusion proof**

Prepare the same isolated subtrees before build and activation. After
activation, change one file in each excluded subtree and run `verify`.
Expected: verification remains successful because non-runtime files are not
activation inputs. Retain the existing proof that a runtime `.py` change fails
verification.

```python
def test_activation_ignores_nested_nonruntime_source_subtrees(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_nested_nonruntime_probe,
    )
    activated, _ = _payload(
        installed,
        "activate",
        "--source-root",
        str(installed.source_root),
    )
    assert activated.returncode == 0, activated.stderr

    probe_root = (
        installed.source_root
        / "src"
        / "buddyswitch"
        / "modules"
        / "probe"
    )
    for part in ("tests", "docs", "projects"):
        path = probe_root / part / "probe.py"
        path.write_text("NON_RUNTIME_VALUE = 2\n", encoding="utf-8")

    verified, payload = _payload(installed, "verify")
    assert verified.returncode == 0, verified.stderr
    assert payload["ok"] is True
```

- [ ] **Step 4: Strengthen the static declaration expectation**

Make the static unit contract require finder exclusions for top-level and
arbitrarily nested `tests`, `docs`, and `projects` package segments. The
expectation must match the exact `pyproject.toml` declaration, not a prose
substring.

- [ ] **Step 5: Run the new proofs and confirm RED**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/process/package/test_distribution_install.py \
  tests/process/package/test_runtime_activation.py
```

Expected before production/config repair: failures show nested forbidden
packages in the wheel and/or excluded-file activation drift.

### Task 3: Repair the single package and activation boundary

**Files:**

- Modify: `pyproject.toml`
- Modify: `src/buddyswitch/foundation/process_runtime/activation.py`

- [ ] **Step 1: Exclude forbidden package segments**

Keep `pyproject.toml` as the only package-discovery owner. Its finder exclusion
must reject both top-level and arbitrarily nested package paths for all three
names:

```toml
exclude = [
  "buddyswitch.tests*",
  "buddyswitch.*.tests*",
  "buddyswitch.docs*",
  "buddyswitch.*.docs*",
  "buddyswitch.projects*",
  "buddyswitch.*.projects*",
]
```

Do not add recursive package-data inclusion or a second build declaration.

- [ ] **Step 2: Exclude the same non-runtime source segments from activation**

Add one private constant:

```python
NON_RUNTIME_SOURCE_PARTS = frozenset(
    {"__pycache__", "tests", "docs", "projects"}
)
```

In `_source_inputs`, calculate each candidate's relative parts below
`src/buddyswitch` and exclude the candidate when those parts intersect the
constant. Continue excluding `.pyc`, rejecting symlinks for included build
inputs, sorting by source-relative path, and including `pyproject.toml`.

```python
paths.extend(
    path
    for path in package_source.rglob("*")
    if path.is_file()
    and not NON_RUNTIME_SOURCE_PARTS.intersection(
        path.relative_to(package_source).parts
    )
    and path.suffix != ".pyc"
)
```

- [ ] **Step 3: Rebuild and reactivate before using the public runner**

The source digest changes in this step. Build a fresh wheel with
`/Users/chen/miniconda3/bin/python`, force-reinstall it non-editably into
`.buddyswitch-runtime/venv`, reactivate, and move the temporary wheel
directory to Trash:

```bash
wheel_dir=$(mktemp -d /tmp/bs-s1-e1-wheel.XXXXXX)
/Users/chen/miniconda3/bin/python -m pip wheel \
  --no-deps \
  --no-build-isolation \
  --wheel-dir "$wheel_dir" \
  /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
.buddyswitch-runtime/venv/bin/python -m pip install \
  --force-reinstall \
  --no-deps \
  --no-index \
  --find-links "$wheel_dir" \
  buddyswitch==0.1.0
.buddyswitch-runtime/venv/bin/python -m \
  buddyswitch.application.entrypoints.runtime_activation \
  activate --source-root /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
mv "$wheel_dir" \
  "/Users/chen/.Trash/$(basename "$wheel_dir")"
```

Remove the temporary wheel/build directory and prove no egg-info/build residue
remains.

- [ ] **Step 4: Run C1 GREEN**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/process/package/test_distribution_install.py \
  tests/process/package/test_runtime_activation.py
```

Expected: all pass and all owned resources are cleaned.

### Task 4: Prove the repaired entry and stop

**Files:**

- No new implementation files.

- [ ] **Step 1: Run the complete affected C1 matrix**

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/process/package/test_distribution_install.py \
  tests/process/package/test_runtime_activation.py \
  tests/unit/architecture/test_unit_runtime_policy.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/support/test_runner.py \
  tests/process/launcher/test_bootstrap_config.py \
  tests/process/launcher/test_public_cli.py
```

- [ ] **Step 2: Run both frozen pre-move C2 groups**

```bash
./buddyswitch-test focused \
  tests/unit/architecture tests/unit/env_tool tests/unit/daemon \
  tests/unit/actor tests/unit/launcher tests/unit/runtime_protocol

./buddyswitch-test focused \
  tests/integration/env_tool tests/integration/runtime \
  tests/integration/runtime_broker tests/integration/daemon \
  tests/integration/app_server
```

Expected: both groups pass before any source/asset move.

- [ ] **Step 3: Inspect identity and cleanup**

Prove:

```text
HEAD unchanged
index empty
no commits
no source/asset moves
only packet-authorized files changed
no build/wheel/egg-info/test-run/process/socket/lock residue
git diff --check passes
```

- [ ] **Step 4: Return and stop**

Return the exact packet in `S1-E1-GOAL-PACKET.md`. Do not begin C2 and do not
edit the master ledger, finding register, residue register, READY review, or
original executor state.
