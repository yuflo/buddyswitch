# BuddySwitch Runtime Automation Permissions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reduce BuddySwitch product-mode Codex approval prompts by keeping runtime writes inside explicitly writable roots and enabling network access inside `workspace-write`.

**Architecture:** Move BuddySwitch runtime locks from `${BUDDYSWITCH_SHARED_ROOT}.lock` into `${BUDDYSWITCH_SHARED_ROOT}/run/locks/`, then generate instance `CODEX_HOME/config.toml` with dynamic writable roots. The launcher keeps sandbox boundaries: it grants the shared runtime root, the repo git common directory, and temp directories, but not the full source checkout or `~/.codex`.

**Tech Stack:** Bash launcher, Python helper scripts, Codex CLI `config.toml`, pytest launcher/runtime tests.

---

## Confirmed Requirement

Current problem:
- `buddyswitch-codex` launcher commands are user-initiated and do not themselves cause the in-session Codex approval prompt.
- The approval prompt appears after Codex enters a buddy instance, when the agent runs runtime commands such as `python3 scripts/switch_runtime.py resolve ...`.
- Current runtime lock paths write outside `.codex-buddyswitch/`: `${BUDDYSWITCH_SHARED_ROOT}.lock` and `${BUDDYSWITCH_SHARED_ROOT}.lock.<pid>.proof`.
- Current instance config does not set `sandbox_mode`, `approval_policy`, `sandbox_workspace_write.network_access`, or `sandbox_workspace_write.writable_roots`.

Target behavior:
- Buddy runtime writes under `${BUDDYSWITCH_SHARED_ROOT}` are allowed automatically.
- Network access from commands is allowed automatically through `sandbox_workspace_write.network_access = true`.
- Writes outside the instance workspace and configured writable roots still require sandbox approval.
- Paths in config are generated dynamically from the current runtime environment; do not hard-code any developer home path.

Official Codex configuration basis:
- `sandbox_workspace_write.network_access = true` allows outbound network access inside `workspace-write`.
- `sandbox_workspace_write.writable_roots` adds writable roots when `sandbox_mode = "workspace-write"`.
- `--full-auto` is equivalent to `workspace-write` plus `on-request`; it still asks for workspace-external writes and network unless configured.
- Granular approval supports keeping `sandbox_approval = true` while suppressing other prompt categories.

## File Map

- Modify `tools/launcher/runtime_lock.py`: move launcher lock/proof paths under `${BUDDYSWITCH_SHARED_ROOT}/run/locks`.
- Modify `scripts/switch_runtime.py`: use the same in-root lock path for product-mode `resolve` and `persist`.
- Modify `scripts/runtime_store/projections.py`: use the same in-root lock path for read-side snapshot locking.
- Modify `tools/launcher/env.sh`: call an idempotent config patcher every time shared env is ensured.
- Create `tools/launcher/codex_config.py`: patch instance/shared Codex config with dynamic sandbox and writable-root settings without clobbering MCP/project config.
- Modify `tests/test_buddyswitch_launcher.py`: verify generated config grants specific roots and network access, and does not hard-code local user paths.
- Modify `tests/test_switch_runtime.py` and/or `tests/test_buddyswitch_launcher.py`: verify runtime lock files are created under `run/locks`, not beside shared root.
- Modify `tests/test_repo_consistency.py`: protect docs/config examples from reintroducing `${BUDDYSWITCH_SHARED_ROOT}.lock`.

## Runtime Permission Contract

Generated instance config must include this effective shape, with dynamic absolute paths:

```toml
sandbox_mode = "workspace-write"
approval_policy = { granular = {
  sandbox_approval = true,
  rules = false,
  mcp_elicitations = false,
  request_permissions = false,
  skill_approval = false,
} }

[sandbox_workspace_write]
network_access = true
writable_roots = [
  "<absolute BUDDYSWITCH_SHARED_ROOT>",
  "<absolute repo git common dir>",
  "/tmp",
  "<absolute TMPDIR when present>",
]
```

Dynamic path rules:
- `BUDDYSWITCH_SHARED_ROOT`: use the runtime value after `buddyswitch_env_init`, canonicalized with `Path(...).expanduser().resolve(strict=False)`.
- Repo git common dir: run `git -C "${BUDDYSWITCH_REPO_ROOT}" rev-parse --git-common-dir`; if relative, join it with `${BUDDYSWITCH_REPO_ROOT}`; canonicalize.
- `/tmp`: include unless Codex behavior later proves it is redundant; explicit inclusion keeps behavior clear.
- `$TMPDIR`: include only when set and non-empty; canonicalize; deduplicate roots.
- Do not include the full source checkout path.
- Do not include `~/.codex` as writable.

## Task 1: Move Runtime Lock Into Shared Root

**Files:**
- Modify: `tools/launcher/runtime_lock.py`
- Modify: `scripts/switch_runtime.py`
- Modify: `scripts/runtime_store/projections.py`
- Test: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_switch_runtime.py`

- [ ] **Step 1: Add failing tests for lock path location**

Add assertions that product-mode runtime commands no longer create `${shared_root}.lock`.

```python
lock_path = Path(f"{shared_root}.lock")
new_lock_path = shared_root / "run" / "locks" / "runtime.lock"

self.assertFalse(lock_path.exists())
self.assertTrue(new_lock_path.exists())
```

For lock proof paths, assert they are created under:

```python
shared_root / "run" / "locks"
```

Expected failure before implementation: tests see the old `${shared_root}.lock` path.

- [ ] **Step 2: Patch launcher lock helper**

In `tools/launcher/runtime_lock.py`, replace the old derived paths with a helper:

```python
def runtime_lock_dir(shared_root: str) -> Path:
    return Path(shared_root) / "run" / "locks"


def runtime_lock_path(shared_root: str) -> Path:
    return runtime_lock_dir(shared_root) / "runtime.lock"


def runtime_proof_path(shared_root: str) -> Path:
    return runtime_lock_dir(shared_root) / f"runtime.{os.getpid()}.proof"
```

Use:

```python
lock_path = runtime_lock_path(shared_root)
lock_path.parent.mkdir(parents=True, exist_ok=True)
lock_fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
proof_path = runtime_proof_path(shared_root)
```

- [ ] **Step 3: Patch product runtime lock**

In `scripts/switch_runtime.py`, replace:

```python
lock_path = Path(f"{shared_root}.lock")
```

with:

```python
lock_path = Path(shared_root) / "run" / "locks" / "runtime.lock"
```

Keep `lock_path.parent.mkdir(parents=True, exist_ok=True)`.

- [ ] **Step 4: Patch read-side projection lock**

In `scripts/runtime_store/projections.py`, replace both old lock path returns with:

```python
return Path(shared_root) / "run" / "locks" / "runtime.lock"
```

and:

```python
return derived_shared_root / "run" / "locks" / "runtime.lock"
```

- [ ] **Step 5: Verify lock movement**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_switch_runtime.py -q
```

Expected: tests pass and no test expects `${shared_root}.lock`.

## Task 2: Generate High-Automation Instance Codex Config

**Files:**
- Create: `tools/launcher/codex_config.py`
- Modify: `tools/launcher/env.sh`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing config tests**

Add a launcher test that starts or opens an instance with fake `codex`, then reads:

```python
config_text = (instance_root / "codex-home" / "config.toml").read_text(encoding="utf-8")
```

Assert:

```python
self.assertIn('sandbox_mode = "workspace-write"', config_text)
self.assertIn('network_access = true', config_text)
self.assertIn('sandbox_approval = true', config_text)
self.assertIn('rules = false', config_text)
self.assertIn('mcp_elicitations = false', config_text)
self.assertIn('request_permissions = false', config_text)
self.assertIn('skill_approval = false', config_text)
self.assertIn(str(shared_root), config_text)
self.assertIn(str(repo_root / ".git"), config_text)
self.assertIn('"/tmp"', config_text)
masked_config = config_text
for allowed_path in (str(shared_root), str(repo_root / ".git"), "/tmp", os.environ.get("TMPDIR", "")):
    if allowed_path:
        masked_config = masked_config.replace(allowed_path, "")
self.assertNotIn(str(Path.home()), masked_config)
self.assertNotIn(str(repo_root), config_text.replace(str(repo_root / ".git"), ""))
```

Add a second test with pre-existing MCP config:

```toml
[mcp_servers.chrome-devtools-cockpit]
command = "npx"
args = ["chrome-devtools-mcp@latest", "--browser-url=http://127.0.0.1:9222"]
```

Assert the MCP block remains after patching.

- [ ] **Step 2: Create config patcher**

Create `tools/launcher/codex_config.py` with this behavior:
- Arguments: `--config`, `--shared-root`, `--repo-root`, repeated `--temp-root`.
- Read existing config if present.
- Remove existing top-level `sandbox_mode = ...`.
- Remove existing top-level `approval_policy = ...`.
- Remove the existing `[sandbox_workspace_write]` table through the next TOML section.
- Append a managed block with dynamic values.
- Preserve other sections, including `[skills.bundled]`, `[features]`, `[mcp_servers.*]`, `[projects.*]`, and TUI state.

Core rendering:

```python
def toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def render_managed_block(roots: list[Path]) -> str:
    rendered_roots = ",\n  ".join(toml_string(str(root)) for root in roots)
    return f"""
# BuddySwitch managed automation permissions
sandbox_mode = "workspace-write"
approval_policy = {{ granular = {{
  sandbox_approval = true,
  rules = false,
  mcp_elicitations = false,
  request_permissions = false,
  skill_approval = false,
}} }}

[sandbox_workspace_write]
network_access = true
writable_roots = [
  {rendered_roots}
]
""".strip() + "\n"
```

Root calculation:

```python
def canonical(path: str) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def repo_git_common_dir(repo_root: Path) -> Path:
    output = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "--git-common-dir"],
        text=True,
    ).strip()
    git_dir = Path(output)
    if not git_dir.is_absolute():
        git_dir = repo_root / git_dir
    return canonical(str(git_dir))
```

Deduplicate roots while preserving order.

- [ ] **Step 3: Wire config patcher into launcher**

In `tools/launcher/env.sh`, define:

```bash
BUDDYSWITCH_CODEX_CONFIG_HELPER="${BUDDYSWITCH_LAUNCHER_DIR}/codex_config.py"
```

After `BUDDYSWITCH_CODEX_HOME` is created, call:

```bash
buddyswitch_patch_codex_config() {
  local config_path temp_root_args=()
  config_path="${BUDDYSWITCH_CODEX_HOME}/config.toml"

  if [[ -n "${TMPDIR:-}" ]]; then
    temp_root_args+=(--temp-root "${TMPDIR}")
  fi

  python3 "${BUDDYSWITCH_CODEX_CONFIG_HELPER}" \
    --config "${config_path}" \
    --shared-root "${BUDDYSWITCH_SHARED_ROOT}" \
    --repo-root "${BUDDYSWITCH_REPO_ROOT}" \
    --temp-root "/tmp" \
    "${temp_root_args[@]}"
}
```

Call `buddyswitch_patch_codex_config` inside `buddyswitch_ensure_shared_env` every time, not only when `config.toml` is missing.

- [ ] **Step 4: Preserve existing base config**

Keep the existing default blocks when a config file is newly created:

```toml
[skills.bundled]
enabled = false

[features]
plugins = false
```

The patcher appends the managed permissions block after those defaults.

- [ ] **Step 5: Verify config generation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py -q
```

Expected:
- Instance config contains `workspace-write`.
- Instance config contains `network_access = true`.
- Instance config contains dynamic writable roots for shared root, repo `.git`, `/tmp`, and `$TMPDIR` when present.
- Existing MCP config is preserved.

## Task 3: Existing Instance Refresh Behavior

**Files:**
- Modify: `tools/launcher/env.sh`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add test for existing instance config patch**

Create an existing instance with a config file containing only:

```toml
[features]
plugins = false
```

Run:

```bash
./buddyswitch-codex instance open <instance-id> -- --help
```

with fake `codex`, then assert config now includes:

```toml
sandbox_mode = "workspace-write"

[sandbox_workspace_write]
network_access = true
```

- [ ] **Step 2: Ensure open path calls config patch**

Because `instance_open_locked_bootstrap` already calls `buddyswitch_ensure_shared_env`, no new open-path hook should be necessary after Task 2. Verify that the test passes through the existing call path.

- [ ] **Step 3: State the runtime limitation**

Document in code comments or README only if needed:
- Existing already-running Codex TUI sessions do not reload `config.toml`.
- The new config applies on next `instance start`, `instance open`, or restarted Codex process.

## Task 4: Guard Against Regression

**Files:**
- Modify: `tests/test_repo_consistency.py`
- Modify: docs only if existing docs mention old lock paths.

- [ ] **Step 1: Add consistency checks**

Add assertions that source files do not contain old lock construction:

```python
self.assertNotIn('Path(f"{shared_root}.lock")', combined_runtime_sources)
self.assertNotIn('Path(f"{derived_shared_root}.lock")', combined_runtime_sources)
```

Add assertions that docs/spec examples do not hard-code the current developer home path:

```python
self.assertNotIn(str(Path.home() / ".codex-buddyswitch"), spec_text)
```

- [ ] **Step 2: Verify no stale docs**

Run:

```bash
rg -n "\\.codex-buddyswitch\\.lock|Path\\(f\\\"\\{shared_root\\}\\.lock|Path\\(f\\\"\\{derived_shared_root\\}\\.lock" .
```

Expected:
- No product docs instruct users to rely on `.codex-buddyswitch.lock`.
- No config examples hard-code a developer home path.
- Tests may mention old patterns only as negative assertions.

## Task 5: Full Verification

**Files:**
- No new files beyond previous tasks.

- [ ] **Step 1: Shell syntax**

Run:

```bash
bash -n buddyswitch-codex tools/launcher/env.sh tools/launcher/browser_cockpit.sh tools/launcher/instance.sh tools/launcher/cleanup.sh
```

Expected: no shell syntax output.

- [ ] **Step 2: Python compile**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile tools/launcher/codex_config.py tools/launcher/runtime_lock.py scripts/switch_runtime.py scripts/runtime_store/projections.py
```

Expected: no output.

- [ ] **Step 3: Focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_switch_runtime.py tests/test_repo_consistency.py -q
```

Expected: all pass.

- [ ] **Step 4: Current main regression suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_buddyswitch_launcher.py tests/test_cleanup_system.py tests/test_switch_runtime.py tests/test_repo_consistency.py -q
```

Expected: all pass.

- [ ] **Step 5: Manual config proof**

Start or open an instance with fake or real Codex, then inspect:

```bash
./buddyswitch-codex instance list
sed -n '1,160p' "${BUDDYSWITCH_SHARED_ROOT}/instances/<instance-id>/codex-home/config.toml"
```

Expected:
- `sandbox_mode = "workspace-write"`
- `network_access = true`
- `writable_roots` includes the actual shared root.
- `writable_roots` includes the actual repo git common dir.
- `writable_roots` includes `/tmp`.
- No root is hard-coded to a specific user's home.

## Self-Review

- Requirement coverage: covered runtime lock relocation, dynamic writable roots, network auto-allow, granular approval, existing instance refresh, and regression tests.
- External directory write confirmation: the plan explicitly grants only `${BUDDYSWITCH_SHARED_ROOT}`, repo git common dir, `/tmp`, and `$TMPDIR` when present.
- Network confirmation: the plan explicitly writes `sandbox_workspace_write.network_access = true`.
- Hard-coded path check: the plan requires dynamic path generation and negative tests against developer-home hard-coding.
- Boundary check: the plan does not grant write access to the full source checkout or `~/.codex`.
- Remaining risk: existing already-running Codex sessions must be restarted to load updated config.
