# Instance Private Writable Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the unclear shared-state buddybox and global-temp writable surface with one instance-local persistent private file surface at `workspace/buddybox/`, while preserving Codex internal runtime writes.

**Architecture:** This is a direct forward replacement. Buddybox env tools, context, artifact attachment adoption, launcher startup, permission profile generation, cleanup, and tests all converge on the active instance workspace path `buddybox/`. Global `/tmp` and host `$TMPDIR` stop being product-mode shell writable roots; Codex gets an instance-local runtime temp directory instead.

**Tech Stack:** Bash launcher, Python runtime/env tools, Python unittest/pytest, Codex permission profile TOML, macOS Codex sandbox smoke.

---

## Non-Negotiable Direction

- Do not add a dual-path reader.
- Do not migrate old shared-state buddybox files into the new location.
- Do not keep `state/buddyswitch/local/buddybox` as a fallback.
- Do not keep `workspace/buddyswitch/local/buddybox` as an active or migrated buddybox projection.
- Do not rely on prompt text to prevent `/tmp` writes.
- Do not remove Codex runtime writable roots needed for `HOME`, `CODEX_HOME`, `XDG_CONFIG_HOME`, and instance-local temp.
- Do not touch main. Work only inside `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`.

## Target Runtime Layout

```text
<shared-root>/
  instances/
    inst-pm-xxxx/
      instance.json
      workspace/
        buddybox/
        projects/app
        AGENTS.md
      taskbox/pm/
      home/
      codex-home/
      xdg-config/
      tmp/
      runtime/
  project/
    workspace/
      projects/app
  state/
    buddyswitch/objects/
```

`workspace/buddybox/` is the persistent private work output surface for the active buddy instance. `tmp/` is ephemeral runtime scratch and must not be presented as a review or artifact destination.

## Files To Modify

- `scripts/env/repos/runtime_files.py`
  - Resolve buddybox root from active instance workspace.

- `scripts/env/repos/buddybox_files.py`
  - Stop appending active buddy id to the physical buddybox root.

- `scripts/env/domain/buddybox_workspace.py`
  - Expose a safe relative root hint: `workspace_relative_root = "buddybox"`.

- `scripts/env/tools/buddybox/_impl.py`
  - Import files only from runtime workspace and instance-local temp.
  - Reject importing from buddybox itself, shared state, source checkout, and global temp.

- `scripts/env/repos/artifacts.py`
  - Continue reading buddybox attachments through the updated repo helper.

- `tools/launcher/env.sh`
  - Bind `BUDDYSWITCH_INSTANCE_TMP`.
  - Create `workspace/buddybox` and `tmp`.
  - Write `instance_root` into instance records.
  - Start Codex with `TMPDIR`, `TMP`, and `TEMP` pointing at instance tmp.
  - Stop passing global `/tmp` and host `$TMPDIR` to product-mode permission generation.

- `tools/launcher/codex_config.py`
  - Add `workspace/buddybox` and `instance_root/tmp` to product-mode writable roots.
  - Keep `home`, `codex-home`, and `xdg-config`.
  - Reject global temp roots in product mode.

- `scripts/runtime_kernel/dispatcher.py`
  - Export `BUDDYSWITCH_INSTANCE_ROOT` and `BUDDYSWITCH_INSTANCE_TMP` for env tool dispatch.

- `tools/launcher/workspace.sh`
  - Ensure `workspace/buddybox`.
  - Remove stale old buddybox projections without migration.

- `scripts/env_cleanup.py`
  - Discover and delete `instances/*/workspace/buddybox` using instance owner scope.

- `scripts/env_profiles.py`
  - Change buddybox root contract to `buddybox`.

- `framework/contracts/buddy-env-profile.json`
  - Keep contract shape, update expectations through `scripts/env_profiles.py` tests.

- `buddyswitch/env-profiles/*.json`
  - Change `"root": "buddyswitch/local/buddybox/{buddy_id}"` to `"root": "buddybox"`.

- `tests/test_buddybox_env_tool.py`
- `tests/test_env_layer_boundaries.py`
- `tests/test_clean_runtime_environment.py`
- `tests/test_cleanup_system.py`
- `tests/test_buddyswitch_launcher.py`
- `tests/test_buddy_env_profiles.py`
- `tests/test_context_binding_env_tool.py`
- `tests/test_artifact_env_tool.py`
- `tests/test_repo_consistency.py`

## Task 1: Add Failing Buddybox Root Tests

**Files:**

- Modify: `tests/test_buddybox_env_tool.py`
- Test: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Update the instance fixture to include instance root and workspace**

Change `_instance_json()` so it creates and records both `instance_root` and `workspace_dir`:

```python
def _instance_json(self, *, buddy: str, instance_id: str) -> Path:
    instance_root = self._runtime_path(f"instances/{instance_id}")
    workspace_dir = instance_root / "workspace"
    workspace_dir.mkdir(parents=True, exist_ok=True)
    path = instance_root / "instance.json"
    path.write_text(
        json.dumps(
            {
                "instance_id": instance_id,
                "buddy": buddy,
                "status": "active",
                "instance_root": str(instance_root),
                "workspace_dir": str(workspace_dir),
                "browser_port": None,
                "updated_at": "2026-05-24T00:00:00Z",
            },
            ensure_ascii=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return path
```

- [ ] **Step 2: Replace old physical path assertions**

In lifecycle tests, assert files exist only under the active instance workspace:

```python
expected = self._runtime_path(f"instances/{instance_id}/workspace/buddybox/prototypes/hero.html")
self.assertTrue(expected.exists())
self.assertFalse(self._runtime_path("buddyswitch/local/buddybox/pm/prototypes/hero.html").exists())
self.assertFalse(self._runtime_path("state/buddyswitch/local/buddybox/pm/prototypes/hero.html").exists())
self.assertFalse(self._runtime_path(f"{_OLD_BUDDYBOX_ROOT}/pm/prototypes/hero.html").exists())
```

- [ ] **Step 3: Add same-buddy two-instance isolation test**

Add:

```python
def test_same_buddy_instances_have_isolated_buddybox_files(self) -> None:
    inst_a = "inst-pm-box-isolated-a"
    inst_b = "inst-pm-box-isolated-b"
    json_a = self._instance_json(buddy="pm", instance_id=inst_a)
    json_b = self._instance_json(buddy="pm", instance_id=inst_b)

    write_a = self._dispatch(
        instance_json=json_a,
        instance_id=inst_a,
        buddy="pm",
        action="write",
        args={"logical_name": "notes/private.md", "content": "a-only"},
    )
    self.assertTrue(write_a.get("ok"), msg=write_a)

    list_b = self._dispatch(
        instance_json=json_b,
        instance_id=inst_b,
        buddy="pm",
        action="list",
        args={"recursive": True},
    )
    self.assertTrue(list_b.get("ok"), msg=list_b)
    self.assertEqual(list_b.get("files"), [])

    read_b = self._dispatch(
        instance_json=json_b,
        instance_id=inst_b,
        buddy="pm",
        action="read",
        args={"logical_name": "notes/private.md"},
    )
    self.assertFalse(read_b.get("ok"), msg=read_b)
    self.assertEqual((read_b.get("error") or {}).get("code"), "E_BUDDYBOX_NOT_FOUND")
```

- [ ] **Step 4: Run the focused failing tests**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_buddybox_logical_name_text_binary_lifecycle -q
python3 -m pytest tests/test_buddybox_env_tool.py::BuddyboxEnvToolTests::test_same_buddy_instances_have_isolated_buddybox_files -q
```

Expected before implementation:

- lifecycle fails because current files are under old shared/runtime buddybox paths.
- isolation fails because same buddy instances share current buddybox storage.

## Task 2: Move Buddybox Repository Root To `workspace/buddybox`

**Files:**

- Modify: `scripts/env/repos/runtime_files.py`
- Modify: `scripts/env/repos/buddybox_files.py`
- Modify: `scripts/env/domain/buddybox_workspace.py`
- Test: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Replace buddybox root resolver**

In `scripts/env/repos/runtime_files.py`, replace:

```python
def buddybox_local_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    return BUDDYBOX_LOCAL_DIR
```

with:

```python
def buddybox_local_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    return runtime_workspace_root(instance_payload) / "buddybox"
```

- [ ] **Step 2: Stop appending buddy id to the physical root**

In `scripts/env/repos/buddybox_files.py`, replace:

```python
def active_buddy_root(*, active_buddy: str, instance_payload: dict[str, Any] | None = None) -> Path:
    return runtime_files.buddybox_local_dir(instance_payload) / active_buddy
```

with:

```python
def active_buddy_root(*, active_buddy: str, instance_payload: dict[str, Any] | None = None) -> Path:
    runtime_files.require_id(active_buddy, "buddy")
    return runtime_files.buddybox_local_dir(instance_payload)
```

- [ ] **Step 3: Expose a relative root hint without absolute path leakage**

In `scripts/env/domain/buddybox_workspace.py`, add this field to `build_buddybox_desc()`:

```python
"workspace_relative_root": "buddybox",
```

Keep `state_summary` based on the ensured root. Do not include an absolute root.

- [ ] **Step 4: Run buddybox tests**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -q
```

Expected after this task:

- Root and isolation tests pass.
- Import-file tests may still fail until Task 5 updates import boundaries.

## Task 3: Update Launcher Instance Directories And Records

**Files:**

- Modify: `tools/launcher/env.sh`
- Modify: `tests/test_buddyswitch_launcher.py`
- Test: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add instance tmp binding**

In `buddyswitch_env_bind_instance()`, add:

```bash
export BUDDYSWITCH_INSTANCE_TMP="${instance_root}/tmp"
```

after `BUDDYSWITCH_INSTANCE_ROOT`.

- [ ] **Step 2: Create buddybox and tmp directories during instance setup**

Add a small function near `buddyswitch_instance_ensure_taskbox()`:

```bash
buddyswitch_instance_ensure_private_writable_surface() {
  if [[ -z "${BUDDYSWITCH_WORKSPACE_DIR:-}" || -z "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
    echo "buddyswitch: instance workspace and tmp must be bound" >&2
    return 2
  fi
  mkdir -p "${BUDDYSWITCH_WORKSPACE_DIR}/buddybox"
  mkdir -p "${BUDDYSWITCH_INSTANCE_TMP}"
}
```

Call it during instance startup after workspace creation and before Codex starts. Use the existing startup flow location that already calls `buddyswitch_instance_ensure_taskbox`.

- [ ] **Step 3: Write `instance_root` into instance records**

In `buddyswitch_instance_write_record()`, pass `BUDDYSWITCH_INSTANCE_ROOT` to the Python snippet and add:

```python
"instance_root": instance_root,
```

The Python snippet should read:

```python
instance_root = sys.argv[6]
payload = {
    "instance_id": instance_id,
    "buddy": buddy,
    "status": status,
    "instance_root": instance_root,
    "workspace_dir": workspace_dir,
    "browser_port": None,
    "updated_at": now,
}
```

- [ ] **Step 4: Start Codex with instance-local temp env**

In `buddyswitch_run_codex()`, preserve current behavior when no instance is active. When `BUDDYSWITCH_INSTANCE_TMP` is set, create it and run:

```bash
TMPDIR="${BUDDYSWITCH_INSTANCE_TMP}" \
TMP="${BUDDYSWITCH_INSTANCE_TMP}" \
TEMP="${BUDDYSWITCH_INSTANCE_TMP}" \
HOME="${BUDDYSWITCH_HOME}" \
CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
codex "$@"
```

- [ ] **Step 5: Add launcher test assertions**

In `tests/test_buddyswitch_launcher.py`, update the instance start test that already inspects `instance_root` and `workspace_dir` to assert:

```python
self.assertTrue((instance_root / "workspace" / "buddybox").is_dir())
self.assertTrue((instance_root / "tmp").is_dir())
payload = json.loads((instance_root / "instance.json").read_text(encoding="utf-8"))
self.assertEqual(payload["instance_root"], str(instance_root))
```

- [ ] **Step 6: Run focused launcher tests**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -k "start and instance" -q
```

Expected:

- New assertions pass.
- Existing instance lifecycle tests continue to pass.

## Task 4: Replace Global Temp Permission With Instance Temp And Buddybox

**Files:**

- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/codex_config.py`
- Modify: `tests/test_env_layer_boundaries.py`
- Modify: `tests/test_clean_runtime_environment.py`
- Test: `tests/test_env_layer_boundaries.py`, `tests/test_clean_runtime_environment.py`

- [ ] **Step 1: Stop passing host temp roots in product mode**

In `buddyswitch_patch_codex_config()`, remove this logic:

```bash
if [[ -n "${TMPDIR:-}" ]]; then
  temp_root_args+=(--temp-root "${TMPDIR}")
fi
```

and remove the unconditional:

```bash
--temp-root "/tmp"
```

When `active_buddy` is set, pass only:

```bash
--temp-root "${BUDDYSWITCH_INSTANCE_TMP}"
```

If no active buddy is set, keep existing local-mode behavior unchanged.

- [ ] **Step 2: Add buddybox and instance tmp to product-mode writable roots**

In `_build_profile_mode_filesystem()` in `tools/launcher/codex_config.py`, add:

```python
buddybox_root = workspace_dir / "buddybox"
instance_tmp = instance_root / "tmp"
writable_roots: list[Path] = [home, codex_home, xdg_config_home, buddybox_root, instance_tmp]
```

Then stop extending product-mode writable roots from arbitrary `args.temp_root`. Validate `args.temp_root` contains only `instance_tmp`; reject any other temp root with:

```python
raise ValueError(f"product-mode temp root must be the active instance tmp: {candidate}")
```

- [ ] **Step 3: Keep global temp excluded**

Ensure generated product-mode filesystem entries do not include:

```text
"/tmp" = "write"
<host tempfile.gettempdir()> = "write"
```

Do not use `sandbox_workspace_write` in product profile mode; keep `[permissions.buddyswitch-runtime.filesystem]`.

- [ ] **Step 4: Update boundary tests**

In `tests/test_env_layer_boundaries.py`, add assertions for PM:

```python
self.assertIn(str((workspace_dir / "buddybox").resolve(strict=False)), writable_paths)
self.assertIn(str((instance_root / "tmp").resolve(strict=False)), writable_paths)
self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
self.assertNotIn("/tmp", writable_paths)
self.assertNotIn(str(Path(tempfile.gettempdir()).resolve(strict=False)), writable_paths)
```

For DEV, assert both source root and buddybox are writable:

```python
self.assertIn(str(project_source_root.resolve(strict=False)), writable_paths)
self.assertIn(str((runtime_workspace_dir / "buddybox").resolve(strict=False)), writable_paths)
```

- [ ] **Step 5: Update macOS sandbox smoke**

In `tests/test_clean_runtime_environment.py`, set:

```python
sandbox_env["TMPDIR"] = str(instance_root / "tmp")
sandbox_env["TMP"] = str(instance_root / "tmp")
sandbox_env["TEMP"] = str(instance_root / "tmp")
sandbox_env["BUDDYSWITCH_STATE_ROOT"] = str(shared_root / "state")
```

Use this shell script:

```bash
set +e
mkdir -p "$HOME/.cache" && echo home > "$HOME/.cache/probe.txt"; home=$?
mkdir -p "$CODEX_HOME/sessions" && echo codex > "$CODEX_HOME/sessions/probe.jsonl"; codex=$?
mkdir -p "$XDG_CONFIG_HOME/test" && echo xdg > "$XDG_CONFIG_HOME/test/probe.txt"; xdg=$?
mkdir -p "$TMPDIR" && echo tmp > "$TMPDIR/probe.txt"; inst_tmp=$?
mkdir -p buddybox/prototypes && echo buddybox > buddybox/prototypes/probe.txt; buddybox=$?
echo root > workspace-root-probe.txt; workspace_root=$?
echo global > /tmp/buddyswitch-global-probe.txt; global_tmp=$?
mkdir -p "$BUDDYSWITCH_STATE_ROOT/buddyswitch/objects" && echo state > "$BUDDYSWITCH_STATE_ROOT/buddyswitch/objects/probe.txt"; state=$?
echo "home=$home codex=$codex xdg=$xdg inst_tmp=$inst_tmp buddybox=$buddybox workspace_root=$workspace_root global_tmp=$global_tmp state=$state"
test "$home" = 0
test "$codex" = 0
test "$xdg" = 0
test "$inst_tmp" = 0
test "$buddybox" = 0
test "$workspace_root" != 0
test "$global_tmp" != 0
test "$state" != 0
```

- [ ] **Step 6: Run focused permission tests**

Run:

```bash
python3 -m pytest tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_clean_runtime_environment.py::CleanRuntimeEnvironmentTests::test_codex_sandbox_smoke_for_runtime_workspace -q
```

Expected:

- Config profile includes only intended writable roots.
- Sandbox smoke denies global temp while preserving Codex runtime writes.

## Task 5: Tighten Buddybox Import Boundaries

**Files:**

- Modify: `scripts/env/tools/buddybox/_impl.py`
- Modify: `scripts/env/repos/buddybox_files.py`
- Modify: `tests/test_buddybox_env_tool.py`
- Test: `tests/test_buddybox_env_tool.py`

- [ ] **Step 1: Add runtime helper for instance tmp**

In `scripts/env/repos/runtime_files.py`, add:

```python
def instance_tmp_dir(instance_payload: dict[str, Any] | None = None) -> Path:
    return instance_root_from_context(
        instance_json=None,
        instance_payload=instance_payload,
    ) / "tmp"
```

If `instance_payload` is missing, fall back to `BUDDYSWITCH_INSTANCE_ROOT` only when it is present:

```python
raw_root = os.environ.get("BUDDYSWITCH_INSTANCE_ROOT")
if isinstance(raw_root, str) and raw_root.strip():
    return Path(raw_root.strip()).expanduser().resolve(strict=False) / "tmp"
raise ValueError("instance context is required for instance tmp access")
```

- [ ] **Step 2: Replace system temp import allowance**

In `scripts/env/tools/buddybox/_impl.py`, replace:

```python
allowed_roots=(
    context.repos.runtime_files.runtime_workspace_root(context["instance_payload"]),
    Path(tempfile.gettempdir()),
),
blocked_roots=(
    context.repos.runtime_files.OBJECTS_ROOT,
    context.repos.runtime_files.LOCAL_ROOT,
),
```

with:

```python
workspace_root = context.repos.runtime_files.runtime_workspace_root(context["instance_payload"])
buddybox_root = context.repos.buddybox.active_buddy_root(
    active_buddy=active_buddy,
    instance_payload=context["instance_payload"],
)
instance_tmp = context.repos.runtime_files.instance_tmp_dir(context["instance_payload"])
allowed_roots=(workspace_root, instance_tmp)
blocked_roots=(
    buddybox_root,
    context.repos.runtime_files.OBJECTS_ROOT,
    context.repos.runtime_files.LOCAL_ROOT,
)
```

Use those variables in the `import_private_file()` call.

- [ ] **Step 3: Update source path error guidance**

Change `_source_path_field_error()` expected/example to avoid global temp:

```python
"expected": "existing local file path under the runtime workspace or active instance tmp",
"example": "tmp/chrome-devtools/desktop.png",
```

- [ ] **Step 4: Update import tests**

In `tests/test_buddybox_env_tool.py`, make valid sources live under:

```python
instance_root / "workspace" / "tmp" / "chrome-devtools" / "desktop.png"
instance_root / "tmp" / "chrome-devtools" / "desktop.png"
```

Add invalid sources under:

```python
instance_root / "workspace" / "buddybox" / "private.txt"
Path(tempfile.gettempdir()) / "buddyswitch-import-global-temp.txt"
```

- [ ] **Step 5: Run import tests**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -k "import_file" -q
```

Expected:

- Valid workspace and instance-tmp imports pass.
- Buddybox self-import, shared state, source checkout, global temp, symlink, and directory imports fail without writes.

## Task 6: Remove Old Buddybox Workspace Migration

**Files:**

- Modify: `tools/launcher/workspace.sh`
- Modify: `tests/test_clean_runtime_environment.py`
- Test: `tests/test_clean_runtime_environment.py`

- [ ] **Step 1: Ensure `workspace/buddybox` in instance mode**

Replace `buddyswitch_workspace_local_runtime_paths()` body:

```bash
buddyswitch_workspace_local_runtime_paths() {
  cat <<'EOF'
buddybox
EOF
}
```

- [ ] **Step 2: Remove buddybox migration loop**

In `buddyswitch_workspace_cleanup_stale_state_projections()`, delete the loop that migrates each old buddy directory to:

```bash
${state_root}/buddyswitch/local/buddybox/${buddy_id}
```

Replace it with removal of the stale old root:

```bash
workspace_buddybox_root="${workspace_dir}/buddyswitch/local/buddybox"
if [[ -L "${workspace_buddybox_root}" ]]; then
  rm -f "${workspace_buddybox_root}"
elif [[ -e "${workspace_buddybox_root}" ]]; then
  buddyswitch_workspace_force_remove_path "${workspace_buddybox_root}" || return $?
fi
```

Keep object projection migration unchanged. This task removes only old buddybox projection migration.

- [ ] **Step 3: Update stale cleanup tests**

In `tests/test_clean_runtime_environment.py`, replace `test_stale_local_runtime_data_is_migrated_to_state_root` with two tests:

```python
def test_stale_object_projection_is_migrated_to_state_root(self) -> None:
    ...
```

and:

```python
def test_stale_buddybox_projection_is_removed_without_migration(self) -> None:
    shared_root, workspace_dir, project_workspace_dir = self._prepare_runtime_workspace(buddy="pm")
    local_box = workspace_dir / "buddyswitch" / "local" / "buddybox" / "pm" / "coordination" / "a-log.md"
    local_box.parent.mkdir(parents=True, exist_ok=True)
    local_box.write_text("hello\n", encoding="utf-8")

    cleanup = self._run_cleanup(
        shared_root=shared_root,
        workspace_dir=workspace_dir,
        project_workspace_dir=project_workspace_dir,
        buddy="pm",
    )
    self.assertEqual(cleanup.returncode, 0, msg=cleanup.stderr)
    self.assertFalse((workspace_dir / "buddyswitch" / "local" / "buddybox").exists())
    self.assertFalse((shared_root / "state" / "buddyswitch" / "local" / "buddybox" / "pm" / "coordination" / "a-log.md").exists())
    self.assertFalse((workspace_dir / "buddybox" / "coordination" / "a-log.md").exists())
```

- [ ] **Step 4: Run runtime workspace tests**

Run:

```bash
python3 -m pytest tests/test_clean_runtime_environment.py -q
```

Expected:

- Old buddybox projections are removed, not migrated.
- Fresh workspaces include `buddybox`.

## Task 7: Update Cleanup To Instance Workspace Buddybox

**Files:**

- Modify: `scripts/env_cleanup.py`
- Modify: `tests/test_cleanup_system.py`
- Test: `tests/test_cleanup_system.py`

- [ ] **Step 1: Change cleanup relative directory constants**

Replace cleanup's active buddybox relative path from old `buddyswitch/local/buddybox` semantics to:

```python
BUDDYBOX_RELATIVE_DIR = "buddybox"
```

Update every use of `BUDDYBOX_RELATIVE_DIR` in `scripts/env_cleanup.py` to use the new `"buddybox"` relative directory.

- [ ] **Step 2: Make owner parsing work without buddy suffix**

Replace `_parse_buddybox_owner_path()` with logic that finds `workspace/buddybox/<logical_name>` and returns:

```python
buddy_root = Path(*parts[: marker_end])
logical_name = "/".join(parts[marker_end:])
```

The owner buddy is selected by `discover_instance_workspaces(..., buddy_filter=buddy)` before deletion, not by a physical buddy-id path segment.

- [ ] **Step 3: Change buddy cleanup plan**

In `build_cleanup_plan()` for `scope == "buddy"`, use:

```python
buddybox_relative_dir = BUDDYBOX_RELATIVE_DIR
```

instead of appending `/{buddy}`.

- [ ] **Step 4: Update cleanup tests**

In `tests/test_cleanup_system.py`, seed files:

```python
pm_owned = pm_workspace / "buddybox" / "notes" / "draft.md"
dev_owned = dev_workspace / "buddybox" / "notes" / "keep.md"
```

Remove fixtures under `workspace/buddyswitch/local/buddybox/<buddy>`.

Assert PM cleanup deletes only PM instance buddybox and all-data cleanup deletes every instance buddybox file.

- [ ] **Step 5: Run cleanup tests**

Run:

```bash
python3 -m pytest tests/test_cleanup_system.py -q
```

Expected:

- Cleanup follows instance owner scope.
- No shared-state buddybox paths are discovered as active private files.

## Task 8: Update Env Profiles, Contract Validation, And Context Wording

**Files:**

- Modify: `scripts/env_profiles.py`
- Modify: `buddyswitch/env-profiles/design.json`
- Modify: `buddyswitch/env-profiles/dev.json`
- Modify: `buddyswitch/env-profiles/market.json`
- Modify: `buddyswitch/env-profiles/pm.json`
- Modify: `buddyswitch/env-profiles/test.json`
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `tests/test_buddy_env_profiles.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Test: `tests/test_buddy_env_profiles.py`, `tests/test_context_binding_env_tool.py`

- [ ] **Step 1: Replace env profile root template**

In `scripts/env_profiles.py`, replace:

```python
BUDDYBOX_ROOT_TEMPLATE = "buddyswitch/local/buddybox/{buddy_id}"
```

with:

```python
BUDDYBOX_ROOT = "buddybox"
```

Replace `resolve_buddybox_root()` with:

```python
def resolve_buddybox_root(root_value: str, *, buddy_id: str) -> str:
    if root_value != BUDDYBOX_ROOT:
        raise EnvProfileError(
            f"buddybox.root must be {BUDDYBOX_ROOT!r}; got {root_value!r}"
        )
    return root_value
```

- [ ] **Step 2: Update every env profile**

Change each profile's buddybox block to:

```json
"buddybox": {
  "root": "buddybox"
}
```

- [ ] **Step 3: Clarify context wording**

In `context_sources_desc()`, update buddybox description to include relative workspace root:

```python
"workspace_relative_root": "buddybox",
```

Do not include absolute paths.

- [ ] **Step 4: Update profile and context tests**

In `tests/test_buddy_env_profiles.py`, assert:

```python
self.assertEqual(profile["buddybox"]["root"], "buddybox")
```

In context tests, assert serialized context includes `"workspace_relative_root": "buddybox"` and does not include old paths:

```python
packed = json.dumps(response, ensure_ascii=True)
self.assertIn("buddybox", packed)
self.assertNotIn("buddyswitch/local/buddybox", packed)
self.assertNotIn("state/buddyswitch/local/buddybox", packed)
self.assertNotIn("buddyswitch/content/buddybox", packed)
```

- [ ] **Step 5: Run profile and context tests**

Run:

```bash
python3 -m pytest tests/test_buddy_env_profiles.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
```

Expected:

- Profiles and context describe the new root only.

## Task 9: Add Static Consistency Gates

**Files:**

- Modify: `tests/test_repo_consistency.py`
- Test: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add old path/token guard**

Add a test that scans implementation directories and rejects old active buddybox roots:

```python
def test_instance_private_writable_surface_has_no_legacy_buddybox_roots(self) -> None:
    forbidden = (
        'BUDDYBOX_ROOT_TEMPLATE = "buddyswitch/local/buddybox/{buddy_id}"',
        'BUDDYBOX_LOCAL_DIR = LOCAL_ROOT / "buddybox"',
        'workspace_buddybox_root="${workspace_dir}/buddyswitch/local/buddybox"',
        'state/buddyswitch/local/buddybox',
        'buddyswitch/content/buddybox',
    )
    scan_targets = ["scripts", "tools", "buddyswitch/env-profiles", "framework/contracts"]
    for token in forbidden:
        completed = subprocess.run(
            ["rg", "-n", token, *scan_targets, "-g", "!**/__pycache__/**"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")
```

- [ ] **Step 2: Add global temp product-mode guard**

Add:

```python
def test_product_mode_does_not_grant_global_tmp_as_writable_root(self) -> None:
    forbidden = (
        '--temp-root "/tmp"',
        'Path(tempfile.gettempdir())',
        'system tempdir',
    )
    scan_targets = ["tools/launcher/env.sh", "scripts/env/tools/buddybox/_impl.py"]
    for token in forbidden:
        completed = subprocess.run(
            ["rg", "-n", token, *scan_targets],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertIn(completed.returncode, {0, 1}, msg=completed.stderr)
        self.assertEqual(completed.stdout.strip(), "", msg=f"{token}\n{completed.stdout}")
```

- [ ] **Step 3: Run consistency tests**

Run:

```bash
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

- Fails until all old tokens and global temp writable paths are removed from implementation.

## Task 10: Full Verification And Regression Sweep

**Files:**

- No source edits in this task.
- Test: focused and full test suites.

- [ ] **Step 1: Run focused suite**

Run:

```bash
python3 -m pytest tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_env_layer_boundaries.py -q
python3 -m pytest tests/test_clean_runtime_environment.py -q
python3 -m pytest tests/test_cleanup_system.py -q
python3 -m pytest tests/test_buddy_env_profiles.py -q
python3 -m pytest tests/test_context_binding_env_tool.py -q
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_repo_consistency.py -q
```

Expected:

- All pass.

- [ ] **Step 2: Run launcher regression**

Run:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
```

Expected:

- All pass.

- [ ] **Step 3: Run env contract regression**

Run:

```bash
python3 -m pytest tests/test_env_tool_response_contract.py tests/test_env_tool_payload_contract.py tests/test_env_layer_end_to_end.py -q
```

Expected:

- All pass.

- [ ] **Step 4: Run full suite**

Run:

```bash
python3 -m pytest tests -q
```

Expected:

- All pass or only documented environment skips, such as Codex CLI unavailable for macOS sandbox smoke.

- [ ] **Step 5: Manual product-mode smoke**

Start a PM instance:

```bash
./buddyswitch-codex instance start --buddy pm
```

Inside the launched Codex shell, verify these commands:

```bash
pwd
mkdir -p buddybox/manual && echo ok > buddybox/manual/probe.txt
echo fail > /tmp/buddyswitch-should-fail.txt
echo fail > workspace-root-probe.txt
```

Expected:

- `buddybox/manual/probe.txt` succeeds.
- global `/tmp` write fails under sandbox.
- workspace root write fails under sandbox.

## Completion Criteria

- `workspace/buddybox` is the only active persistent buddybox filesystem root.
- Global `/tmp` and host `$TMPDIR` are not writable roots in product-mode Codex permissions.
- Codex runtime internal writes still work through instance `home`, `codex-home`, `xdg-config`, and `tmp`.
- Old buddybox paths are not read, migrated, or used as fallback.
- Cleanup and context follow instance owner scope.
- Focused tests, launcher regression, env contract regression, and full test suite pass.

## Plan Self-Review

- Root cause coverage: Tasks 2, 4, 5, and 6 directly remove shared-state buddybox storage and global temp writable output.
- Directory remodel coverage: Tasks 2, 3, 6, 7, and 8 make `workspace/buddybox` the single active private file directory and remove old projection migration.
- Codex runtime safety coverage: Tasks 3 and 4 preserve instance `home`, `codex-home`, `xdg-config`, and `tmp` while denying global temp writes in product mode.
- Test coverage: Task 1 starts with failing buddybox behavior tests; Tasks 4, 5, 6, 7, 8, and 9 add boundary, sandbox, cleanup, profile, context, import, and consistency coverage.
- Forward cleanup coverage: The plan contains no fallback read, dual path, compatibility migration, or shared-state buddybox retention.
- Execution clarity: Each task names files, concrete code edits, exact verification commands, and expected outcomes.
