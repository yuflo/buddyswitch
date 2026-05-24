# Buddybox Direct Host Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the host-facing `buddybox` env tool workflow with direct file writes to the existing instance-local `workspace/buddybox` directory.

**Architecture:** Keep the physical `workspace/buddybox` surface and the recent sandbox boundaries. Remove `buddybox` from env tool discovery, manifest permissions, and skill guidance; expose the writable surface as runtime facts and an environment variable. Product object mutation stays explicit through artifact, track, task, request, message, and comment tools.

**Tech Stack:** Python runtime env tools, Bash launcher scripts, Codex permission profile TOML generation, pytest/unittest.

---

## Non-Negotiable Scope

- Do not rename `workspace/buddybox`.
- Do not keep a transition path where `buddybox.write`, `buddybox.import_file`, or `source_buddybox_logical_name` remain host-facing.
- Do not add a wrapper env tool for generic file writes.
- Do not make artifact creation implicit after file writes.
- Do not weaken source root, state root, project root, or global `/tmp` restrictions.

## File Map

- `tools/launcher/env.sh`: export `BUDDYSWITCH_BUDDYBOX_DIR`, ensure the directory exists, and set zsh-safe temp variables.
- `tools/launcher/app_server.sh`: propagate `BUDDYSWITCH_BUDDYBOX_DIR` and `TMPPREFIX` into app-server-managed turns.
- `tools/launcher/codex_config.py`: keep `workspace/buddybox` as the only persistent workspace write root and keep `instance/tmp` as the only temp write root.
- `scripts/env/repos/runtime_files.py`: keep `buddybox_local_dir()` as the source of truth and expose helper naming aligned with direct filesystem use.
- `scripts/env/tools/context/_impl.py`: replace `buddybox_desc` and fake `supports` with `writable_surfaces` facts.
- `scripts/env/tools/buddybox/**`: delete the env tool package.
- `scripts/env/tools/artifact/tool.py`: replace `source_buddybox_logical_name` with `source_path` on `artifact.attach_file`.
- `scripts/env/tools/artifact/_impl.py`: validate and read attachment source files from the active instance `workspace/buddybox`.
- `scripts/env/repos/artifacts.py`: replace `adopt_buddybox_attachment()` with `adopt_local_attachment()` that pins a validated file.
- `scripts/env/domain/source_refs.py`, `scripts/env/repos/artifacts.py`, `scripts/env/domain/tasks.py`, `scripts/env/tools/task/tool.py`: remove buddybox logical-name refs from product metadata.
- `buddyswitch/manifest.toml`: remove `buddybox-tool` skill and `buddybox.*` permissions.
- `scripts/env_manifest.py`: remove buddybox as a product env-tool permission object while keeping buddybox directory facts owned by launcher/profile context.
- `buddyswitch/skills/shared/buddybox-tool/`: delete the skill.
- `buddyswitch/skills/design/shape-prototype/SKILL.md` and asset template: replace buddybox import guidance with direct `$BUDDYSWITCH_BUDDYBOX_DIR` writes and explicit artifact attachment.
- `AGENTS.md`, `README.md`, `framework/contracts/*.md`: replace env-tool/logical-name guidance with concise direct-directory guidance.
- Tests listed in `docs/spec/2026-05-24-buddybox-direct-host-files-test-plan.md`.

## Task 1: Launcher Environment And Sandbox Contract

**Files:**
- Modify: `tools/launcher/env.sh`
- Modify: `tools/launcher/app_server.sh`
- Modify: `tests/test_buddy_env_sandbox.py`
- Modify: `tests/test_clean_runtime_environment.py`
- Modify: `tests/test_buddyswitch_launcher.py`

- [ ] **Step 1: Add failing launcher tests for direct buddybox env**

In `tests/test_buddy_env_sandbox.py`, extend
`test_non_dev_permission_profile_keeps_workspace_read_only_and_writes_only_safe_roots`
to assert `workspace/buddybox` remains the persistent write root and that no
new root replaces it:

```python
self.assertIn(str((workspace_dir / "buddybox").resolve(strict=False)), writable_paths)
self.assertNotIn(str(workspace_dir.resolve(strict=False)), writable_paths)
```

In the macOS sandbox test body, set and use the explicit env var:

```python
sandbox_env["BUDDYSWITCH_BUDDYBOX_DIR"] = str(workspace_dir / "buddybox")
sandbox_env["TMPPREFIX"] = str(instance_root / "tmp" / "zsh")
```

Add these command lines to the zsh sandbox script:

```sh
mkdir -p "$BUDDYSWITCH_BUDDYBOX_DIR/prototypes" && echo buddybox > "$BUDDYSWITCH_BUDDYBOX_DIR/prototypes/probe.txt"; buddybox=$?
cat > "$BUDDYSWITCH_BUDDYBOX_DIR/heredoc.txt" <<'EOF'
ok
EOF
heredoc=$?
test "$(cat "$BUDDYSWITCH_BUDDYBOX_DIR/heredoc.txt")" = ok; heredoc_read=$?
```

Assert:

```python
self.assertIn("buddybox=0", sandboxed.stdout)
self.assertIn("heredoc=0", sandboxed.stdout)
self.assertIn("heredoc_read=0", sandboxed.stdout)
```

- [ ] **Step 2: Run focused launcher tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_clean_runtime_environment.py tests/test_buddyswitch_launcher.py -q
```

Expected before implementation: failures showing `BUDDYSWITCH_BUDDYBOX_DIR`
and `TMPPREFIX` are missing or not propagated.

- [ ] **Step 3: Export buddybox and zsh temp environment**

In `tools/launcher/env.sh`, update `buddyswitch_env_bind_instance()`:

```bash
export BUDDYSWITCH_WORKSPACE_DIR="${instance_root}/workspace"
export BUDDYSWITCH_BUDDYBOX_DIR="${BUDDYSWITCH_WORKSPACE_DIR}/buddybox"
export BUDDYSWITCH_INSTANCE_TMP="${instance_root}/tmp"
```

Update `buddyswitch_instance_ensure_private_writable_surface()`:

```bash
if [[ -z "${BUDDYSWITCH_BUDDYBOX_DIR:-}" || -z "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
  echo "buddyswitch: instance buddybox and tmp must be bound" >&2
  return 2
fi
mkdir -p "${BUDDYSWITCH_BUDDYBOX_DIR}"
mkdir -p "${BUDDYSWITCH_INSTANCE_TMP}"
```

Update `buddyswitch_run_codex()` to export:

```bash
TMPDIR="${BUDDYSWITCH_INSTANCE_TMP}" \
TMP="${BUDDYSWITCH_INSTANCE_TMP}" \
TEMP="${BUDDYSWITCH_INSTANCE_TMP}" \
TMPPREFIX="${BUDDYSWITCH_INSTANCE_TMP}/zsh" \
BUDDYSWITCH_BUDDYBOX_DIR="${BUDDYSWITCH_BUDDYBOX_DIR}" \
HOME="${BUDDYSWITCH_HOME}" \
CODEX_HOME="${BUDDYSWITCH_CODEX_HOME}" \
XDG_CONFIG_HOME="${BUDDYSWITCH_XDG_CONFIG_HOME}" \
codex "$@"
```

In `tools/launcher/app_server.sh`, compute a safe prefix before the
`python3 "${BUDDYSWITCH_APP_SERVER_HELPER}" ensure` environment block:

```bash
local tmp_prefix
if [[ -n "${BUDDYSWITCH_INSTANCE_TMP:-}" ]]; then
  tmp_prefix="${BUDDYSWITCH_INSTANCE_TMP}/zsh"
else
  tmp_prefix="${TMPPREFIX:-}"
fi
```

Then propagate:

```bash
TMPPREFIX="${tmp_prefix}" \
BUDDYSWITCH_BUDDYBOX_DIR="${BUDDYSWITCH_BUDDYBOX_DIR:-${BUDDYSWITCH_WORKSPACE_DIR}/buddybox}" \
```

- [ ] **Step 4: Run focused launcher tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_clean_runtime_environment.py tests/test_buddyswitch_launcher.py -q
```

Expected after implementation: all selected tests pass.

## Task 2: Context And Status Writable-Surface Facts

**Files:**
- Modify: `scripts/env/tools/context/_impl.py`
- Modify: `scripts/env/tools/context/tool.py`
- Modify: `tests/test_context_binding_env_tool.py`
- Modify: `tests/test_turn_runtime.py`

- [ ] **Step 1: Add failing context tests**

In `tests/test_context_binding_env_tool.py`, replace
`test_context_outputs_describe_instance_private_buddybox_without_legacy_paths`
with a test named
`test_context_outputs_writable_surfaces_without_buddybox_tool_methods`.

Assert:

```python
surfaces = summarized.get("writable_surfaces")
self.assertIsInstance(surfaces, dict, msg=summarized)
persistent = surfaces.get("persistent_files")
self.assertEqual(persistent.get("env"), "BUDDYSWITCH_BUDDYBOX_DIR")
self.assertEqual(persistent.get("workspace_relative_root"), "buddybox")
self.assertFalse(persistent.get("mutates_product_state"))
temporary = surfaces.get("temporary_files")
self.assertEqual(temporary.get("env"), "BUDDYSWITCH_INSTANCE_TMP")
```

Assert serialized context excludes:

```python
for retired in ("buddybox_desc", "describe_capability", "write_private_text", "write_private_binary", "logical_name_policy"):
    self.assertNotIn(retired, packed)
```

In `tests/test_turn_runtime.py`, change status expectations:

```python
self.assertNotIn("buddybox", tools)
```

- [ ] **Step 2: Run context/status tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_turn_runtime.py -q
```

Expected before implementation: failures for missing `writable_surfaces` and
existing `buddybox` env tool/status entries.

- [ ] **Step 3: Implement writable surface projection**

In `scripts/env/tools/context/_impl.py`, add:

```python
def _build_writable_surfaces(instance_payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "persistent_files": {
            "kind": "host_writable_directory",
            "env": "BUDDYSWITCH_BUDDYBOX_DIR",
            "workspace_relative_root": "buddybox",
            "durability": "active_instance_persistent",
            "mutates_product_state": False,
        },
        "temporary_files": {
            "kind": "host_writable_directory",
            "env": "BUDDYSWITCH_INSTANCE_TMP",
            "durability": "active_instance_ephemeral",
            "mutates_product_state": False,
        },
    }
```

In `_current_context_sections()`, include:

```python
"writable_surfaces": _build_writable_surfaces(instance_payload),
```

Remove `buddybox_desc` from summary output. In `context_sources_desc()`, replace
the `buddybox` source descriptor with:

```python
"writable_surfaces": {
    "description": "Runtime writable filesystem surfaces for host-visible files.",
    "scope": "read-only writable-surface facts",
    "source_of_truth": "launcher instance environment and permission profile",
    "mutates_product_state": False,
    "grants_write_authority": False,
}
```

Update `context.get` and `context.summarize` action return metadata in
`scripts/env/tools/context/tool.py` so `returns` includes `writable_surfaces`
and no longer promises `buddybox_desc`.

- [ ] **Step 4: Run context/status tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_turn_runtime.py -q
```

Expected after implementation: selected tests pass.

## Task 3: Remove Buddybox Env Tool And Manifest Surface

**Files:**
- Delete: `scripts/env/tools/buddybox/__init__.py`
- Delete: `scripts/env/tools/buddybox/tool.py`
- Delete: `scripts/env/tools/buddybox/_impl.py`
- Delete: `tests/test_buddybox_env_tool.py`
- Modify: `buddyswitch/manifest.toml`
- Modify: `scripts/env_manifest.py`
- Modify: `tests/test_env_client_payload_cli.py`
- Modify: `tests/test_repo_consistency.py`
- Modify: `tests/test_runtime_skills.py`

- [ ] **Step 1: Add failing removal tests**

In `tests/test_repo_consistency.py`, add:

```python
def test_buddybox_env_tool_package_is_removed(self) -> None:
    self.assertFalse((ROOT / "scripts" / "env" / "tools" / "buddybox").exists())
    self.assertNotIn("buddybox", tool_catalog.supported_tools())
```

In `tests/test_env_client_payload_cli.py`, add:

```python
def test_buddybox_cli_resource_is_not_registered(self) -> None:
    completed = subprocess.run(
        ["python3", str(ROOT / "scripts" / "env" / "client.py"), "buddybox", "write", "--payload", "{}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    self.assertEqual(completed.returncode, 2)
    self.assertIn("invalid choice", completed.stderr)
```

In `tests/test_runtime_skills.py`, assert no materialized buddy lists
`buddybox-tool`.

- [ ] **Step 2: Run removal tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_repo_consistency.py tests/test_env_client_payload_cli.py tests/test_runtime_skills.py -q
```

Expected before implementation: failures because the env tool, permissions,
and skill still exist.

- [ ] **Step 3: Delete env tool and manifest entries**

Delete `scripts/env/tools/buddybox/`.

In `buddyswitch/manifest.toml`:

- remove the `[[skills]]` row with `id = "buddybox-tool"`;
- remove `"buddybox-tool"` from every buddy `skills` list;
- remove `buddybox.read`, `buddybox.write`, and `buddybox.delete` from every
  buddy `permissions` list.

In `scripts/env_manifest.py`, remove `"buddybox"` from the supported
permission objects in `_validate_permission()` and update
`buddy_authority_profile()` wording from:

```python
"while product writes are explicit env.tool operations over track/task/artifact/buddybox "
```

to:

```python
"while product writes are explicit env.tool operations over track/task/artifact "
```

Delete `tests/test_buddybox_env_tool.py` because the env tool contract no
longer exists. Coverage for the direct file surface lives in launcher,
sandbox, context, artifact, and repo consistency tests.

- [ ] **Step 4: Run removal tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_repo_consistency.py tests/test_env_client_payload_cli.py tests/test_runtime_skills.py tests/test_turn_runtime.py -q
```

Expected after implementation: selected tests pass and `buddybox` is absent
from tool discovery.

## Task 4: Artifact Attachments From Direct Buddybox Files

**Files:**
- Modify: `scripts/env/tools/artifact/tool.py`
- Modify: `scripts/env/tools/artifact/_impl.py`
- Modify: `scripts/env/repos/artifacts.py`
- Modify: `tests/test_artifact_env_tool.py`

- [ ] **Step 1: Add failing artifact attachment tests**

In `tests/test_artifact_env_tool.py`, replace buddybox import setup with
ordinary file writes under `instance_root / "workspace" / "buddybox"`.

Call `artifact.attach_file` with:

```python
args={
    "artifact_id": "art-design-attachment",
    "filename": "desktop.png",
    "source_path": str(source),
    "content_type": "image/png",
}
```

Assert:

```python
self.assertTrue(attached.get("ok"), msg=attached)
self.assertNotIn("source_path", json.dumps(attached, ensure_ascii=True))
self.assertNotIn(str(source), json.dumps(attached, ensure_ascii=True))
```

Add rejection coverage for:

```python
{"artifact_id": artifact_id, "filename": "desktop.png", "source_buddybox_logical_name": "screenshots/desktop.png"}
```

Expected rejection: unsupported payload field.

- [ ] **Step 2: Run artifact tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_artifact_env_tool.py -k "attachment or attach_file" -q
```

Expected before implementation: failures because `source_path` is unsupported
and `source_buddybox_logical_name` is still required.

- [ ] **Step 3: Change artifact attach schema**

In `scripts/env/tools/artifact/tool.py`, change `attach_file` schema:

```python
"required": ["artifact_id", "filename", "source_path"],
"properties": {
    "artifact_id": {"type": "string", "description": "Active-buddy-owned draft artifact id to attach a file to."},
    "filename": {"type": "string", "description": "Display filename without path separators."},
    "source_path": {
        "type": "string",
        "description": "Existing source file path under the active instance buddybox directory.",
    },
    "content_type": {"type": "string", "description": "Optional content type metadata for the attachment."},
}
```

Update `description`, `preconditions`, `reads`, and `does_not_write` text to
refer to an active instance buddybox file path rather than a logical name.

- [ ] **Step 4: Implement source path validation and adoption**

In `scripts/env/repos/artifacts.py`, replace `adopt_buddybox_attachment()` with
`adopt_local_attachment()`:

```python
def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def adopt_local_attachment(
    artifact_id: str,
    filename: str,
    created_by: str,
    source_path: Path,
    content_type: str | None,
    context: Any,
) -> tuple[dict[str, Any], dict[str, Any]]:
    artifact = get_artifact(artifact_id)
    if artifact is None:
        raise ValueError(f"artifact not found: {artifact_id}")

    root = context.repos.runtime_files.buddybox_local_dir(context.instance_payload).resolve(strict=False)
    try:
        resolved_source = source_path.expanduser().resolve(strict=True)
    except FileNotFoundError as exc:
        raise FileNotFoundError(str(source_path)) from exc
    if not _path_is_within(resolved_source, root):
        raise ValueError("source_path must resolve inside the active instance buddybox directory")
    if resolved_source.is_dir():
        raise IsADirectoryError(str(source_path))
    if not resolved_source.is_file():
        raise ValueError("source_path must resolve to a regular file")

    raw = resolved_source.read_bytes()
    if not raw:
        raise ValueError("source_path must reference a non-empty file")

    attachment_id = f"att-{uuid.uuid4().hex[:10]}"
    inferred_content_type = mimetypes.guess_type(resolved_source.name)[0] or "application/octet-stream"
    content_type_value = content_type.strip() if isinstance(content_type, str) and content_type.strip() else inferred_content_type
    timestamp = now_iso()
    attachment = {
        "attachment_id": attachment_id,
        "filename": _normalize_attachment_filename(filename),
        "content_type": content_type_value,
        "size_bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
        "created_by": created_by,
        "created_at": timestamp,
    }

    target_path = attachment_file(artifact_id, attachment_id)
    runtime_files.require_runtime_workspace_write_root()
    target_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        os.link(resolved_source, target_path)
    except OSError:
        shutil.copyfile(resolved_source, target_path)

    updated_artifact = dict(artifact)
    updated_artifact["attachments"] = attachment_summaries(artifact_id) + [attachment]
    updated_artifact["updated_at"] = timestamp
    saved = save_artifact(updated_artifact)
    return saved, attachment
```

In `scripts/env/tools/artifact/_impl.py`, read `source_path`, reject missing
or non-string values, call `adopt_local_attachment()`, and ensure rejection
responses use `correctable_fields=["source_path"]`.

- [ ] **Step 5: Run artifact tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_artifact_env_tool.py -q
```

Expected after implementation: artifact tests pass without
`source_buddybox_logical_name`.

## Task 5: Remove Buddybox Logical-Name Metadata From Product Objects

**Files:**
- Modify: `scripts/env/domain/source_refs.py`
- Modify: `scripts/env/repos/artifacts.py`
- Modify: `scripts/env/domain/tasks.py`
- Modify: `scripts/env/tools/task/tool.py`
- Modify: `tests/test_artifact_env_tool.py`
- Modify: `tests/test_task_env_tool.py`

- [ ] **Step 1: Add failing metadata tests**

In `tests/test_task_env_tool.py`, replace the buddybox ref success case with:

```python
rejected = self._dispatch(
    instance_json=instance_json,
    tool="task",
    action="create",
    args={"task_id": "task-dev-bad-buddybox-ref", "title": "Bad ref", "refs": [{"type": "buddybox", "logical_name": "prototype/index.html"}]},
)
self.assertFalse(rejected.get("ok"), msg=rejected)
self.assertIn("unsupported", json.dumps(rejected, ensure_ascii=True).lower())
```

In `tests/test_artifact_env_tool.py`, add a create/update metadata rejection
case for:

```python
"source_refs": [{"type": "buddybox", "logical_name": "prototype/index.html"}]
```

- [ ] **Step 2: Run metadata tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_task_env_tool.py tests/test_artifact_env_tool.py -q
```

Expected before implementation: tests fail because buddybox refs are accepted.

- [ ] **Step 3: Remove buddybox ref type support**

In `scripts/env/domain/source_refs.py`, remove `"buddybox"` from
`_ALLOWED_TYPES`, delete `validate_buddybox_ref_logical_name()`, and remove
the `elif ref_type == "buddybox"` branch.

In `scripts/env/repos/artifacts.py`, remove `_validate_buddybox_ref_logical_name()`
and the `elif ref_type == "buddybox"` branch in `_normalize_source_refs()`.

In `scripts/env/domain/tasks.py`, remove `"buddybox"` from
`ALLOWED_TASK_REF_TYPES` and delete the branch that accepts `logical_name`.

In `scripts/env/tools/task/tool.py`, remove `logical_name` from the ref schema
and replace prose mentions of buddybox refs with generic private notes or
artifact/task/track ids.

- [ ] **Step 4: Run metadata tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_task_env_tool.py tests/test_artifact_env_tool.py -q
```

Expected after implementation: selected tests pass and buddybox logical-name
refs are rejected.

## Task 6: Skills, Role Contracts, And Live Documentation

**Files:**
- Delete: `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- Delete directory if empty: `buddyswitch/skills/shared/buddybox-tool/`
- Modify: `buddyswitch/skills/design/shape-prototype/SKILL.md`
- Modify: `buddyswitch/skills/design/shape-prototype/assets/design-handoff-template.md`
- Modify: `AGENTS.md`
- Modify: `README.md`
- Modify: `framework/contracts/pm.md`
- Modify: `framework/contracts/design.md`
- Modify: `framework/contracts/dev.md`
- Modify: `framework/contracts/market.md`
- Modify: `framework/contracts/test.md`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Add failing live guidance tests**

In `tests/test_repo_consistency.py`, add a scan over live guidance paths:

```python
def test_live_guidance_uses_direct_buddybox_directory_not_env_tool_payloads(self) -> None:
    paths = [
        ROOT / "AGENTS.md",
        ROOT / "README.md",
        ROOT / "framework" / "contracts",
        ROOT / "buddyswitch" / "skills",
    ]
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for root in paths
        for path in ([root] if root.is_file() else root.rglob("*"))
        if path.is_file() and path.suffix in {".md", ".toml"}
    ).lower()
    for forbidden in (
        "buddybox write --payload",
        "buddybox.import_file",
        "source_buddybox_logical_name",
        "write_private_text",
        "write_private_binary",
        "address them only through buddybox env tools",
    ):
        self.assertNotIn(forbidden, text)
    self.assertIn("buddyswitch_buddybox_dir", text)
```

- [ ] **Step 2: Run live guidance tests and confirm failure**

Run:

```sh
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected before implementation: failures for `buddybox-tool` and old guidance.

- [ ] **Step 3: Remove buddybox tool skill and update concise guidance**

Delete `buddyswitch/skills/shared/buddybox-tool/`.

In `AGENTS.md` and role contracts, replace the private file guidance with:

```markdown
Persistent private host files are written under `$BUDDYSWITCH_BUDDYBOX_DIR`, which resolves to the active instance `workspace/buddybox`. Product objects still require explicit env tools; do not edit `buddyswitch/objects/**` or old buddybox runtime paths directly.
```

In `buddyswitch/skills/design/shape-prototype/SKILL.md`, replace step 4 with:

```markdown
4. When visual evidence will reduce downstream ambiguity, write or copy the file under `$BUDDYSWITCH_BUDDYBOX_DIR`, attach it with `artifact.attach_file` using `source_path`, and cite the resulting `attachment_id` in the handoff artifact.
```

In the design handoff template, replace "Attached through generic artifact
attachments after buddybox import" with "Attached through explicit artifact
attachments from a file under `$BUDDYSWITCH_BUDDYBOX_DIR`."

- [ ] **Step 4: Run live guidance tests and confirm pass**

Run:

```sh
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected after implementation: selected tests pass.

## Task 7: Full Runtime Contract Verification

**Files:**
- No new implementation files.
- Verify all files changed in Tasks 1-6.

- [ ] **Step 1: Run focused suites**

Run:

```sh
python3 -m pytest \
  tests/test_buddy_env_sandbox.py \
  tests/test_buddyswitch_launcher.py \
  tests/test_clean_runtime_environment.py \
  tests/test_context_binding_env_tool.py \
  tests/test_turn_runtime.py \
  tests/test_artifact_env_tool.py \
  tests/test_task_env_tool.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  tests/test_env_client_payload_cli.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run semantic/runtime contract suites**

Run:

```sh
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
```

Expected: both suites pass with the supported env tool set excluding
`buddybox`.

- [ ] **Step 3: Run final live-reference scan**

Run:

```sh
rg -n "buddybox write --payload|buddybox\\.import_file|source_buddybox_logical_name|write_private_text|write_private_binary|address them only through buddybox env tools" \
  AGENTS.md README.md framework buddyswitch scripts tests tools
```

Expected: no output.

- [ ] **Step 4: Inspect git status**

Run:

```sh
git status --short
```

Expected: changes are limited to this worktree and match the planned files.
Do not revert unrelated pre-existing changes such as
`docs/memo/2026-05-23-cowork-forward-stages.md` unless the user explicitly
requests it.

## Completion Criteria

The implementation is complete when:

- `$BUDDYSWITCH_BUDDYBOX_DIR` is the documented and runtime-visible persistent
  host file entry point.
- `workspace/buddybox` remains the physical directory.
- `buddybox` is gone from env tool discovery, manifest permissions, and runtime
  skills.
- Artifact attachments use explicit `source_path` under the active instance
  buddybox directory.
- Product metadata no longer accepts buddybox logical-name refs.
- All verification commands in Task 7 pass.
