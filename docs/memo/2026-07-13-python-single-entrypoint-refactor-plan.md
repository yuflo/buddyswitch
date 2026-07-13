# Python Single-Entrypoint Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `tools/launcher/env.sh` resolve the single unversioned `python` command once, export its absolute path as `BUDDYSWITCH_PYTHON`, and require every non-`docs/**` Python execution path to consume that value without version checks, historical entrypoints, overrides, or fallback branches.

**Architecture:** `buddyswitch_env_init` owns interpreter resolution before any workspace or launcher helper runs. It ignores inherited `BUDDYSWITCH_PYTHON`, resolves only `python` from `PATH`, verifies that command can execute, and exports one absolute path. Shell helpers, persisted MCP commands, Python child processes, test subprocesses, generated test executables, diagnostics, and active role guidance all consume that exported path; no other resolver or compatibility path remains.

**Tech Stack:** Bash launcher helpers, Python standard library, `unittest`/`pytest`, TOML via the standard-library `tomllib`, ripgrep-based repository checks.

---

## Confirmed requirements

1. The only resolver lives in `tools/launcher/env.sh`.
2. BuddySwitch startup requires no human-supplied interpreter setting.
3. The resolver selects only the unversioned `python` command from `PATH`.
4. Inherited `BUDDYSWITCH_PYTHON` is overwritten, not treated as an override.
5. There is no candidate list, versioned command probe, numeric version comparison, or fallback interpreter.
6. Every Python process receives the one exported absolute path.
7. Persisted MCP configuration stores that same path and is generically reconciled when it differs.
8. Non-`docs/**` source contains no old command token, Python shebang, `sys.executable` process path, `tomli` compatibility import, or Python-version-specific branch.
9. `docs/**` is excluded from source cleanup and consistency checks. This plan file is the only documentation artifact created for the work.
10. A future project virtual environment changes only the resolver target in `tools/launcher/env.sh`; consumers stay unchanged.

## Re-audit result

The scan boundary is tracked repository content excluding `docs/**` and duplicate `.worktrees/**` checkouts.

| Surface | Current residue | Required end state |
| --- | ---: | --- |
| Shell launcher/helper command references | 107 across 9 files | All use `"${BUDDYSWITCH_PYTHON}"` |
| Production Python references | 109: 107 shebangs and 2 non-shebang references | Zero old command references and zero Python shebangs |
| Test references | 194: 97 file shebangs and 97 fixture/assertion/command references | Zero old command references and zero Python shebangs |
| Active non-`docs/**` guidance references | 40 across 38 files | All show `"$BUDDYSWITCH_PYTHON"` |
| Total old command references | 450 | Zero |
| `sys.executable` references | 53 across production and tests | Zero; tests consume the configured path too |
| Version-compatibility TOML paths | `scripts/env_manifest.py`, `tools/launcher/env.sh`, and 4 tests | Standard-library `tomllib` only |
| Executable tracked Python files | 3 | Zero |
| Existing `BUDDYSWITCH_PYTHON` support | None | One assignment owner in `env.sh`; all other occurrences are consumers |

No `pyproject.toml`, `.python-version`, `.tool-versions`, `tox.ini`, `pytest.ini`, requirements file, Pipfile, Poetry lock, or uv lock currently owns Python selection. This plan deliberately does not introduce one.

### Runtime shell inventory

These are the complete non-`docs/**` shell consumers and their current reference counts:

- `buddyswitch-codex` — 31
- `tools/launcher/app_server.sh` — 16
- `tools/launcher/browser_cockpit.sh` — 11
- `tools/launcher/cleanup.sh` — 3
- `tools/launcher/daemon.sh` — 6
- `tools/launcher/env.sh` — 22
- `tools/launcher/instance.sh` — 12
- `tools/launcher/runtime_broker.sh` — 4
- `tools/launcher/workspace.sh` — 2

`buddyswitch-codex` sources all launcher helpers and calls `buddyswitch_env_init` before dispatching commands, so the resolver can run before every production Python consumer. Tests that source `workspace.sh` directly must switch to the correct composition root (`env.sh` plus `buddyswitch_env_init`) instead of recreating interpreter resolution.

### Hidden dual paths found by the second audit

- `scripts/runtime_kernel/lifecycle.py` launches the broker with a string command independent of the launcher.
- `tools/launcher/central_daemon.py` and `tools/launcher/daemon_core.py` launch children through `sys.executable`.
- `tools/launcher/env.sh` and `tools/launcher/browser_cockpit.sh` persist MCP command paths and must compare desired interpreter identity, not only script arguments.
- `scripts/env_manifest.py` keeps a hand-written TOML parser for runtimes without `tomllib`.
- `tools/launcher/env.sh` plus four tests retain `tomli` import fallbacks.
- Three Python files are tracked executable: `scripts/env_cleanup.py`, `scripts/env_manifest.py`, and `tools/launcher/chrome_devtools_cockpit_proxy.py`.
- Six test files embed temporary Python shebangs in generated executables: `tests/test_browser_cockpit_launcher.py`, `tests/test_browser_cockpit_proxy.py`, `tests/test_browser_lazy_release_integration.py`, `tests/test_browser_runtime_manager.py`, `tests/test_buddyswitch_launcher.py`, and `tests/test_runtime_broker.py`.

## Target runtime contract

```text
PATH
  └── python
        └── tools/launcher/env.sh::buddyswitch_resolve_python
              └── export BUDDYSWITCH_PYTHON=/absolute/path/to/python
                    ├── launcher and helper shell calls
                    ├── env MCP persisted command
                    ├── browser MCP persisted command
                    ├── daemon and broker child processes
                    ├── active diagnostics and role instructions
                    └── test runner, test subprocesses, and generated test executables
```

There is no incoming configuration branch. `BUDDYSWITCH_PYTHON` is an internal resolved output, not a user override. Missing or unusable `python` is a startup error.

## File responsibility map

- `tools/launcher/env.sh`: sole resolver, exported interpreter value, env MCP desired-state comparison and registration.
- `buddyswitch-codex` and eight `tools/launcher/*.sh` helpers: shell consumers only.
- `tools/launcher/browser_cockpit.sh`: browser MCP desired-state comparison and registration.
- `scripts/runtime_kernel/lifecycle.py`, `tools/launcher/central_daemon.py`, `tools/launcher/daemon_core.py`: Python child-process consumers only.
- `scripts/env_manifest.py`: one standard-library TOML parsing path.
- `tests/python_runtime.py`: test-only consumer that exposes the already-resolved path and generates exact-path temporary shebangs; it does not resolve or default anything.
- `tests/test_buddyswitch_launcher.py`: resolver, launcher propagation, env MCP, browser MCP, and diagnostic behavior.
- `tests/test_repo_consistency.py`: repository-wide no-residue and single-owner gate.
- Remaining tests: consume `tests.python_runtime.PYTHON` instead of selecting an interpreter.

## Task 1: Add and prove the sole resolver

**Files:**

- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tools/launcher/env.sh`

- [ ] **Step 1: Add failing resolver tests**

Add focused tests that source `env.sh`, set `PATH` after sourcing, and invoke `buddyswitch_resolve_python` directly. The success case must put one executable named `python` in a temporary directory, set an intentionally invalid inherited `BUDDYSWITCH_PYTHON`, and assert that the inherited value is overwritten. The failure case must use an empty temporary `PATH` and assert immediate failure.

```python
def test_python_resolver_uses_only_path_python_and_overwrites_inherited_value(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        bin_dir = Path(temp_root) / "bin"
        bin_dir.mkdir()
        current_python = shutil.which("python")
        self.assertIsNotNone(current_python)
        assert current_python is not None
        (bin_dir / "python").symlink_to(current_python)

        command = r'''
set -euo pipefail
source tools/launcher/env.sh
PATH="$1"
export BUDDYSWITCH_PYTHON="/ignored/inherited/interpreter"
buddyswitch_resolve_python
printf '%s\n' "$BUDDYSWITCH_PYTHON"
'''
        completed = subprocess.run(
            ["/bin/bash", "-c", command, "resolver-test", str(bin_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertEqual(completed.returncode, 0, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), str(bin_dir / "python"))


def test_python_resolver_fails_when_path_has_no_python(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        command = r'''
set -euo pipefail
source tools/launcher/env.sh
PATH="$1"
buddyswitch_resolve_python
'''
        completed = subprocess.run(
            ["/bin/bash", "-c", command, "resolver-test", temp_root],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("requires an executable 'python' on PATH", completed.stderr)


def test_python_resolver_rejects_unusable_path_python(self) -> None:
    with tempfile.TemporaryDirectory() as temp_root:
        bin_dir = Path(temp_root) / "bin"
        bin_dir.mkdir()
        fake_python = bin_dir / "python"
        fake_python.write_text("#!/bin/sh\nexit 64\n", encoding="utf-8")
        fake_python.chmod(fake_python.stat().st_mode | stat.S_IXUSR)

        command = r'''
set -euo pipefail
source tools/launcher/env.sh
PATH="$1"
buddyswitch_resolve_python
'''
        completed = subprocess.run(
            ["/bin/bash", "-c", command, "resolver-test", str(bin_dir)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("could not execute PATH python", completed.stderr)
```

- [ ] **Step 2: Run the focused tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_uses_only_path_python_and_overwrites_inherited_value \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_fails_when_path_has_no_python \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_rejects_unusable_path_python -q
```

Expected: all three tests fail because `buddyswitch_resolve_python` does not exist.

- [ ] **Step 3: Implement the resolver and call it from env initialization**

Add this function after `source "${BUDDYSWITCH_WORKSPACE_HELPER}"` and invoke it as the first operation in `buddyswitch_env_init`:

```bash
buddyswitch_resolve_python() {
  local python_path

  python_path="$(type -P python 2>/dev/null || true)"
  if [[ -z "${python_path}" || ! -x "${python_path}" ]]; then
    echo "BuddySwitch requires an executable 'python' on PATH." >&2
    return 1
  fi

  if [[ "${python_path}" != /* ]]; then
    case "${python_path}" in
      */*) python_path="$(cd "${python_path%/*}" && pwd)/${python_path##*/}" ;;
      *) python_path="$(pwd)/${python_path}" ;;
    esac
  fi

  if ! "${python_path}" -c 'import tomllib' >/dev/null 2>&1; then
    echo "BuddySwitch could not execute PATH python: ${python_path}" >&2
    return 1
  fi

  export BUDDYSWITCH_PYTHON="${python_path}"
}

buddyswitch_env_init() {
  local source_home source_codex_home shared_root

  buddyswitch_resolve_python || return $?
  source_home="${BUDDYSWITCH_SOURCE_HOME:-${HOME}}"
  source_codex_home="${BUDDYSWITCH_SOURCE_CODEX_HOME:-${CODEX_HOME:-${source_home}/.codex}}"
  shared_root="${BUDDYSWITCH_SHARED_ROOT:-${source_home}/.codex-buddyswitch}"
  shared_root="${shared_root%/}"
}
```

Do not read `BUDDYSWITCH_PYTHON` before the export assignment and do not add an alternate candidate.

- [ ] **Step 4: Run resolver and launcher smoke tests and verify GREEN**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts python -m pytest \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_uses_only_path_python_and_overwrites_inherited_value \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_fails_when_path_has_no_python \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_python_resolver_rejects_unusable_path_python \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_launcher_help_and_reset_flow -q
```

Expected: all selected tests pass; normal launcher startup resolves the interpreter without a launch argument.

- [ ] **Step 5: Commit the resolver slice**

```bash
git add tools/launcher/env.sh tests/test_buddyswitch_launcher.py
git commit -m "refactor: establish single Python resolver"
```

## Task 2: Propagate the resolved path through runtime execution

**Files:**

- Modify: `buddyswitch-codex`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tools/launcher/browser_cockpit.sh`
- Modify: `tools/launcher/cleanup.sh`
- Modify: `tools/launcher/daemon.sh`
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/instance.sh`
- Modify: `tools/launcher/runtime_broker.sh`
- Modify: `tools/launcher/workspace.sh`
- Modify: `scripts/runtime_kernel/lifecycle.py`
- Modify: `tools/launcher/central_daemon.py`
- Modify: `tools/launcher/daemon_core.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_browser_cockpit_launcher.py`
- Modify: `tests/test_central_daemon_service.py`
- Modify: `tests/test_daemon_core.py`
- Modify: `tests/test_runtime_broker.py`

- [ ] **Step 1: Change launcher and MCP assertions first**

Update `_assert_env_mcp_registration` and `_assert_cockpit_proxy_registration` to accept `expected_python: str` and assert that the first command after `--` equals that absolute path. Add a stale-config regression that writes a different absolute interpreter path and verifies generic MCP remove/add reconciliation.

```python
def _assert_env_mcp_registration(
    self,
    argv: list[object],
    *,
    actor_id: str,
    role: str,
    broker_socket: str,
    expected_python: str,
) -> None:
    self.assertEqual(argv[:3], ["mcp", "add", "buddyswitch-env"])
    separator_index = argv.index("--")
    self.assertEqual(argv[separator_index + 1], expected_python)
```

For each integration test, derive `expected_python` with `shutil.which("python", path=env["PATH"])` and assert it is non-null before comparing.

- [ ] **Step 2: Add child-process regressions first**

Patch `BUDDYSWITCH_PYTHON` to a sentinel absolute path while `subprocess.Popen` is mocked, then assert each command starts with the sentinel.

```python
configured_python = "/configured/runtime/python"
with patch.dict(os.environ, {"BUDDYSWITCH_PYTHON": configured_python}):
    payload = cli.start_central_daemon(paths)
self.assertTrue(payload["started"])
self.assertEqual(commands[0][0], configured_python)
```

Apply the same assertion to `daemon_core.start_daemon` and `runtime_kernel.lifecycle.start_broker_process`.

- [ ] **Step 3: Run the propagation tests and verify RED**

Initialize the new resolver, then run:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_central_daemon_service.py \
  tests/test_daemon_core.py \
  tests/test_runtime_broker.py -q
```

Expected: new interpreter-identity assertions fail because runtime paths still use historical commands or `sys.executable`.

- [ ] **Step 4: Replace every shell execution with the exported value**

In the nine shell files listed above, replace every executable invocation with the quoted value:

```bash
"${BUDDYSWITCH_PYTHON}" "${BUDDYSWITCH_RUNTIME_LOCK_HELPER}" -- "$@"
"${BUDDYSWITCH_PYTHON}" -c \
  'import json, sys; print(json.loads(sys.argv[1]))' \
  "${payload}"
```

This includes inline JSON/TOML parsing, runtime locks, config patching, app-server operations, browser helpers, cleanup, daemon control, instance operations, broker control, workspace path resolution, runtime skill installation, and the web management server. Do not introduce a shell wrapper that preserves the old command.

- [ ] **Step 5: Make env MCP desired state interpreter-aware**

Pass `${BUDDYSWITCH_PYTHON}` into the inline TOML check, compare `server["command"]` to that value, and register the MCP with the same value:

```bash
"${BUDDYSWITCH_PYTHON}" - \
  "${config_path}" \
  "${server_name}" \
  "${BUDDYSWITCH_PYTHON}" \
  "${BUDDYSWITCH_ENV_MCP_SERVER}" \
  "${BUDDYSWITCH_REPO_ROOT}" \
  "${BUDDYSWITCH_ACTOR_ID}" \
  "${active_role}" \
  "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}" <<'PY'
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
server_name = sys.argv[2]
expected_python = sys.argv[3]
server_path = sys.argv[4]
repo_root = sys.argv[5]
actor_id = sys.argv[6]
role = sys.argv[7]
broker_socket = sys.argv[8]

try:
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

server = payload.get("mcp_servers", {}).get(server_name)
if not isinstance(server, dict):
    raise SystemExit(1)
args = server.get("args")
if server.get("command") != expected_python or not isinstance(args, list):
    raise SystemExit(1)

required = [
    server_path,
    "--repo-root",
    repo_root,
    "--actor-id",
    actor_id,
    "--role",
    role,
    "--broker-socket",
    broker_socket,
]
if any(value not in args for value in required):
    raise SystemExit(1)
PY
```

The registration command must be:

```bash
buddyswitch_run_codex mcp add "${server_name}" -- \
  "${BUDDYSWITCH_PYTHON}" \
  "${BUDDYSWITCH_ENV_MCP_SERVER}" \
  --repo-root "${BUDDYSWITCH_REPO_ROOT}" \
  --actor-id "${BUDDYSWITCH_ACTOR_ID}" \
  --role "${active_role}" \
  --broker-socket "${BUDDYSWITCH_RUNTIME_BROKER_SOCKET}"
```

- [ ] **Step 6: Make browser MCP desired state interpreter-aware**

Replace `buddyswitch_browser_mcp_uses_cockpit_proxy` with a TOML-backed desired-state check that validates both command and proxy path. A stale command is a generic mismatch, not a special compatibility branch.

```bash
buddyswitch_browser_mcp_uses_cockpit_proxy() {
  local server_name="$1"
  local config_path

  config_path="$(buddyswitch_codex_config_path)"
  [[ -f "${config_path}" ]] || return 1

  "${BUDDYSWITCH_PYTHON}" - \
    "${config_path}" \
    "${server_name}" \
    "${BUDDYSWITCH_PYTHON}" \
    "${BUDDYSWITCH_BROWSER_COCKPIT_PROXY}" <<'PY'
import sys
import tomllib
from pathlib import Path

config_path = Path(sys.argv[1])
server_name = sys.argv[2]
expected_python = sys.argv[3]
proxy_path = sys.argv[4]

try:
    payload = tomllib.loads(config_path.read_text(encoding="utf-8"))
except Exception:
    raise SystemExit(1)

server = payload.get("mcp_servers", {}).get(server_name)
if not isinstance(server, dict):
    raise SystemExit(1)
args = server.get("args")
if server.get("command") != expected_python or not isinstance(args, list):
    raise SystemExit(1)
if proxy_path not in args:
    raise SystemExit(1)
PY
}
```

Register the browser MCP with `"${BUDDYSWITCH_PYTHON}"` as the command argument.

- [ ] **Step 7: Replace Python-owned child-process paths**

Use the environment value directly with no helper fallback. The three complete command arrays become:

```python
# scripts/runtime_kernel/lifecycle.py
command = [
    os.environ["BUDDYSWITCH_PYTHON"],
    str(broker_script),
    "serve",
    "--socket",
    str(paths.socket_path),
    "--pid-file",
    str(paths.pid_file),
    "--instance-json",
    str(instance_json_path),
    "--manifest",
    str(manifest_path),
]

# tools/launcher/central_daemon.py
command = [
    os.environ["BUDDYSWITCH_PYTHON"],
    str(Path(__file__).resolve()),
    "serve",
    "--shared-root",
    str(paths.shared_root),
]

# tools/launcher/daemon_core.py
command = [
    os.environ["BUDDYSWITCH_PYTHON"],
    str(INSTANCE_DAEMON_ENTRYPOINT.resolve()),
    "run",
    "--instance-json",
    str(instance_json),
]
```

Apply this to `scripts/runtime_kernel/lifecycle.py`, `tools/launcher/central_daemon.py`, and `tools/launcher/daemon_core.py`. Keep existing environment inheritance/copying so descendants receive the same value.

- [ ] **Step 8: Update shell-backed test fixtures used by these tests**

In `tests/test_buddyswitch_launcher.py` and `tests/test_browser_cockpit_launcher.py`, replace embedded shell fixture calls with:

```bash
"${BUDDYSWITCH_PYTHON}" - "${BUDDYSWITCH_TEST_CDP_STATE_FILE}" <<'PY'
```

This is required because those fake `curl` and browser scripts run inside the launcher environment and must prove propagation rather than accidentally selecting another interpreter.

- [ ] **Step 9: Verify syntax and focused runtime behavior**

Run:

```bash
bash -n buddyswitch-codex tools/launcher/*.sh
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_central_daemon_service.py \
  tests/test_daemon_core.py \
  tests/test_runtime_broker.py -q
```

Expected: shell syntax is valid and all selected tests pass with the same interpreter identity.

- [ ] **Step 10: Commit runtime propagation**

```bash
git add buddyswitch-codex tools/launcher scripts/runtime_kernel/lifecycle.py \
  tests/test_buddyswitch_launcher.py tests/test_browser_cockpit_launcher.py \
  tests/test_central_daemon_service.py tests/test_daemon_core.py tests/test_runtime_broker.py
git commit -m "refactor: propagate one Python runtime path"
```

## Task 3: Remove Python-version compatibility branches

**Files:**

- Modify: `scripts/env_manifest.py`
- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_buddyswitch_launcher.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_runtime_skills.py`
- Test: `tests/test_env_manifest_v2.py`

- [ ] **Step 1: Add a standard-parser source contract and run it RED**

Add this assertion to `tests/test_env_manifest_v2.py` without spelling compatibility package names as a source token:

```python
def test_manifest_loader_has_one_standard_toml_path(self) -> None:
    source = (ROOT / "scripts" / "env_manifest.py").read_text(encoding="utf-8")
    compatibility_package = "tom" + "li"
    self.assertIn("import tomllib", source)
    self.assertNotRegex(source, rf"\b{compatibility_package}\b")
    self.assertNotIn("_parse_toml_scalar", source)
    self.assertNotIn("_parse_toml_array", source)
```

Run:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_env_manifest_v2.py::EnvManifestV2Tests::test_manifest_loader_has_one_standard_toml_path -q
```

Expected: failure because the manual parser remains.

- [ ] **Step 2: Collapse `scripts/env_manifest.py` to `tomllib` only**

Replace the conditional import with `import tomllib`. Delete `_strip_toml_comment`, `_split_array_items`, `_parse_toml_scalar`, `_parse_toml_array`, and the manual branch in `_load_toml`. Keep only:

```python
def _load_toml(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - delegated to stdlib parser
        raise ManifestError(f"Invalid TOML in {path}: {exc}") from exc
```

- [ ] **Step 3: Remove all test and inline import fallbacks**

Use direct `import tomllib` in the four test modules and the `env.sh` inline MCP parser. Do not retain an exception branch, optional import, or alternate package.

- [ ] **Step 4: Verify manifest and config parsing**

Run:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_env_manifest_v2.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_runtime_skills.py \
  tests/test_buddyswitch_launcher.py -q
```

Expected: all selected tests pass through the standard parser.

- [ ] **Step 5: Commit compatibility removal**

```bash
git add scripts/env_manifest.py tools/launcher/env.sh \
  tests/test_env_manifest_v2.py tests/test_buddy_env_sandbox.py \
  tests/test_buddyswitch_launcher.py tests/test_env_layer_boundaries.py \
  tests/test_runtime_skills.py
git commit -m "refactor: remove Python version compatibility paths"
```

## Task 4: Put the test suite on the same configured interpreter

**Files:**

- Create: `tests/python_runtime.py`
- Modify all 98 tracked `tests/**/*.py` files only where they contain a Python shebang, old command, `sys.executable`, or generated Python executable.
- Specifically modify command/assertion files:
  - `tests/helpers/fake_codex.py`
  - `tests/test_black_box_tool_runtime.py`
  - `tests/test_browser_cockpit_launcher.py`
  - `tests/test_browser_cockpit_proxy.py`
  - `tests/test_browser_lazy_release_integration.py`
  - `tests/test_browser_runtime_manager.py`
  - `tests/test_buddy_env_profiles.py`
  - `tests/test_buddy_env_sandbox.py`
  - `tests/test_buddyswitch_launcher.py`
  - `tests/test_clean_runtime_environment.py`
  - `tests/test_cleanup_system.py`
  - `tests/test_env_client_payload_cli.py`
  - `tests/test_env_layer_boundaries.py`
  - `tests/test_env_native_mcp_projection.py`
  - `tests/test_env_tool_package_independence.py`
  - `tests/test_env_tool_router.py`
  - `tests/test_host_decision_surface_product_mode.py`
  - `tests/test_market_browser_evidence.py`
  - `tests/test_memory_removal_contract.py`
  - `tests/test_prepare_runtime_context.py`
  - `tests/test_repo_consistency.py`
  - `tests/test_run_env_services.py`
  - `tests/test_runless_runtime_contract.py`
  - `tests/test_runtime_broker.py`
  - `tests/test_runtime_skills.py`
  - `tests/test_search_env_tool.py`
  - `tests/test_submit_turn.py`
  - `tests/test_turn_runtime.py`
  - `tests/test_web_management.py`
  - `tests/test_app_server_client.py`
  - `tests/test_browser_page_expired_handler.py`
  - `tests/test_cdp_browser_session.py`
  - `tests/test_daemon_core.py`

- [ ] **Step 1: Add a test-only consumer with no resolution or fallback**

Create `tests/python_runtime.py`:

```python
"""Test access to the Python path already resolved by BuddySwitch."""

from __future__ import annotations

import os
from pathlib import Path


def configured_python() -> str:
    raw = os.environ.get("BUDDYSWITCH_PYTHON")
    if not raw:
        raise RuntimeError(
            "BUDDYSWITCH_PYTHON is not initialized; source tools/launcher/env.sh "
            "and call buddyswitch_env_init before running tests."
        )
    path = Path(raw)
    if not path.is_absolute():
        raise RuntimeError("BUDDYSWITCH_PYTHON must be an absolute path")
    return str(path)


PYTHON = configured_python()


def executable_python_source(source: str) -> str:
    return f"#!{PYTHON}\n{source.lstrip()}"
```

This module consumes the runtime value. It must not call `which`, inspect `PATH`, read the running interpreter, or supply a default.

- [ ] **Step 2: Replace all test subprocess interpreter selections**

Import `PYTHON` in every affected test module and replace old command strings and running-interpreter references with it:

```python
from tests.python_runtime import PYTHON

completed = subprocess.run(
    [PYTHON, "-c", script],
    cwd=ROOT,
    text=True,
    capture_output=True,
    check=False,
)
```

In `tests/helpers/fake_codex.py`, use `os.environ["BUDDYSWITCH_PYTHON"]` for its runtime probes because it runs as a generated child executable and already inherits the launcher environment.

- [ ] **Step 3: Replace generated Python shebangs with the configured absolute path**

For the six embedded-shebang test files identified in the audit, import `executable_python_source`, remove the shebang line from each embedded source string, and pass that complete source string through `executable_python_source` before `_write_exec` writes it. Do not alter the fixture's executable body or arguments.

When `tests/test_buddyswitch_launcher.py` copies `tests/helpers/fake_codex.py`, prepend the generated exact-path shebang instead of relying on a source-file shebang:

```python
def _write_fake_codex(self, path: Path) -> None:
    helper_path = ROOT / "tests" / "helpers" / "fake_codex.py"
    self._write_exec(
        path,
        executable_python_source(helper_path.read_text(encoding="utf-8")),
    )
```

- [ ] **Step 4: Correct tests that source helper shells outside the composition root**

In `tests/test_buddyswitch_launcher.py` and `tests/test_clean_runtime_environment.py`, replace direct `source tools/launcher/workspace.sh` setup for functions that execute Python with:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
```

Keep direct `workspace.sh` sourcing only in tests that call no Python-consuming function. This prevents tests from inventing a second resolver.

- [ ] **Step 5: Run converted test surfaces**

Run:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_app_server_client.py \
  tests/test_browser_cockpit_proxy.py \
  tests/test_browser_lazy_release_integration.py \
  tests/test_browser_page_expired_handler.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_cdp_browser_session.py \
  tests/test_env_native_mcp_projection.py \
  tests/test_repo_consistency.py \
  tests/test_runtime_broker.py -q
```

Expected: all selected tests pass and every spawned Python process receives the configured path.

- [ ] **Step 6: Commit test unification**

```bash
git add tests
git commit -m "test: use the configured Python runtime exclusively"
```

## Task 5: Remove historical residue and add a permanent repository gate

**Files:**

- Modify: every tracked `scripts/**/*.py`, `tools/launcher/*.py`, and `tests/**/*.py` file whose first line is a Python shebang.
- Change mode: `scripts/env_cleanup.py`
- Change mode: `scripts/env_manifest.py`
- Change mode: `tools/launcher/chrome_devtools_cockpit_proxy.py`
- Modify: `scripts/env/client.py`
- Modify: `README.md`
- Modify these 27 skill files:
  - `buddyswitch/skills/dev/debug-regression/SKILL.md`
  - `buddyswitch/skills/dev/enter-dev-workspace/SKILL.md`
  - `buddyswitch/skills/dev/finish-dev-change/SKILL.md`
  - `buddyswitch/skills/dev/handle-empty-source-root/SKILL.md`
  - `buddyswitch/skills/dev/handle-review-feedback/SKILL.md`
  - `buddyswitch/skills/dev/implement-scoped-change/SKILL.md`
  - `buddyswitch/skills/dev/parallelize-independent-dev-work/SKILL.md`
  - `buddyswitch/skills/dev/plan-thin-slice-implementation/SKILL.md`
  - `buddyswitch/skills/dev/prepare-review-readiness/SKILL.md`
  - `buddyswitch/skills/dev/pressure-test-dev-skill/SKILL.md`
  - `buddyswitch/skills/dev/read-implementation-context/SKILL.md`
  - `buddyswitch/skills/dev/request-dev-code-review/SKILL.md`
  - `buddyswitch/skills/dev/select-local-verification/SKILL.md`
  - `buddyswitch/skills/dev/write-implementation-report/SKILL.md`
  - `buddyswitch/skills/pm/decide-from-proof/SKILL.md`
  - `buddyswitch/skills/pm/define-scope/SKILL.md`
  - `buddyswitch/skills/pm/frame-product-direction/SKILL.md`
  - `buddyswitch/skills/pm/make-product-decision/SKILL.md`
  - `buddyswitch/skills/pm/read-product-context/SKILL.md`
  - `buddyswitch/skills/pm/sequence-product-work/SKILL.md`
  - `buddyswitch/skills/pm/synthesize-cross-functional-inputs/SKILL.md`
  - `buddyswitch/skills/pm/triage-track/SKILL.md`
  - `buddyswitch/skills/pm/write-acceptance-criteria/SKILL.md`
  - `buddyswitch/skills/pm/write-requirements/SKILL.md`
  - `buddyswitch/skills/shared/artifact-tool/SKILL.md`
  - `buddyswitch/skills/shared/task-management/SKILL.md`
  - `buddyswitch/skills/shared/track-tool/SKILL.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/test.md`
- Modify: `tools/launcher/assets/roles/design/AGENTS.md`
- Modify: `tools/launcher/assets/roles/dev/AGENTS.md`
- Modify: `tools/launcher/assets/roles/market/AGENTS.md`
- Modify: `tools/launcher/assets/roles/pm/AGENTS.md`
- Modify: `tools/launcher/assets/roles/test/AGENTS.md`
- Modify: `tests/test_repo_consistency.py`
- Modify functional expectation tests that currently assert old diagnostic text: `tests/test_buddyswitch_launcher.py`, `tests/test_host_decision_surface_product_mode.py`, and `tests/test_runtime_skills.py`.

- [ ] **Step 1: Add the no-residue consistency test and verify RED**

Add one tracked-file scan to `tests/test_repo_consistency.py`. Construct forbidden names so the test does not contain the residue it bans.

```python
def test_python_runtime_has_one_non_docs_entrypoint(self) -> None:
    old_command = "python" + "3"
    running_interpreter = "sys." + "executable"
    version_api = "sys." + "version_info"
    platform_version_api = "platform." + "python_version"
    compatibility_package = "tom" + "li"
    version_pattern = re.compile(r"\b[Pp]ython(?:\s*|[-_.]?)[0-9]+\.[0-9]+\b")
    residue: list[str] = []
    assignment_owners: list[str] = []
    resolver_owners: list[str] = []

    tracked = subprocess.check_output(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        text=True,
    ).split("\0")
    for relative in tracked:
        if not relative:
            continue
        path = Path(relative)
        if path.parts and path.parts[0] == "docs":
            continue
        try:
            text = (ROOT / path).read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for token in (old_command, running_interpreter, version_api, platform_version_api):
            if token in text:
                residue.append(f"{relative}: contains {token}")
        if re.search(rf"\b{compatibility_package}\b", text):
            residue.append(f"{relative}: contains compatibility TOML package")
        if version_pattern.search(text):
            residue.append(f"{relative}: contains a Python version literal")
        first_line = text.splitlines()[0] if text.splitlines() else ""
        if first_line.startswith("#!") and "python" in first_line.lower():
            residue.append(f"{relative}: contains a Python shebang")
        if "BUDDYSWITCH_PYTHON:-" in text:
            residue.append(f"{relative}: defaults BUDDYSWITCH_PYTHON")
        if "export BUDDYSWITCH_PYTHON=" in text:
            assignment_owners.append(relative)
        if re.search(r"\btype\s+-P\s+python\b", text):
            resolver_owners.append(relative)

    stage_rows = subprocess.check_output(
        ["git", "ls-files", "--stage", "*.py"],
        cwd=ROOT,
        text=True,
    ).splitlines()
    executable_python = [row.split(maxsplit=3)[3] for row in stage_rows if row.startswith("100755 ")]

    self.assertEqual(residue, [], msg="\n".join(residue))
    self.assertEqual(assignment_owners, ["tools/launcher/env.sh"])
    self.assertEqual(resolver_owners, ["tools/launcher/env.sh"])
    self.assertEqual(executable_python, [])
```

Run:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_python_runtime_has_one_non_docs_entrypoint -q
```

Expected: failure listing current shebangs, guidance, test residues, and executable file modes.

- [ ] **Step 2: Remove all non-doc Python source shebangs**

Use the tracked inventory as the exact mechanical boundary:

```bash
git grep -l '^#!/usr/bin/env python3$' -- \
  'scripts/**/*.py' 'scripts/*.py' 'tools/launcher/*.py' \
  'tests/**/*.py' 'tests/*.py'
```

Remove only the matching first line with `apply_patch`. The audited result is 107 production files plus 97 test files. Do not replace it with another Python shebang.

- [ ] **Step 3: Remove direct-execution file modes**

```bash
chmod -x scripts/env_cleanup.py scripts/env_manifest.py \
  tools/launcher/chrome_devtools_cockpit_proxy.py
```

All callers must already invoke these paths through `${BUDDYSWITCH_PYTHON}` before this step.

- [ ] **Step 4: Update active diagnostics and instructions**

Use this command form inside launched actor/runtime environments:

```bash
"$BUDDYSWITCH_PYTHON" scripts/turn_runtime.py status
```

Use this form for the env client:

```bash
"$BUDDYSWITCH_PYTHON" scripts/env/client.py context summarize
```

Update `README.md`, all listed skills, framework contracts, role AGENTS templates, `scripts/env/client.py`, and the root launcher diagnostic. In README's direct local diagnostic section, show initialization rather than manual interpreter assignment:

```bash
source tools/launcher/env.sh
buddyswitch_env_init
"$BUDDYSWITCH_PYTHON" scripts/env/client.py context summarize
```

- [ ] **Step 5: Remove semantic historical expectations from tests**

Tests that prohibit the retired env client path should assert the script path or operation is absent without reconstructing an old interpreter command. Tests that assert current diagnostics should expect `$BUDDYSWITCH_PYTHON` wording. No test should preserve an old command merely as a fixture string.

- [ ] **Step 6: Run the repository gate and verify GREEN**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_python_runtime_has_one_non_docs_entrypoint \
  tests/test_buddyswitch_launcher.py \
  tests/test_runtime_skills.py \
  tests/test_host_decision_surface_product_mode.py -q
```

Expected: all selected tests pass and the consistency test reports no residue.

- [ ] **Step 7: Commit residue removal and the permanent gate**

```bash
git add README.md buddyswitch/skills framework/contracts scripts tools/launcher tests
git commit -m "refactor: remove alternate Python entrypoints"
```

## Task 6: Final verification and acceptance

**Files:**

- Verify only; no new implementation files.

- [ ] **Step 1: Verify shell syntax**

```bash
bash -n buddyswitch-codex tools/launcher/*.sh
```

Expected: exit code 0 and no output.

- [ ] **Step 2: Verify the resolved runtime identity**

```bash
source tools/launcher/env.sh
buddyswitch_env_init
test -n "$BUDDYSWITCH_PYTHON"
test "${BUDDYSWITCH_PYTHON#/}" != "$BUDDYSWITCH_PYTHON"
"$BUDDYSWITCH_PYTHON" -c 'import os, sys; assert os.path.abspath(sys.executable)'
```

Expected: exit code 0; no manual interpreter variable was set before initialization.

- [ ] **Step 3: Run focused runtime verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest \
  tests/test_buddyswitch_launcher.py \
  tests/test_browser_cockpit_launcher.py \
  tests/test_browser_cockpit_proxy.py \
  tests/test_central_daemon_service.py \
  tests/test_daemon_core.py \
  tests/test_runtime_broker.py \
  tests/test_env_manifest_v2.py \
  tests/test_repo_consistency.py -q
```

Expected: all selected tests pass.

- [ ] **Step 4: Run the complete Python test suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=scripts "$BUDDYSWITCH_PYTHON" -m pytest tests -q
```

Expected: complete suite passes with no collection error and no tests selecting another interpreter.

- [ ] **Step 5: Run explicit residue scans outside docs**

```bash
if rg -n --hidden \
  --glob '!.git/**' \
  --glob '!.worktrees/**' \
  --glob '!docs/**' \
  'python3|sys\.(executable|version_info)|platform\.python_version|\btomli\b|[Pp]ython[[:space:]<>=~^-]*[0-9]+\.[0-9]+' .; then
  exit 1
fi

git ls-files -s '*.py' | awk '$1 == "100755" {print $4; failed=1} END {exit failed}'
```

Expected: both commands exit 0 without matches.

- [ ] **Step 6: Verify one assignment owner and one resolver owner**

```bash
rg -n 'export BUDDYSWITCH_PYTHON=' buddyswitch-codex tools scripts tests README.md buddyswitch framework
rg -n 'type -P python' buddyswitch-codex tools scripts tests README.md buddyswitch framework
```

Expected: each command returns exactly one line, both in `tools/launcher/env.sh`.

- [ ] **Step 7: Verify patch hygiene**

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; status contains only the intended single-entrypoint refactor and this approved plan artifact.

## Acceptance checklist

- [ ] `./buddyswitch-codex help` initializes Python automatically.
- [ ] The resolver only selects `python` from `PATH`.
- [ ] An inherited `BUDDYSWITCH_PYTHON` cannot create an override path.
- [ ] Missing/unusable `python` fails immediately with one clear error.
- [ ] `BUDDYSWITCH_PYTHON` is absolute and has exactly one assignment owner.
- [ ] All shell, Python child, MCP, test, fixture, diagnostic, and active guidance paths consume the same value.
- [ ] Existing MCP entries with a different command are replaced by generic desired-state reconciliation.
- [ ] No numeric Python version is hardcoded in non-`docs/**` code.
- [ ] No old command, Python shebang, `sys.executable`, alternate TOML package, or executable Python source file remains outside `docs/**`.
- [ ] No interpreter fallback or compatibility branch remains.
- [ ] Focused tests and the complete Python test suite pass through the resolved interpreter.
- [ ] `docs/**` historical content remains untouched except for this replacement plan.

## Explicit non-goals

- Do not create a virtual environment in this change.
- Do not add project dependency/version metadata.
- Do not add user-facing interpreter flags or environment overrides.
- Do not preserve direct executable Python scripts.
- Do not rewrite historical `docs/**` content.
- Do not broaden this work into unrelated runtime or product fallback removal. The removed compatibility paths are specifically interpreter-selection and Python-version compatibility paths.

## Future virtual-environment transition

When a project virtual environment becomes the chosen architecture, change only `buddyswitch_resolve_python` so its one target is the project environment's interpreter. Keep the exported `BUDDYSWITCH_PYTHON` contract and every consumer unchanged. Do not add `.venv` as a fallback beside PATH selection; replace the resolver target in one forward migration.
