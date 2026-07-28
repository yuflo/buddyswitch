# S1 E2 Exact Runtime Correspondence Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:executing-plans` to implement this plan task by task. Steps use
> checkbox (`- [ ]`) syntax for tracking. Follow root `AGENTS.md` and
> `$buddyswitch-testing`.

**Goal:** Make C1 activation prove exact path-and-byte correspondence between
the current non-test package source and the installed package before it writes
or accepts a runtime identity.

**Architecture:** `pyproject.toml` remains the only build/content declaration.
The activation owner builds one source package manifest and one installed
package manifest, rejects all package-tree symlinks before exclusions, and
compares the two manifests directly at `activate` and `verify`; it does not
parse setuptools configuration or introduce a build manifest.

**Tech Stack:** Python 3.13, `setuptools.build_meta`, `importlib.metadata`,
wheel `RECORD`, existing JSON activation contract, existing
`./buddyswitch-test`.

---

## 1. Stage identity

```text
Stage/checkpoint:
S1 / C1 / E2

State:
ACCEPTED through S1-E2-ACCEPTANCE.md; packet consumed

Source:
S1-E2-SOURCE-SNAPSHOT.md

Preflight:
S1-E2-PREFLIGHT.md / E2P-1c5a001693442adc

Finding/residue:
F-034 / R-PKG-019

Owning boundary:
src/buddyswitch/foundation/process_runtime/activation.py

Build declaration owner:
pyproject.toml
```

## 2. Acceptance sentence

> Given a non-editable BuddySwitch wheel and its checkout source, activation
> succeeds only when every regular non-test file below
> `src/buddyswitch/**` has exactly one installed package counterpart at the
> same relative path with the same bytes, the installed package has no
> unrecorded counterpart, and the package source contains no symlink.

Consumer path:

```text
explicit runtime setup
  -> installed runtime_activation activate
    -> source manifest + installed RECORD/package-root manifest
      -> exact correspondence
        -> atomic activation record or RUNTIME_MISMATCH with no record change
```

## 3. Accepted pre-READY evidence

| Boundary claim | Evidence | Result |
|---|---|---|
| required package-owned `assets/docs` content ships and corresponds | `E2P-1c5a001693442adc` | PASS |
| co-located tests/cache remain non-runtime | `E2P-1c5a001693442adc` | PASS |
| source/installed add, missing and byte drift are rejected | `E2P-1c5a001693442adc` | PASS |
| file, directory and excluded-subtree source symlinks fail before exclusions | `E2P-1c5a001693442adc` | PASS |
| current C1 behavior before mutation | run `d2fe4bb7b85f416fb42aacfd6798146e` | 53 passed, 29 subtests |
| complete C2 unit behavior before mutation | run `90678f930b614b91a2c2df0ff66016e8` | 314 passed, 1035 subtests |
| complete C2 integration behavior before mutation | run `a5b0e1edee794816801d996438eb3f98` | 353 passed, 276 subtests |

The three preservation runs remain identity-valid because only
`docs/memo/**` and the out-of-repository preflight changed afterward. No
executable, test, fixture, runner, dependency or active runtime changed.

## 4. Allowed scope

| Path | Class | Disposition |
|---|---|---|
| `pyproject.toml` | build/content owner | MODIFY |
| `src/buddyswitch/foundation/process_runtime/activation.py` | runtime identity owner | MODIFY |
| `tests/support/package_runtime.py` | isolated package fixture | MODIFY |
| `tests/unit/architecture/test_package_contract.py` | static proof | MODIFY |
| `tests/process/package/test_distribution_install.py` | wheel/install proof | MODIFY |
| `tests/process/package/test_runtime_activation.py` | activation/correspondence proof | MODIFY |

No other executable, test, fixture, current architecture or product file may
change.

Coordinating-owned migration documents, finding/residue status and READY
records are read-only to the executor. The hub updates them after return.

## 5. Frozen behavior and non-goals

Preserve:

- activation commands `activate --source-root`, `verify`, `status`;
- JSON success/failure envelope and exit codes 5/6;
- activation record fields/schema/version and atomic mode `0600` write;
- non-editable installed runtime, interpreter/package-root/version/digest
  binding;
- source drift and installed drift rejection after activation;
- root `pyproject.toml` participation in source/build attribution;
- all accepted Demand, Tool, C2 and product behavior.

Do not:

- add a custom build backend, generated manifest, setuptools parser or second
  package selection engine;
- add compatibility, fallback, editable/source import or `PYTHONPATH`;
- change activation JSON fields or public commands;
- exclude package-internal `docs` or `projects` names;
- move sources/assets, begin C2, delete old roots or edit Demand;
- commit, stage, switch branches or run `./buddyswitch-test full`.

## 6. Task 1 — Write exact correspondence RED

**Files**

- Modify: `tests/support/package_runtime.py`
- Modify: `tests/unit/architecture/test_package_contract.py`
- Modify: `tests/process/package/test_distribution_install.py`
- Modify: `tests/process/package/test_runtime_activation.py`

- [ ] **Step 1: Replace the ambiguous fixture**

Replace `NON_RUNTIME_PROBE_PARTS` and `add_nested_nonruntime_probe` with one
fixture named `add_correspondence_probe`:

```python
RUNTIME_ASSET = Path("launcher/assets/docs/help.md")
COLOCATED_TEST = Path("modules/probe/tests/test_probe.py")


def add_correspondence_probe(source_root: Path) -> None:
    package_root = source_root / "src" / "buddyswitch"

    for relative, content in (
        (Path("launcher/__init__.py"), '"""launcher."""\n'),
        (RUNTIME_ASSET, "# Runtime help\n"),
        (Path("modules/__init__.py"), '"""modules."""\n'),
        (Path("modules/probe/__init__.py"), "PROBE = True\n"),
        (Path("modules/probe/tests/__init__.py"), '"""tests."""\n'),
        (COLOCATED_TEST, "def test_probe():\n    assert True\n"),
    ):
        target = package_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")

    cache = package_root / "modules" / "probe" / "__pycache__" / "probe.pyc"
    cache.parent.mkdir()
    cache.write_bytes(b"not-a-real-pyc")
```

Keep `install_clean_runtime` behavior unchanged.

- [ ] **Step 2: Correct the static package contract expectation**

The exact finder exclusion becomes:

```python
"exclude": [
    "buddyswitch.tests*",
    "buddyswitch.*.tests*",
],
```

Do not add `docs` or `projects` exclusions.

- [ ] **Step 3: Replace the wheel-boundary proof**

Replace the nested non-runtime test with:

```python
def test_runtime_assets_ship_while_colocated_tests_and_caches_do_not(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    with zipfile.ZipFile(installed.wheel) as archive:
        names = set(archive.namelist())

    assert "buddyswitch/launcher/assets/docs/help.md" in names
    assert "buddyswitch/modules/probe/__init__.py" in names
    assert not [
        name
        for name in names
        if "/tests/" in f"/{name}"
        or "/__pycache__/" in f"/{name}"
        or name.endswith(".pyc")
    ]
```

Also remove `"/docs/"` and `"/projects/"` from the blanket forbidden list in
the clean-distribution test. Required package data remains governed by the
explicit package-data roots.

- [ ] **Step 4: Add first-activation correspondence RED**

Add a small assertion helper:

```python
def _assert_runtime_mismatch(
    installed: InstalledRuntime,
    command: str = "activate",
) -> dict[str, object]:
    args = (
        ("--source-root", str(installed.source_root))
        if command == "activate"
        else ()
    )
    completed, payload = _payload(installed, command, *args)
    assert completed.returncode == 6
    assert payload["ok"] is False
    assert payload["error"]["code"] == "RUNTIME_MISMATCH"
    return payload
```

Add:

```python
def test_activation_rejects_source_drift_before_first_record(
    tmp_path: Path,
) -> None:
    installed = install_clean_runtime(
        tmp_path,
        prepare_source=add_correspondence_probe,
    )
    asset = (
        installed.source_root
        / "src"
        / "buddyswitch"
        / RUNTIME_ASSET
    )
    asset.write_bytes(asset.read_bytes() + b"SOURCE DRIFT\n")

    _assert_runtime_mismatch(installed)
    assert not (installed.runtime_dir / "activation.json").exists()
```

Add a second test that installs the correspondence fixture, activates once,
records `activation.json` bytes, then independently mutates and restores:

```python
test_activation_rejects_correspondence_drift_without_rewriting_record
```

It covers:

```text
source-only regular file
source file missing
source runtime-asset byte drift
installed-only unrecorded file
installed recorded file missing
installed byte drift
```

For every mutation, `activate` must return `RUNTIME_MISMATCH` and the existing
activation record bytes must remain unchanged.

- [ ] **Step 5: Add symlink-before-exclusion RED**

Using one clean installed fixture and no activation record, independently add
and remove:

```python
test_activation_rejects_source_symlinks_before_exclusions
```

It covers:

```text
modules/probe/linked.py -> regular source file
modules/probe/linked_package -> real directory
modules/probe/tests/linked_test.py -> regular source file
```

Each `activate` call must return `RUNTIME_MISMATCH`, identify a forbidden
source symlink in error details and leave `activation.json` absent.

- [ ] **Step 6: Correct the ignored-content proof**

Rename the existing nested-nonruntime activation test to:

```python
test_activation_ignores_colocated_tests_and_cache_but_tracks_runtime_assets
```

After successful activation:

- changing files below the real `tests` subtree and `__pycache__` remains
  verified;
- changing `launcher/assets/docs/help.md` returns `RUNTIME_MISMATCH`.

- [ ] **Step 7: Run the exact RED**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py::test_pyproject_is_the_only_exact_package_build_owner \
  tests/process/package/test_distribution_install.py::test_runtime_assets_ship_while_colocated_tests_and_caches_do_not \
  tests/process/package/test_runtime_activation.py::test_activation_rejects_source_drift_before_first_record \
  tests/process/package/test_runtime_activation.py::test_activation_rejects_correspondence_drift_without_rewriting_record \
  tests/process/package/test_runtime_activation.py::test_activation_rejects_source_symlinks_before_exclusions \
  tests/process/package/test_runtime_activation.py::test_activation_ignores_colocated_tests_and_cache_but_tracks_runtime_assets
```

Expected RED:

- static package exclusion still contains `docs/projects`;
- current activation accepts at least the source-only or source-asset drift
  before first activation;
- current activation ignores a symlink inside the excluded tests subtree.

A setup/import/build failure is not valid RED.

## 7. Task 2 — Make package content semantics exact

**Files**

- Modify: `pyproject.toml`

- [ ] **Step 1: Remove the false package-name exclusions**

The only finder exclusions are:

```toml
exclude = [
  "buddyswitch.tests*",
  "buddyswitch.*.tests*",
]
```

Keep `setuptools.build_meta`, package-data owners and explicit asset patterns
unchanged. Do not add catch-all package data.

## 8. Task 3 — Implement one correspondence owner

**Files**

- Modify: `src/buddyswitch/foundation/process_runtime/activation.py`

- [ ] **Step 1: Separate full-tree symlink validation from manifest filtering**

Use:

```python
NON_RUNTIME_PACKAGE_DIRS = frozenset({"tests", "__pycache__"})


def _reject_tree_symlinks(root: Path, *, label: str) -> None:
    for current_text, directory_names, file_names in os.walk(
        root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        for name in (*directory_names, *file_names):
            candidate = current / name
            if candidate.is_symlink():
                raise RuntimeActivationError(
                    "RUNTIME_MISMATCH",
                    f"{label} symlink is forbidden: {candidate}",
                    exit_code=MISMATCH_EXIT,
                    details={"path": str(candidate)},
                )
```

Call this on the entire source package tree before pruning tests/cache. Call it
on the installed package tree before installed manifest filtering.

- [ ] **Step 2: Build the source package manifest**

Implement:

```python
def _source_package_manifest(source_root: Path) -> dict[str, bytes]:
    package_root = source_root / "src" / PACKAGE_NAME
    if package_root.is_symlink() or not package_root.is_dir():
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "source root must contain a real src/buddyswitch directory",
            exit_code=MISMATCH_EXIT,
        )
    _reject_tree_symlinks(package_root, label="package source")

    manifest: dict[str, bytes] = {}
    for current_text, directory_names, file_names in os.walk(
        package_root,
        topdown=True,
        followlinks=False,
    ):
        current = Path(current_text)
        directory_names[:] = [
            name
            for name in directory_names
            if name not in NON_RUNTIME_PACKAGE_DIRS
        ]
        for name in file_names:
            candidate = current / name
            if candidate.suffix == ".pyc":
                continue
            manifest[candidate.relative_to(package_root).as_posix()] = (
                candidate.read_bytes()
            )
    return manifest
```

Validate `pyproject.toml` as a real, non-symlink regular file. Compute the
recorded source digest from:

```text
pyproject.toml path + bytes
src/buddyswitch/<manifest-relative-path> + bytes
```

Use the already-read manifest bytes; do not rescan during one operation.

- [ ] **Step 3: Return the installed package manifest from the existing owner**

Extend `_distribution_manifest` to return:

```python
tuple[str, str, Path, dict[str, bytes]]
```

Keep current non-editable detection, version, package-root validation,
distribution digest and unrecorded-file protection.

For recorded package files:

- select only distribution paths whose first part is `buddyswitch`;
- reject missing or symlinked files;
- strip the leading `buddyswitch/`;
- map the remaining relative path to exact bytes.

Scan the actual installed package root after full-tree symlink rejection.
Exclude only `__pycache__` and `.pyc` from actual/recorded equality. Any
unrecorded or missing installed package path returns `RUNTIME_MISMATCH`.

- [ ] **Step 4: Compare exact manifests once**

Implement:

```python
def _require_package_correspondence(
    source: dict[str, bytes],
    installed: dict[str, bytes],
) -> None:
    source_only = sorted(set(source) - set(installed))
    installed_only = sorted(set(installed) - set(source))
    changed = sorted(
        relative
        for relative in set(source) & set(installed)
        if source[relative] != installed[relative]
    )
    if source_only or installed_only or changed:
        raise RuntimeActivationError(
            "RUNTIME_MISMATCH",
            "source and installed BuddySwitch package content disagree",
            exit_code=MISMATCH_EXIT,
            details={
                "source_only": source_only,
                "installed_only": installed_only,
                "changed": changed,
            },
        )
```

At both `activate` and `verify`:

1. read the source package manifest;
2. read the distribution/install manifest;
3. require exact correspondence;
4. derive/compare the recorded source and distribution digests;
5. write no activation record until all checks pass.

Do not add a fallback or retain `_source_inputs` as a second truth.

- [ ] **Step 5: Preserve failure effects**

Any correspondence or symlink failure:

- returns exit 6 and `RUNTIME_MISMATCH`;
- contains exact path-set or symlink details;
- writes no first activation record;
- leaves an existing activation record byte-identical.

## 9. Task 4 — Rebuild, reactivate and prove exact GREEN

- [ ] **Step 1: Rebuild the one active runtime**

After production/config changes, before using the public runner:

```bash
wheel_dir=$(mktemp -d /private/tmp/bs-s1-e2-wheel.XXXXXX)
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
  activate \
  --source-root /Users/chen/Dev/buddyswitch/.worktrees/fea-tool
```

Move the explicit temporary wheel root and any build-created egg-info residue
to uniquely named paths below `/Users/chen/.Trash`. Do not remove or rewrite
unrelated files.

- [ ] **Step 2: Run the exact GREEN**

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/process/package/test_distribution_install.py \
  tests/process/package/test_runtime_activation.py
```

Expected: all direct correspondence, package-content, symlink and existing
activation tests pass with clean run-root cleanup.

## 10. Task 5 — Reprove the complete affected boundary

- [ ] **Step 1: Run the full C1 matrix**

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

- [ ] **Step 2: Run complete C2 unit pre-move preservation**

```bash
./buddyswitch-test focused \
  tests/unit/architecture tests/unit/env_tool tests/unit/daemon \
  tests/unit/actor tests/unit/launcher tests/unit/runtime_protocol
```

- [ ] **Step 3: Run complete C2 integration pre-move preservation**

```bash
./buddyswitch-test focused \
  tests/integration/env_tool tests/integration/runtime \
  tests/integration/runtime_broker tests/integration/daemon \
  tests/integration/app_server
```

Any new failure, flake, timeout or cleanup residue stops E2. Do not proceed
into C2.

## 11. Task 6 — Audit and return

- [ ] **Step 1: Inspect exact scope and replacement**

Prove:

```text
only the six allowed files changed
old independent source scan is absent
no docs/projects package-name exclusion remains
no custom backend/generated manifest/config parser exists
activation schema/public commands unchanged
F-033 accepted changes remain intact
no C2 source/asset movement occurred
```

- [ ] **Step 2: Inspect cleanup**

Prove:

```text
all focused run roots absent
no probe/build/pip process
no repository build/wheel/egg-info residue
no PID/socket/lock/temp residue
index empty
HEAD unchanged
git diff --check passes
```

- [ ] **Step 3: Return and stop**

Return the exact Goal Packet result. Do not close F-034/R-PKG-019, accept C1,
resume S1 or begin C2; those decisions belong to the coordinating hub.

## 12. Stop and replan

Stop immediately if:

- exact correspondence requires parsing setuptools rules, a custom backend,
  generated manifest or second content owner;
- legitimate package assets cannot coexist with test/cache exclusion;
- any package-source symlink can evade validation;
- the public activation JSON/command/exit contract must change;
- another executable/test file or C2 move becomes necessary;
- the complete preservation baseline produces a new failure family;
- starting identity or unrelated dirty-work ownership differs.

Because this is the architecture-reviewed successor after two invalidated
specifications, another specification contradiction does not produce E3.
Return `ARCHITECTURE_REOPEN_REQUIRED` and stop.
