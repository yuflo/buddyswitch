# Buddybox Direct Host Files Test Plan

## Objective

Prove that BuddySwitch keeps the existing instance-local `workspace/buddybox`
directory as the persistent host file surface while removing the complex
host-facing `buddybox` env tool workflow. The host should write ordinary files
to the exported buddybox directory; product object mutation remains explicit
through product env tools.

## Current Bottleneck

The recent instance-private writable surface work correctly made
`workspace/buddybox` the only active persistent buddybox directory and kept
source/state/project boundaries tight. The remaining bottleneck is the exposed
host path: Codex CLI currently has to discover `buddybox.write`, build JSON
payloads, understand `logical_name`, avoid misleading `supports` entries, and
interpret artifact next-action hints just to save a file.

This test plan proves the replacement path end to end without transition or
dual main paths.

## Functional Requirements

| ID | Requirement |
| --- | --- |
| FR1 | Launcher binds `BUDDYSWITCH_BUDDYBOX_DIR` to `$BUDDYSWITCH_WORKSPACE_DIR/buddybox` for product-mode instances. |
| FR2 | Launcher creates `workspace/buddybox` and `instance/tmp` before Codex/app-server runtime work begins. |
| FR3 | Product-mode permissions allow persistent writes to `workspace/buddybox`, temporary writes to `instance/tmp`, and deny writes to workspace root, source root for non-dev buddies, state/project roots, and global `/tmp`. |
| FR4 | Product-mode shell environment sets `TMPDIR`, `TMP`, `TEMP`, and `TMPPREFIX` to instance-local temp paths so zsh here-docs do not depend on global `/tmp`. |
| FR5 | `context.get`, `context.summarize`, `context.list_sources`, and `turn_runtime.py status` expose writable-surface facts for buddybox and tmp without exposing fake methods such as `describe_capability` or `write_private_text`. |
| FR6 | `buddybox` is not a supported env tool and `python3 scripts/env/client.py buddybox ...` is not a valid host workflow. |
| FR7 | Manifest validation, manifest permissions, and runtime skill materialization no longer include `buddybox.read`, `buddybox.write`, `buddybox.delete`, or `buddybox-tool`. |
| FR8 | Role contracts, AGENTS templates, README, and shared skills point to direct file writes under `$BUDDYSWITCH_BUDDYBOX_DIR` and do not teach `buddybox write --payload`, `import-file`, or `logical_name` for host file writes. |
| FR9 | `artifact.attach_file` remains explicit product-object mutation, but it reads a real source file path under the active instance buddybox directory instead of `source_buddybox_logical_name`. |
| FR10 | Artifact `source_refs` and task refs no longer accept private buddybox `logical_name` refs; use artifact ids, track ids, task ids, notes, external refs, or explicit attachments instead. |
| FR11 | Direct writes to `$BUDDYSWITCH_BUDDYBOX_DIR` do not create or mutate artifact, track, task, request, message, or comment objects. |
| FR12 | Old buddybox storage paths remain inactive: no read, write, migration, fallback, or documented main path uses `buddyswitch/local/buddybox`, `state/buddyswitch/local/buddybox`, or `buddyswitch/content/buddybox`. |

## Test Matrix

### Launcher And Permission Tests

1. `tests/test_buddyswitch_launcher.py`
   - Extend the profile-mode config assertions to verify exactly one
     `/instances/<id>/workspace/buddybox` filesystem entry with value `write`.
   - Verify the instance environment exported by launcher setup includes
     `BUDDYSWITCH_BUDDYBOX_DIR` equal to `BUDDYSWITCH_WORKSPACE_DIR/buddybox`.
   - Verify no generated config grants write access to workspace root, instance
     root, shared root, state root, project workspace, or global `/tmp`.

2. `tests/test_buddy_env_sandbox.py`
   - Keep non-dev source-root denial coverage.
   - Add a sandbox command that writes:
     - `$BUDDYSWITCH_BUDDYBOX_DIR/probe.txt` and expects success.
     - `$BUDDYSWITCH_INSTANCE_TMP/probe.txt` and expects success.
     - `workspace-root-probe.txt` and expects failure.
     - `/tmp/buddyswitch-global-probe.txt` and expects failure.
   - Add a zsh here-doc check:
     ```sh
     cat > "$BUDDYSWITCH_BUDDYBOX_DIR/heredoc.txt" <<'EOF'
     ok
     EOF
     test "$(cat "$BUDDYSWITCH_BUDDYBOX_DIR/heredoc.txt")" = ok
     ```
   - Assert the sandbox environment has `TMPPREFIX` under
     `$BUDDYSWITCH_INSTANCE_TMP`.

3. `tests/test_clean_runtime_environment.py`
   - Replace direct `buddybox/prototypes` shell writes with
     `$BUDDYSWITCH_BUDDYBOX_DIR/prototypes`.
   - Keep the stale legacy projection cleanup test and assert no stale legacy
     file is copied into `workspace/buddybox`.

### Context And Status Tests

4. `tests/test_context_binding_env_tool.py`
   - Replace `buddybox_desc` expectations with `writable_surfaces`.
   - Assert:
     ```python
     surfaces["persistent_files"]["env"] == "BUDDYSWITCH_BUDDYBOX_DIR"
     surfaces["persistent_files"]["workspace_relative_root"] == "buddybox"
     surfaces["persistent_files"]["mutates_product_state"] is False
     surfaces["temporary_files"]["env"] == "BUDDYSWITCH_INSTANCE_TMP"
     ```
   - Assert serialized context does not contain
     `describe_capability`, `write_private_text`, `write_private_binary`,
     `logical_name_policy`, or `buddybox_desc`.
   - Assert `tool_catalog` and `operation_semantics` do not include the
     `buddybox` tool.

5. `tests/test_turn_runtime.py`
   - Update status coverage so `payload["env_tools"]` does not include
     `buddybox`.
   - Assert status includes writable-surface facts through the context/status
     projection rather than tool-catalog action schemas.

### Env Tool And CLI Removal Tests

6. `tests/test_repo_consistency.py`
   - Add a guard that `scripts/env/tools/buddybox` does not exist.
   - Add a guard that live runtime docs/skills/contracts do not contain
     `buddybox write --payload`, `buddybox.import_file`,
     `source_buddybox_logical_name`, `write_private_text`, or
     `write_private_binary`.
   - Keep existing guards against direct writes to runtime object state.

7. `tests/test_env_client_payload_cli.py`
   - Assert `python3 scripts/env/client.py buddybox write --payload '{}'`
     exits with argparse invalid-choice behavior.
   - Assert known tools such as `context` and `artifact` still work through
     CLI registration.

### Artifact Attachment Tests

8. `tests/test_artifact_env_tool.py`
   - Replace buddybox import setup with ordinary filesystem setup:
     ```python
     source = instance_root / "workspace" / "buddybox" / "screenshots" / "desktop.png"
     source.parent.mkdir(parents=True, exist_ok=True)
     source.write_bytes(b"\x89PNG\r\n")
     ```
   - Call:
     ```python
     artifact.attach_file({
         "artifact_id": artifact_id,
         "filename": "desktop.png",
         "source_path": str(source),
         "content_type": "image/png",
     })
     ```
   - Assert the response and persisted attachment metadata do not include
     `source_path` or any absolute filesystem path.
   - Assert the attached bytes are fetchable with `artifact.get_attachment`.
   - Assert `source_buddybox_logical_name` is rejected as an unsupported field.
   - Reject invalid sources:
     - missing file
     - directory
     - empty file
     - source under runtime object state
     - source under source checkout/project workspace
     - source under global `/tmp`
     - source outside active instance `workspace/buddybox`
     - symlink escape from `workspace/buddybox`

### Task And Source Ref Tests

9. `tests/test_task_env_tool.py`
   - Remove the success case for `{"type": "buddybox", "logical_name": ...}`.
   - Add a rejection case proving task refs reject `type="buddybox"`.
   - Keep artifact/track/task/note-style refs green.

10. `tests/test_artifact_env_tool.py` and source-ref focused tests
    - Assert artifact `source_refs` reject `type="buddybox"`.
    - Keep `artifact`, `track`, `task`, `external`, and `note` refs working
      according to existing read-scope rules.

### Skill, Manifest, And Role Contract Tests

11. `tests/test_runtime_skills.py`
    - Assert manifest skill registry does not include `buddybox-tool`.
    - Assert materialized runtime skills for PM, Design, Dev, Market, and Test
      do not include `buddybox-tool`.
    - Assert the Design `shape-prototype` skill mentions
      `$BUDDYSWITCH_BUDDYBOX_DIR` for private working files and does not mention
      `buddybox.import_file`.

12. `tests/test_repo_consistency.py`
    - Assert `scripts/env_manifest.py` no longer treats `buddybox` as a valid
      env-tool permission object.
    - Scan live docs and role contracts, excluding historical `docs/spec/**`
      and `docs/memo/**`, for retired host-path strings:
      - `buddybox write --payload`
      - `buddybox.import_file`
      - `source_buddybox_logical_name`
      - `logical_name values for private files`
      - `address them only through buddybox env tools`
    - Assert allowed live wording names `workspace/buddybox` and
      `BUDDYSWITCH_BUDDYBOX_DIR` as the file surface.

## Verification Commands

Run focused suites while implementing:

```sh
python3 -m pytest tests/test_buddy_env_sandbox.py tests/test_clean_runtime_environment.py -q
python3 -m pytest tests/test_context_binding_env_tool.py tests/test_turn_runtime.py -q
python3 -m pytest tests/test_artifact_env_tool.py tests/test_task_env_tool.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py tests/test_env_client_payload_cli.py -q
```

Run the broader runtime contract set before completion:

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
  tests/test_env_tool_semantic_contract.py \
  tests/test_black_box_tool_runtime.py \
  -q
```

Final grep check:

```sh
rg -n "buddybox write --payload|buddybox\\.import_file|source_buddybox_logical_name|write_private_text|write_private_binary|address them only through buddybox env tools" \
  AGENTS.md README.md framework buddyswitch scripts tests tools
```

Expected final grep result: no live host-path references. Historical matches in
`docs/spec/**` and `docs/memo/**` are acceptable only when they describe prior
work or this replacement plan.

## Definition Of Done

The task is complete only when the host can persist ordinary files through
`$BUDDYSWITCH_BUDDYBOX_DIR`, the old `buddybox` env tool path is gone from live
runtime discovery and skill guidance, artifact/task/source-ref paths no longer
use private buddybox logical names, and the verification commands above pass.
