# Black-Box Tool Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Runtime behavior changes must follow `superpowers:test-driven-development`: write and verify the failing test before production code is edited.

**Goal:** Replace the current per-tool package runtime with a compact black-box env.tool runtime where each tool exposes one public `tool.py` protocol, the host invokes tools through `env.tool_runtime`, and BuddySwitch state access is limited to `ToolContext` capabilities.

**Architecture:** Use a repo-local, in-process, protocol-driven runtime. `scripts/env/tool_runtime` owns definition types, context capabilities, canonical results, registry discovery, catalog projection, generic CLI metadata, and env.tool dispatch. `scripts/env/tools/<tool>/tool.py` owns each tool's external protocol and lazy invocation entrypoint; old `contract.py`, `semantics.py`, `handlers.py`, `cli.py`, and `service.py` files are deleted rather than adapted.

**Tech Stack:** Python 3.9-compatible runtime code, `dataclasses`, `argparse`, `importlib`, `pkgutil`, JSON-compatible input/output schemas, `unittest`/`pytest`, AST boundary tests, broker-routed env.tool integration tests.

---

## Source Inputs

Read before editing:

- `docs/memo/2026-05-20-black-box-tool-runtime-memo.md`
- `docs/spec/2026-05-20-black-box-tool-runtime-test-plan.md`
- `scripts/env/tools/catalog.py`
- `scripts/env/tools/dispatch.py`
- `scripts/env/tools/router.py`
- `scripts/env/tools/responses.py`
- `scripts/env/tools/model.py`
- `scripts/env/tools/discovery.py`
- `scripts/env/tools/cli_helpers.py`
- every current `scripts/env/tools/<tool>/contract.py`
- every current `scripts/env/tools/<tool>/semantics.py`
- every current `scripts/env/tools/<tool>/handlers.py`
- every current `scripts/env/tools/<tool>/service.py`
- every current `scripts/env/tools/<tool>/cli.py`
- `scripts/env/client.py`
- `scripts/runtime_kernel/dispatcher.py`
- `scripts/runtime_kernel/client.py`
- `scripts/runtime_kernel/coordinator.py`
- `scripts/runtime_kernel/lifecycle.py`
- `scripts/turn_runtime.py`
- `scripts/env/repos/runtime_files.py`
- `scripts/env_store.py`
- `scripts/env_legacy_store.py`
- `tests/runtime_root_test_helper.py`
- `tests/test_clean_runtime_environment.py`
- existing env.tool behavior tests under `tests/test_*_env_tool.py`

Also inspect the clean runtime environment commit currently on this branch. This plan is a second
stage after that repair, not an alternative to it.

## Objective And Key Problems

This is the complete black-box runtime replacement, not a partial cleanup.

The current state already supports per-tool package ownership, but it is not black-box because the
host runtime still reads several public files inside each tool package and selected tool services can
reach BuddySwitch runtime internals directly. The repair must make these boundaries true:

1. Host runtime imports only `env.tools.<tool>.tool`.
2. Catalog, operation semantics, payload fields, CLI action lists, and runtime status are projections
   of `ToolDefinition`.
3. Tool implementation code cannot import `env.repos`, `env.domain`, `env_manifest`,
   `runtime_kernel`, or sibling tools.
4. Tool implementation code mutates runtime state only through `ToolContext`.
5. Old per-tool public modules and old shared env.tools runtime modules are deleted in the final
   state.

## Clean Runtime Baseline

The clean runtime environment repair is now the implementation baseline:

```text
runtime workspace root = host-visible, safe-to-search workspace
runtime state root     = broker-owned shared/state
```

Black-box runtime changes must preserve these contracts:

- `scripts/runtime_kernel/dispatcher.py` keeps `BUDDYSWITCH_STATE_ROOT`,
  `runtime_files.refresh_runtime_roots_from_env()`, and `runtime_workspace_root` /
  `runtime_state_root` / `env_store_root` status fields while switching env.tool dispatch to
  `env.tool_runtime.registry`.
- `ToolContext` is the only layer that may call host-owned `env.repos`, `env.domain`,
  `env_manifest`, browser state helpers, or `runtime_files`.
- Tool `_impl.py` files must not derive storage from `workspace_dir`, `BUDDYSWITCH_STATE_ROOT`,
  `buddyswitch/objects/**`, or `buddyswitch/local/buddybox/**`.
- Runtime objects and buddybox private files remain state-root-backed through capability methods,
  not normal workspace file paths.
- `context` and `buddybox` migrations must preserve the clean-runtime behavior that host-facing
  guidance points to env tools and logical names, not direct runtime storage paths.

## Forward Rules

- Do not build a plugin platform, marketplace, remote loader, subprocess sandbox, event bus,
  workflow engine, permission framework, compatibility framework, or schema DSL.
- Do not create import aliases such as `env.tools.catalog -> env.tool_runtime.registry`.
- Do not keep old and new tool systems as supported side-by-side paths.
- Do not preserve per-tool `cli.py` flag builders. The final CLI is generic:
  `python3 scripts/env/client.py <tool> <action> --payload '<json-object>'`.
- Do not regress the clean runtime environment contract: no workspace state projections, no direct
  buddybox storage guidance, no sandbox escalation prompt dependency, and no writes through the
  host-visible workspace.
- During local implementation, an intermediate commit may be temporarily red. The final branch must
  have one active runtime path and passing verification.

## Target File Structure

Create:

```text
scripts/env/tool_runtime/__init__.py
scripts/env/tool_runtime/definition.py
scripts/env/tool_runtime/context.py
scripts/env/tool_runtime/results.py
scripts/env/tool_runtime/registry.py
tests/test_black_box_tool_runtime.py
```

Create for every shipped tool:

```text
scripts/env/tools/<tool>/tool.py
scripts/env/tools/<tool>/_impl.py
```

Modify:

```text
scripts/env/client.py
scripts/runtime_kernel/dispatcher.py
scripts/runtime_kernel/client.py
scripts/runtime_kernel/coordinator.py
scripts/turn_runtime.py
scripts/runtime_kernel/lifecycle.py
tests/test_env_tool_package_independence.py
tests/test_env_tool_payload_contract.py
tests/test_env_tool_response_contract.py
tests/test_env_client_payload_cli.py
tests/test_env_tool_router.py
tests/test_clean_runtime_environment.py
tests/test_buddy_env_sandbox.py
tests/test_env_layer_boundaries.py
tests/test_env_layer_end_to_end.py
tests/test_runtime_skills.py
tests/test_repo_consistency.py
README.md
docs/memo/buddyswitch-parallel-modular-architecture.md
```

Delete in the final state:

```text
scripts/env/tools/catalog.py
scripts/env/tools/cli_helpers.py
scripts/env/tools/discovery.py
scripts/env/tools/dispatch.py
scripts/env/tools/model.py
scripts/env/tools/responses.py
scripts/env/tools/router.py
scripts/env/tools/<tool>/contract.py
scripts/env/tools/<tool>/semantics.py
scripts/env/tools/<tool>/handlers.py
scripts/env/tools/<tool>/cli.py
scripts/env/tools/<tool>/service.py
```

Keep:

```text
scripts/env/tools/__init__.py
scripts/env/tools/<tool>/__init__.py
scripts/env/domain/*.py
scripts/env/repos/*.py
```

`env.domain` and `env.repos` remain host-owned implementation details used by `ToolContext`
capabilities, not by tool packages.

## Runtime Protocol

`scripts/env/tool_runtime/definition.py` owns the external protocol:

```python
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

MUTATES_NONE = "none"
MUTATES_RUNTIME_OBJECTS = "runtime_objects"
MUTATES_RUNTIME_FILES = "runtime_files"
MUTATES_BROKER_TOKEN = "broker_token"
MUTATES_BROWSER_SESSION = "browser_session"


@dataclass(frozen=True)
class ActionDefinition:
    name: str
    title: str
    description: str
    input_schema: Mapping[str, Any]
    output_schema: Mapping[str, Any]
    kind: str
    mutates: str
    required_permission: str
    authority: str
    preconditions: tuple[str, ...] = ()
    returns: tuple[str, ...] = ()
    risk_hints: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    title: str
    description: str
    cli_resource: str
    command: str
    scope: str
    capability_boundary: str
    use_when: tuple[str, ...]
    do_not_use_when: tuple[str, ...]
    actions: tuple[ActionDefinition, ...]
    backend_model: Mapping[str, Any] = field(default_factory=dict)
```

Definition validation rules:

- tool id is non-empty lowercase text;
- action names are non-empty lowercase text with underscores;
- action names are unique within a tool;
- `input_schema["type"] == "object"`;
- `input_schema["additionalProperties"] is False`;
- `input_schema["properties"]` is an object;
- output schema is an object or `{"$ref": "ToolResult"}`;
- `mutates` is one of the mutation constants.

`scripts/env/tools/<tool>/tool.py` follows this exact public shape:

```python
from __future__ import annotations

from typing import Any

from env.tool_runtime.context import ToolContext
from env.tool_runtime.definition import ActionDefinition, ToolDefinition

# Populate with concrete values from the shipped tool/action tables in this plan.
DEFINITION = ToolDefinition(
    id="message",
    title="Message",
    description="Direct buddy-to-buddy inbox messaging.",
    cli_resource="message",
    command="python3 scripts/env/client.py message <action> --payload '<json-object>'",
    scope="direct buddy-to-buddy inbox messaging",
    capability_boundary="Active runtime instance and manifest buddy ids remain authoritative.",
    use_when=("send a message to another buddy", "read active-buddy inbox messages"),
    do_not_use_when=("record shared track progress",),
    actions=(
        ActionDefinition(
            name="send",
            title="message.send",
            description="Send a direct message to another buddy.",
            input_schema={
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "to_buddy": {"type": "string"},
                    "content": {"type": "string"},
                    "reply_to": {"type": "string"},
                },
                "required": ["to_buddy", "content"],
            },
            output_schema={"$ref": "ToolResult"},
            kind="write",
            mutates="runtime_objects",
            required_permission="message.write",
            authority="message.active_buddy",
            preconditions=("target buddy exists in manifest",),
            returns=("message",),
        ),
    ),
)


def invoke(*, action: str, args: dict[str, Any], context: ToolContext) -> dict[str, Any]:
    from . import _impl

    return _impl.invoke(action=action, args=args, context=context)
```

`tool.py` must not import `_impl` at module load time. That keeps catalog/protocol loading separate
from selected implementation loading.

## ToolContext Capabilities

`scripts/env/tool_runtime/context.py` owns the only bridge from tools to BuddySwitch runtime state.

Expose this concrete surface:

```text
context.active_buddy
context.instance_id
context.instance_json
context.instance_payload
context.manifest
context.manifest_path
context.objects
context.buddybox
context.browser
context.catalog
context.now()
context.new_id(prefix)
```

`context.objects` exposes current object operations:

```text
list_tasks()
create_task(task_id, title, summary, status, track_id)
get_task(task_id)
update_task(task_id, title, summary, status, track_id)
archive_task(task_id)
list_tracks()
create_track(track_id, title, outcome, appetite, now, state, health)
get_track(track_id)
update_track_now(track_id, now, state, health)
add_track_material(track_id, artifact_id, label, summary)
add_track_update(track_id, summary, kind, refs)
add_track_proof(track_id, artifact_id, label, summary)
archive_track(track_id)
get_artifact(artifact_id)
create_artifact_revision(artifact_id, title, summary, template, body, source_refs, read_claim, track_id, publish_as, label)
update_artifact_metadata(artifact_id, title, summary, template, body, source_refs, read_claim)
add_comment(target_type, target_id, content, reply_to, artifact_revision_id, anchor, mentions)
list_comments(target_type, target_id, status)
send_message(to_buddy, content, reply_to)
list_messages(buddy)
runtime_sources()
```

`context.buddybox` exposes:

```text
describe()
list_files(logical_name=None, recursive=False, limit=None)
read_file(logical_name, encoding=None)
write_file(logical_name, content=None, content_base64=None, content_type=None)
delete_file(logical_name)
```

`context.browser` exposes:

```text
status()
request(query, backend=None, engine=None)
open_browser(query, engine=None)
issue_evidence_token(target_type, target_id, mode=None)
approve_downgrade(target_type, target_id, reason)
```

`context.catalog` exposes registry projections needed by the `context` tool:

```text
tool_catalog()
operation_semantics()
compact_tool_affordances()
tool_catalog_errors()
```

These methods may call `env.repos`, `env.domain`, `env_manifest`, browser state helpers, and runtime
files internally. Tool packages may not import those internals directly.

`ToolContext` must use the clean runtime root model already implemented in
`scripts/env/repos/runtime_files.py`: runtime object writes and buddybox private files are backed by
`STATE_ROOT`, while `runtime_workspace_root(instance_payload)` remains a host-visible reporting and
context surface. Do not pass filesystem roots into tool `_impl.py` files. Tool code receives
capabilities, logical ids, and logical buddybox names only.

## Tool Migration Map

Move each current service handler into the selected tool's `_impl.invoke` switch:

| Tool | Action to migrated function |
| --- | --- |
| `artifact` | `get -> get_artifact_for_active_buddy`; `create_revision -> create_artifact_revision`; `update_metadata -> update_artifact_metadata` |
| `buddybox` | `desc -> describe_buddybox_for_active_buddy`; `list -> list_buddybox_for_active_buddy`; `read -> read_buddybox_for_active_buddy`; `write -> write_buddybox_for_active_buddy`; `delete -> delete_buddybox_for_active_buddy` |
| `comment` | `add -> add_comment`; `list -> list_comments` |
| `context` | `get -> get_context`; `summarize -> summarize_context`; `list_sources -> list_sources` |
| `evidence` | `issue_browser -> issue_browser_for_active_instance`; `approve_downgrade -> approve_downgrade_for_active_instance` |
| `message` | `send -> send_message`; `list -> list_messages` |
| `search` | `status -> status_for_active_instance`; `request -> request_for_active_instance`; `open_browser -> open_browser_for_active_instance` |
| `task` | `create -> create_task_for_active_buddy`; `list -> list_tasks_for_active_buddy`; `get -> get_task_for_active_buddy`; `update -> update_task_for_active_buddy`; `archive -> archive_task_for_active_buddy` |
| `track` | `create -> create_track_for_pm`; `list -> list_tracks_for_active_buddy`; `open -> open_track_for_active_buddy`; `update_now -> update_now_for_active_buddy`; `add_material -> add_material_to_track`; `add_update -> add_update_to_track`; `add_proof -> add_proof_to_track`; `archive -> archive_track_for_pm` |

During migration, replace direct repo/domain calls inside these functions with the matching
`ToolContext` capability method. Keep tool-specific payload normalization and response wording local
to `_impl.py`.

Use the current clean-runtime versions of the old service files as migration sources. In particular,
preserve `context` guidance that avoids direct `buddyswitch/objects/**` and
`buddyswitch/local/buddybox/**` path instructions, and preserve buddybox behavior that stores by
logical name through the state-root-backed repository helpers.

## Task 1: Add Failing Black-Box Architecture Tests

**Files:**

- Create: `tests/test_black_box_tool_runtime.py`
- Modify: `tests/test_env_tool_package_independence.py`

- [ ] **Step 1: Add shipped tool/action constants**

Use the required tool/action table from `docs/spec/2026-05-20-black-box-tool-runtime-test-plan.md`.

- [ ] **Step 2: Add tests for one public `tool.py` entrypoint**

Implement tests that assert:

- every shipped package has `tool.py`;
- old per-tool files are absent;
- `DEFINITION.id` equals the package name;
- action sets match the required table;
- every action has a closed object input schema.

- [ ] **Step 3: Add tests for metadata-only catalog import**

Use a subprocess that imports `env.tool_runtime.registry`, calls `env_tools_description()` and
`operation_semantics()`, and asserts no private implementation, repo, domain, or runtime kernel
module was loaded.

- [ ] **Step 4: Add AST boundary tests**

Reject imports of `env.repos`, `env.domain`, `env_manifest`, `runtime_kernel`, sibling tools, and
old shared `env.tools.*` runtime modules under `scripts/env/tools/<tool>/`.

- [ ] **Step 5: Add probe add/delete test**

Create a temporary `env.tools.probe.tool` package inside the test, extend `env.tools.__path__`,
invalidate caches, dispatch `probe.ping`, remove the path, clear registry cache, and assert the
probe disappears.

- [ ] **Step 6: Run focused tests and confirm failure**

Run:

```bash
python3 -m pytest tests/test_black_box_tool_runtime.py -q
```

Expected before implementation: failures on missing `env.tool_runtime`, old per-tool files still
existing, and old shared env.tools runtime modules still existing.

## Task 2: Add `env.tool_runtime` SDK

**Files:**

- Create: `scripts/env/tool_runtime/__init__.py`
- Create: `scripts/env/tool_runtime/definition.py`
- Create: `scripts/env/tool_runtime/results.py`
- Create: `scripts/env/tool_runtime/context.py`
- Create: `scripts/env/tool_runtime/registry.py`

- [ ] **Step 1: Implement definition dataclasses and validation**

Add `ActionDefinition`, `ToolDefinition`, mutation constants, and `validate_definition(definition)`.

- [ ] **Step 2: Move canonical response helpers into `results.py`**

Move the behavior from `scripts/env/tools/responses.py` into `env.tool_runtime.results`.

Important simplification: `results.next_action_option(tool, action, reason, mutates=None,
preconditions=None, source_refs=None)` must not import catalog or registry.
It should accept optional `mutates`, `preconditions`, and `source_refs`, and default
`source_refs` to `runtime_context.operation_semantics['<tool>.<action>']`.

- [ ] **Step 3: Implement ToolContext and capability classes**

Create `ToolContext`, `RuntimeObjectAccess`, `BuddyboxAccess`, `BrowserAccess`, and
`RegistryCatalogAccess`. Move repo/domain/runtime-file imports into this module.

- [ ] **Step 4: Implement registry discovery and projection**

`registry.py` must provide:

```text
clear_cache()
discover_tool_ids()
load_definition(tool)
supported_tools()
supported_actions(tool)
get_definition(tool)
get_action_definition(tool, action)
payload_fields_for_action(tool, action)
tool_catalog_errors()
env_tools_description()
operation_semantics()
compact_tool_affordances()
action_mutates(tool, action)
dispatch_env_tool_request(payload, active_buddy, instance_id, instance_json, instance_payload, manifest, manifest_path=None)
```

`dispatch_env_tool_request(payload, active_buddy, instance_id, instance_json, instance_payload,
manifest, manifest_path=None)` replaces `env.tools.router.dispatch_env_tool_request`.
`action_mutates(tool, action)` returns the action mutation constant or `None` for unknown tools or
actions; retry and lock callers must treat `None` as write-risky.

- [ ] **Step 5: Verify SDK import without loading tools**

Run:

```bash
python3 - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "scripts"))
import env.tool_runtime.definition
import env.tool_runtime.context
import env.tool_runtime.results
import env.tool_runtime.registry
print("ok")
PY
```

Expected: `ok`.

## Task 3: Migrate Generic Host Callers To `env.tool_runtime`

**Files:**

- Modify: `scripts/runtime_kernel/dispatcher.py`
- Modify: `scripts/runtime_kernel/client.py`
- Modify: `scripts/runtime_kernel/coordinator.py`
- Modify: `scripts/turn_runtime.py`
- Modify: `scripts/env/client.py`

- [ ] **Step 1: Update broker dispatcher**

Replace `from env.tools.router import dispatch_env_tool_request` with:

```python
from env.tool_runtime.registry import dispatch_env_tool_request
```

Replace `from env.tools import responses as tool_responses` with:

```python
from env.tool_runtime import results as tool_results
```

Keep the broker method name `env.tool` unchanged. Preserve the clean-runtime dispatcher behavior:

- `_runtime_server_env()` still exports `BUDDYSWITCH_STATE_ROOT`;
- `runtime_files.refresh_runtime_roots_from_env()` still runs after environment updates and after
  restoration;
- `ping` and `status` still include `runtime_workspace_root`, `runtime_state_root`, and
  `env_store_root`.

- [ ] **Step 2: Update runtime catalog callers**

Replace imports of `env.tools.catalog` with:

```python
from env.tool_runtime import registry as tool_registry
```

Use `tool_registry.env_tools_description()`, `tool_registry.operation_semantics()`, and
`tool_registry.compact_tool_affordances()`.

For retry and coordination policy, replace old `get_action_spec(...).get("mutates")` lookups with:

```python
tool_registry.action_mutates(tool.strip(), action) == "none"
```

Do not keep a `get_action_spec` compatibility helper just to preserve the old contract shape.

- [ ] **Step 3: Replace CLI registration**

Rewrite `scripts/env/client.py` to build subcommands from `tool_registry`:

```text
python3 scripts/env/client.py <tool> <action> --payload '<json-object>'
```

Rules:

- if `--payload` is omitted, send `{}`;
- reject payload strings that are not JSON objects;
- reject file-path payload shortcuts;
- normalize dash action names to underscore action ids;
- print the broker response as JSON;
- return exit code 0 only when `payload["ok"] is True`.

- [ ] **Step 4: Run focused caller import checks**

Run:

```bash
python3 -m pytest \
  tests/test_runtime_broker.py \
  tests/test_turn_runtime.py \
  tests/test_env_client_payload_cli.py \
  tests/test_clean_runtime_environment.py \
  -q
```

Expected at this checkpoint: failures may remain until tools are migrated, but imports must no
longer fail because of missing `env.tools.router` or `env.tools.catalog`, and clean-runtime status
fields/root refresh behavior must remain intact.

## Task 4: Migrate `message` And `task` First

**Files:**

- Create: `scripts/env/tools/message/tool.py`
- Create: `scripts/env/tools/message/_impl.py`
- Create: `scripts/env/tools/task/tool.py`
- Create: `scripts/env/tools/task/_impl.py`
- Delete after tests import the new path: current `message/contract.py`, `message/semantics.py`,
  `message/handlers.py`, `message/cli.py`, `message/service.py`, `task/contract.py`,
  `task/semantics.py`, `task/handlers.py`, `task/cli.py`, `task/service.py`

- [ ] **Step 1: Define `message` protocol**

Move `message.send` and `message.list` metadata into `DEFINITION`. Input properties must be:

```text
send: to_buddy, content, reply_to
list: buddy
```

- [ ] **Step 2: Define `task` protocol**

Move `task` metadata into `DEFINITION`. Input properties must be:

```text
create: task_id, title, summary, status, track_id
list: status, track_id, limit
get: task_id
update: task_id, title, summary, status, track_id
archive: task_id
```

- [ ] **Step 3: Port implementation to `_impl.py`**

Keep local payload validation and response wording. Replace repo/domain writes with:

```text
context.objects.send_message(to_buddy, content, reply_to)
context.objects.list_messages(buddy)
context.objects.create_task(task_id, title, summary, status, track_id)
context.objects.list_tasks()
context.objects.get_task(task_id)
context.objects.update_task(task_id, title, summary, status, track_id)
context.objects.archive_task(task_id)
```

- [ ] **Step 4: Verify focused tools**

Run:

```bash
python3 -m pytest tests/test_message_env_tool.py tests/test_task_env_tool.py tests/test_black_box_tool_runtime.py -q
```

Expected: message/task behavior passes; black-box tests still fail for unmigrated tools and old
shared env.tools runtime files.

## Task 5: Migrate Object And Collaboration Tools

**Files:**

- Create: `scripts/env/tools/comment/tool.py`
- Create: `scripts/env/tools/comment/_impl.py`
- Create: `scripts/env/tools/track/tool.py`
- Create: `scripts/env/tools/track/_impl.py`
- Create: `scripts/env/tools/artifact/tool.py`
- Create: `scripts/env/tools/artifact/_impl.py`
- Create: `scripts/env/tools/context/tool.py`
- Create: `scripts/env/tools/context/_impl.py`
- Delete old public files for these four tools after their new behavior tests pass.

- [ ] **Step 1: Migrate `comment`**

Input properties:

```text
add: target_type, target_id, content, reply_to, artifact_revision_id, anchor, mentions
list: target_type, target_id, status
```

Use `context.objects.add_comment(target_type, target_id, content, reply_to,
artifact_revision_id, anchor, mentions)` and `context.objects.list_comments(target_type,
target_id, status)`.

- [ ] **Step 2: Migrate `track`**

Input properties:

```text
create: track_id, title, outcome, appetite, now, state, health
list: state, limit
open: track_id
update_now: track_id, now, state, health
add_material: track_id, artifact_id, label, summary
add_update: track_id, summary, kind, refs
add_proof: track_id, artifact_id, label, summary
archive: track_id
```

Use `context.objects` track methods for every state read/write.

- [ ] **Step 3: Migrate `artifact`**

Input properties:

```text
get: artifact_id
create_revision: artifact_id, title, summary, template, body, source_refs, read_claim, track_id, publish_as, label
update_metadata: artifact_id, title, summary, template, body, source_refs, read_claim
```

Use `context.objects.get_artifact(artifact_id)`,
`context.objects.create_artifact_revision(artifact_id, title, summary, template, body, source_refs,
read_claim, track_id, publish_as, label)`, and
`context.objects.update_artifact_metadata(artifact_id, title, summary, template, body, source_refs,
read_claim)`.

- [ ] **Step 4: Migrate `context`**

Input properties:

```text
get: track_id, task_id, limit
summarize: track_id, task_id, limit
list_sources: none
```

Use `context.catalog`, `context.objects.runtime_sources()`, and read-only `context.objects` methods.
The migrated context implementation must preserve the clean-runtime contract: host-facing source
descriptions point to env tool routes such as `track.open`, `task.get/list`, `artifact.get`,
`message.list`, `comment.list`, and `buddybox.read/list/write/delete` by `logical_name`; they must
not instruct the host to read or edit `buddyswitch/objects/**` or
`buddyswitch/local/buddybox/**`.

- [ ] **Step 5: Verify object and collaboration tools**

Run:

```bash
python3 -m pytest \
  tests/test_comment_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_env_tool_response_contract.py \
  -q
```

Expected: migrated behavior passes through `env.tool_runtime.registry`.

## Task 6: Migrate Buddybox, Evidence, And Search

**Files:**

- Create: `scripts/env/tools/buddybox/tool.py`
- Create: `scripts/env/tools/buddybox/_impl.py`
- Create: `scripts/env/tools/evidence/tool.py`
- Create: `scripts/env/tools/evidence/_impl.py`
- Create: `scripts/env/tools/search/tool.py`
- Create: `scripts/env/tools/search/_impl.py`
- Delete old public files for these three tools after their new behavior tests pass.

- [ ] **Step 1: Migrate `buddybox`**

Input properties:

```text
desc: none
list: logical_name, recursive, limit
read: logical_name, encoding
write: logical_name, content, content_base64, content_type
delete: logical_name
```

Use `context.buddybox`. The implementation must keep buddybox storage state-root-backed through the
host capability and expose only logical names to tool callers. Do not pass workspace paths, state
paths, or active buddybox filesystem roots into `scripts/env/tools/buddybox/_impl.py`.

- [ ] **Step 2: Migrate `evidence`**

Input properties:

```text
issue_browser: target_type, target_id, mode
approve_downgrade: target_type, target_id, reason
```

Use `context.browser.issue_evidence_token(target_type, target_id, mode)` and
`context.browser.approve_downgrade(target_type, target_id, reason)`.

- [ ] **Step 3: Migrate `search`**

Input properties:

```text
status: none
request: query, backend, engine
open_browser: query, engine
```

Use `context.browser.status()`, `context.browser.request(query, backend, engine)`, and
`context.browser.open_browser(query, engine)`.

- [ ] **Step 4: Verify capability tools**

Run:

```bash
python3 -m pytest \
  tests/test_buddybox_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_search_env_tool.py \
  tests/test_clean_runtime_environment.py \
  tests/test_runless_runtime_contract.py \
  -q
```

Expected: buddybox, evidence, and search behavior pass through `ToolContext`.

## Task 7: Delete Old Runtime Surfaces

**Files:**

- Delete all files listed in the "Delete in the final state" section.
- Modify tests and docs that import or describe old modules as current architecture.

- [ ] **Step 1: Remove old shared env.tools runtime modules**

Delete:

```text
scripts/env/tools/catalog.py
scripts/env/tools/cli_helpers.py
scripts/env/tools/discovery.py
scripts/env/tools/dispatch.py
scripts/env/tools/model.py
scripts/env/tools/responses.py
scripts/env/tools/router.py
```

- [ ] **Step 2: Remove old per-tool public modules**

For every shipped tool, delete:

```text
contract.py
semantics.py
handlers.py
cli.py
service.py
```

- [ ] **Step 3: Update imports in tests and runtime code**

Replace old imports with:

```python
from env.tool_runtime import registry as tool_registry
from env.tool_runtime.registry import dispatch_env_tool_request
from env.tool_runtime import results as tool_results
```

- [ ] **Step 4: Scan for active runtime residue**

Run:

```bash
rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests README.md docs/memo/buddyswitch-parallel-modular-architecture.md -S
```

Expected: active code and active architecture docs do not describe old files as current runtime.
Historical implementation specs and memos may mention old files as source context or deletion
targets, but they must not be imported as active runtime guidance.

## Task 8: Update Runtime Discovery, Skills, And Docs

**Files:**

- Modify: `README.md`
- Modify: `docs/memo/buddyswitch-parallel-modular-architecture.md`
- Modify: `tests/test_runtime_skills.py`
- Modify: `tests/test_repo_consistency.py`

- [ ] **Step 1: Update current architecture docs**

Current architecture text must name:

```text
scripts/env/tool_runtime/definition.py
scripts/env/tool_runtime/context.py
scripts/env/tool_runtime/results.py
scripts/env/tool_runtime/registry.py
scripts/env/tools/<tool>/tool.py
scripts/env/tools/<tool>/_impl.py
```

Do not describe old per-tool files as current runtime sources.

- [ ] **Step 2: Update skill boundary tests**

Shared tool skills must continue to point users to:

```text
context.get.tool_catalog
context.get.operation_semantics
context.summarize.tool_affordances
python3 scripts/turn_runtime.py status
python3 scripts/env/client.py <tool> <action> --payload '<json-object>'
```

They must not mention private `_impl.py` files.

- [ ] **Step 3: Verify docs and skills**

Run:

```bash
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Expected: pass.

## Task 9: Run Full Focused Verification

**Files:** no planned file edits in this task.

- [ ] **Step 1: Run architecture and contract suites**

```bash
python3 -m pytest \
  tests/test_black_box_tool_runtime.py \
  tests/test_env_tool_package_independence.py \
  tests/test_env_tool_payload_contract.py \
  tests/test_env_tool_response_contract.py \
  tests/test_env_client_payload_cli.py \
  tests/test_env_tool_router.py \
  -q
```

Expected: pass.

- [ ] **Step 2: Run shipped tool behavior suites**

```bash
python3 -m pytest \
  tests/test_task_env_tool.py \
  tests/test_track_env_tool.py \
  tests/test_artifact_env_tool.py \
  tests/test_buddybox_env_tool.py \
  tests/test_context_binding_env_tool.py \
  tests/test_evidence_env_tool.py \
  tests/test_message_env_tool.py \
  tests/test_comment_env_tool.py \
  tests/test_search_env_tool.py \
  -q
```

Expected: pass.

- [ ] **Step 3: Run runtime integration and guidance suites**

```bash
python3 -m pytest \
  tests/test_runtime_broker.py \
  tests/test_turn_runtime.py \
  tests/test_runless_runtime_contract.py \
  tests/test_clean_runtime_environment.py \
  tests/test_buddy_env_sandbox.py \
  tests/test_env_layer_boundaries.py \
  tests/test_env_layer_end_to_end.py \
  tests/test_runtime_skills.py \
  tests/test_repo_consistency.py \
  -q
```

Expected: pass.

- [ ] **Step 4: Run hygiene checks**

```bash
git diff --check
rg -n 'env\.tools\.(catalog|cli_helpers|discovery|dispatch|model|responses|router)|TOOL_SPEC|ACTION_SEMANTICS|HANDLER_SPECS|scripts/env/tools/.*/(contract|semantics|handlers|cli|service)\.py' \
  scripts tests README.md docs/memo/buddyswitch-parallel-modular-architecture.md -S
```

Expected:

- `git diff --check` passes;
- no active code imports old runtime modules;
- active architecture docs do not describe old runtime modules as current architecture;
- historical specs and memos may retain old module names only as source context or deletion targets.

## Completion Checklist

- [ ] `env.tool_runtime` is the only host-owned env.tool runtime package.
- [ ] Each shipped tool has exactly one public `tool.py`.
- [ ] Catalog/protocol loading imports no private implementation modules.
- [ ] Selected invocation imports only selected private implementation code.
- [ ] Tool packages import only the runtime SDK and local private files.
- [ ] Tool packages mutate state only through `ToolContext`.
- [ ] Tool packages never derive runtime object or buddybox storage paths from the host-visible
      workspace.
- [ ] Clean runtime environment tests still prove state-root-backed objects/buddybox and searchable
      host-visible workspaces.
- [ ] Generic CLI builds envelopes from registry definitions.
- [ ] `context.get`, `context.summarize`, and `turn_runtime.py status` project the same registry.
- [ ] Old shared env.tools runtime modules are deleted.
- [ ] Old per-tool public modules are deleted.
- [ ] No compatibility aliases, fallback registry, or old/new dual path remains.
- [ ] Focused architecture, behavior, integration, skill, and consistency tests pass.
