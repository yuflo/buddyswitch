# Artifact Attachments and Design Handoff Test Plan

## Task Goal

Build a complete, generic artifact improvement that lets any buddy attach, list, and read artifact-owned files while hardening artifact template permissions and updating Design handoff guidance to use those generic capabilities.

This task is not a Design-only tool change. Tool behavior must stay buddy-neutral. Buddy-specific product/design judgment belongs in skills and templates; permissions, visibility, payload validation, and attachment durability belong in runtime tool contracts.

## Key Problems To Prove

1. Artifact template access is currently declared per buddy in `buddyswitch/manifest.toml`, but `artifact.create_revision` and `artifact.update_metadata` only validate against the global template vocabulary.
2. Buddybox files are private and not product-readable. Design screenshots or exports need a clean artifact-owned route to become cross-buddy readable.
3. The attachment capability must not become a generic asset platform, a Design-specific screenshot tool, or a compatibility wrapper.
4. Design skills should describe when and how to use attachments, but runtime tools must enforce template permissions and artifact visibility without relying on skill self-discipline.
5. Attachment blobs must not become shared filesystem paths. Cross-buddy reads must use `artifact_id` plus `attachment_id` through `artifact.get_attachment`, so artifact visibility remains the read boundary.
6. Real screenshot/export files must not require large base64 payloads to pass through the agent context. Local files produced by MCP tools should enter buddybox through one generic `buddybox.import_file` action; `artifact.attach_file` should use one input shape only: promote an active-buddy private `buddybox` `logical_name` into an artifact attachment reference.

## Non-Goals

- Do not add a `capture` env tool. Screenshot capture should use the already configured `chrome-devtools` MCP when needed.
- Do not add `design_source`, `a11y_scan`, `component_inventory`, `ux_signal`, Figma ingestion, or visual regression.
- Do not add a generic `asset` tool or standalone asset registry.
- Do not add Design-specific fields to artifact objects or tool payloads.
- Do not preserve invalid old behavior through aliases, compatibility flags, or transitional dual paths.

## Test Strategy

Tests must be written from behavior requirements, not from implementation shortcuts. The suite should prove:

- Generic tool registration and discovery expose the new actions.
- Artifact write paths enforce active buddy template permissions from manifest.
- Local file ingress into buddybox is generic, private, and does not expose filesystem paths in responses.
- Attachments are artifact-owned subresources, not separate product objects.
- Attachment writes are limited to active-buddy-owned drafts; attachment read/list visibility follows artifact readability after publication.
- Producers import local tool outputs into buddybox, then attach by promoting an active-buddy private buddybox file without exposing a path or moving blob bytes through the model.
- Consumers can discover attachment existence from the normal cross-buddy track/artifact reading path before fetching content.
- Attachment payload validation rejects malformed or unsafe inputs without mutating state.
- Design skill guidance uses generic artifact attachment refs and Chrome DevTools screenshots without embedding tool-only business logic.

## Test Matrix

| Requirement | Test Coverage |
| --- | --- |
| `artifact` supports attachment actions | Registry, semantic contract, black-box runtime package, CLI command generation |
| Template permission follows active buddy manifest row | Create/update positive and negative cases across PM, Design, Dev, Test, Market |
| Local tool-output import avoids base64 relay | `buddybox.import_file` imports one local file into active-buddy private buddybox and returns no source path |
| Attachments are generic | Tests use PM/Dev/Test examples as well as Design; no design-specific payload fields |
| Attach writes are owner draft-scoped | Foreign private draft attach is rejected; published artifact attach is rejected; owner draft attach succeeds |
| Attachment reads follow artifact readability | Owner draft readable; foreign draft denied; published material/proof readable |
| Attachment blobs do not pollute artifact body | `artifact.get` returns attachment summaries only, not blob bytes |
| Attachment paths stay internal | Responses expose `attachment_id` and metadata, not runtime filesystem paths |
| Buddybox promotion is ergonomic | `artifact.attach_file` accepts only `source_buddybox_logical_name` and never accepts inline blob payloads |
| Cross-buddy discovery is obvious | `track.open` material/proof rows expose `attachment_count` and attachment summary ids for readable artifacts |
| List is simple and explicit | `artifact.list_attachments` returns summary rows for one readable artifact |
| Get is exact | `artifact.get_attachment` requires `artifact_id` and `attachment_id` and returns `content_base64` only |
| Bad payloads are safe | Invalid ids, missing buddybox source, inline blob fields, unsafe filenames, empty source files reject with no mutation |
| Skill/runtime boundary stays clean | Design skill references generic actions; artifact tool has no Design-only branches or fields |

## Focused Test Additions

### 1. Tool Catalog And Semantic Contract Tests

Modify:

- `tests/test_env_tool_semantic_contract.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_repo_consistency.py`

Required assertions:

- `_EXPECTED_ACTIONS_BY_TOOL["buddybox"]` includes:
  - `desc`
  - `list`
  - `read`
  - `write`
  - `delete`
  - `import_file`
- `_EXPECTED_ACTIONS_BY_TOOL["artifact"]` includes:
  - `list`
  - `get`
  - `create_revision`
  - `update_metadata`
  - `attach_file`
  - `list_attachments`
  - `get_attachment`
- `SHIPPED_TOOLS["artifact"]` in black-box runtime tests includes the same action set.
- `operation_semantics()` includes:
  - `buddybox.import_file`
  - `artifact.attach_file`
  - `artifact.list_attachments`
  - `artifact.get_attachment`
- Each new action has non-placeholder `use_when`, `do_not_use_when`, `reads`, `writes`, `does_not_write`, `visibility`, `durability`, `success_effect`, and `failure_state_guarantee`.
- `tests/test_repo_consistency.py` no longer expects only the four old artifact actions.

Expected failure before implementation:

```bash
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_repo_consistency.py -q
```

Expected: failures identifying missing artifact actions or stale expected action sets.

### 2. Active Buddy Template Permission Tests

Modify:

- `tests/test_artifact_env_tool.py`
- `tests/test_env_tool_response_contract.py`

Behavior cases:

1. PM can create `brief`, `decision`, and `note`.
2. PM cannot create `design` or `proof`.
3. Design can create `design` and `brief`.
4. Design cannot create `decision`, `note`, or `proof`.
5. Dev can create `brief` and `note`.
6. Test can create `proof` and cannot create `brief`.
7. Market can create `brief` and cannot create `design`.
8. `artifact.update_metadata` rejects changing an owned artifact to a template not declared for the active buddy.
9. Rejection uses a dedicated permission boundary such as `artifact.template_permission`, returns `state_changed=false`, `durability=none`, and includes `correctable_fields=["template"]`.
10. Failed template permission writes do not create or mutate artifact JSON.

Representative tests:

```python
def test_create_revision_rejects_template_not_declared_for_active_buddy(self) -> None:
    instance_json = self._instance_json(instance_id="inst-design-template", buddy="design")
    rejected = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-template",
        buddy="design",
        tool="artifact",
        action="create_revision",
        args={
            "artifact_id": "art-design-proof-denied",
            "title": "Wrong template",
            "summary": "should reject",
            "template": "proof",
            "body": "proof is owned by Test, not Design",
        },
    )
    self.assertFalse(rejected.get("ok"), msg=rejected)
    self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
    self.assertEqual(rejected.get("permission_boundary"), "artifact.template_permission")
    self.assertEqual(rejected.get("correctable_fields"), ["template"])
    self.assertFalse(bool(rejected.get("state_changed")), msg=rejected)
    self.assertFalse(env_store.artifact_file("art-design-proof-denied").exists())
```

```python
def test_update_metadata_rejects_template_not_declared_for_active_buddy_without_mutation(self) -> None:
    instance_json = self._instance_json(instance_id="inst-pm-template-update", buddy="pm")
    created = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-pm-template-update",
        buddy="pm",
        tool="artifact",
        action="create_revision",
        args={
            "artifact_id": "art-pm-template-update",
            "title": "PM note",
            "summary": "seed",
            "template": "note",
            "body": "seed",
        },
    )
    self.assertTrue(created.get("ok"), msg=created)

    rejected = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-pm-template-update",
        buddy="pm",
        tool="artifact",
        action="update_metadata",
        args={"artifact_id": "art-pm-template-update", "template": "design"},
    )
    self.assertFalse(rejected.get("ok"), msg=rejected)
    self.assertEqual((rejected.get("error") or {}).get("code"), "E_ARTIFACT_TEMPLATE_PERMISSION")
    stored = env_store.get_artifact("art-pm-template-update")
    self.assertEqual(stored.get("template"), "note")
```

Expected failure before implementation:

```bash
python3 -m pytest tests/test_artifact_env_tool.py::ArtifactEnvToolTests::test_create_revision_rejects_template_not_declared_for_active_buddy -q
```

Expected: current code accepts globally valid but buddy-disallowed templates.

### 3. Buddybox Import Tests

Modify:

- `tests/test_buddybox_env_tool.py`
- `tests/test_env_tool_semantic_contract.py`
- `tests/test_black_box_tool_runtime.py`
- `tests/test_env_client_payload_cli.py`

Behavior cases:

1. `buddybox.import_file` imports one existing local regular file into the active buddy private buddybox at `logical_name`.
2. The response includes private-file metadata and never includes `source_path`, buddybox filesystem path, or any runtime path.
3. The source file is not mutated or deleted.
4. The imported file can be read through `buddybox.read`.
5. Missing source file, directory source, symlink escape, source under runtime objects, source under runtime local buddybox, invalid logical name, and unsupported extra fields reject without writing a private file.
6. Tool catalog, operation semantics, black-box runtime, and CLI command generation expose `buddybox.import_file` / `buddybox import-file`.

Representative test:

```python
def test_import_file_writes_private_file_without_path_exposure(self) -> None:
    instance_json = self._instance_json(instance_id="inst-import-file", buddy="design")
    source = self._runtime_path("tmp/chrome-devtools/desktop.png")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"\x89PNG\r\n")

    imported = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-import-file",
        buddy="design",
        tool="buddybox",
        action="import_file",
        args={
            "logical_name": "screenshots/desktop.png",
            "source_path": str(source),
            "content_type": "image/png",
        },
    )

    self.assertTrue(imported.get("ok"), msg=imported)
    self.assertEqual(imported.get("logical_name"), "screenshots/desktop.png")
    self.assertEqual(imported.get("content_type"), "image/png")
    self.assertNotIn("source_path", imported)
    self.assertNotIn("path", imported)
    self.assertTrue(source.exists())

    read_back = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-import-file",
        buddy="design",
        tool="buddybox",
        action="read",
        args={"logical_name": "screenshots/desktop.png", "encoding": "base64"},
    )
    self.assertTrue(read_back.get("ok"), msg=read_back)
    self.assertEqual(read_back.get("content_base64"), "iVBORw0K")
```

### 4. Attachment Write Tests

Modify:

- `tests/test_artifact_env_tool.py`

Behavior cases:

1. Owner attaches a file from active-buddy private buddybox using `source_buddybox_logical_name`.
2. Inline `content` and `content_base64` payloads are rejected as unsupported fields.
3. Response includes `attachment_id`, attachment summary, `state_changed=true`, `durability=durable`, `created_ids` or `updated_ids`, and no blob content.
4. The artifact metadata returned by `artifact.get` includes attachment summary rows.
5. Attachment rows include:
   - `attachment_id`
   - `filename`
   - `content_type`
   - `size_bytes`
   - `sha256`
   - `created_by`
   - `created_at`
6. `track.open` shows `attachment_count` and attachment ids on readable material/proof rows so another buddy can discover attachments without guessing.
7. Attachment IDs are unique for repeated attaches to the same artifact.
8. Owner can attach to an owned current draft.
9. Owner cannot attach to an already published artifact; create a new revision, attach there, then publish.
10. Foreign buddy cannot attach to another buddy's private draft.

Representative test:

```python
def test_attach_file_creates_artifact_owned_attachment_summary_without_body_blob(self) -> None:
    instance_json = self._instance_json(instance_id="inst-design-attach", buddy="design")
    source = self._runtime_path("tmp/chrome-devtools/desktop.png")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"\x89PNG\r\n\x1a\n")

    buddybox = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-attach",
        buddy="design",
        tool="buddybox",
        action="import_file",
        args={
            "logical_name": "screenshots/desktop.png",
            "source_path": str(source),
            "content_type": "image/png",
        },
    )
    self.assertTrue(buddybox.get("ok"), msg=buddybox)

    created = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-attach",
        buddy="design",
        tool="artifact",
        action="create_revision",
        args={
            "artifact_id": "art-design-attach-r1",
            "title": "Design handoff",
            "summary": "handoff",
            "template": "design",
            "body": "# Handoff",
        },
    )
    self.assertTrue(created.get("ok"), msg=created)

    attached = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-attach",
        buddy="design",
        tool="artifact",
        action="attach_file",
        args={
            "artifact_id": "art-design-attach-r1",
            "filename": "desktop.png",
            "content_type": "image/png",
            "source_buddybox_logical_name": "screenshots/desktop.png",
        },
    )
    self.assertTrue(attached.get("ok"), msg=attached)
    self.assertTrue(attached.get("state_changed"), msg=attached)
    attachment = attached.get("attachment")
    self.assertIsInstance(attachment, dict, msg=attached)
    self.assertEqual(attachment.get("filename"), "desktop.png")
    self.assertEqual(attachment.get("content_type"), "image/png")
    self.assertIn("sha256", attachment)
    self.assertNotIn("content", attachment)
    self.assertNotIn("content_base64", attachment)
    self.assertNotIn("source_buddybox_logical_name", attachment)
    self.assertNotIn("path", attachment)

    read = self._dispatch(
        instance_json=instance_json,
        instance_id="inst-design-attach",
        buddy="design",
        tool="artifact",
        action="get",
        args={"artifact_id": "art-design-attach-r1"},
    )
    self.assertTrue(read.get("ok"), msg=read)
    artifact = read.get("artifact")
    self.assertIsInstance(artifact, dict, msg=read)
    attachments = artifact.get("attachments")
    self.assertIsInstance(attachments, list, msg=artifact)
    self.assertEqual(len(attachments), 1)
    self.assertNotIn("content_base64", attachments[0])
    self.assertNotIn("source_buddybox_logical_name", attachments[0])
    self.assertNotIn("path", attachments[0])
```

### 5. Attachment List And Get Tests

Modify:

- `tests/test_artifact_env_tool.py`

Behavior cases:

1. `artifact.list_attachments` returns summary rows for one readable artifact.
2. `artifact.list_attachments` returns an empty list for a readable artifact with no attachments.
3. `artifact.get_attachment` returns exact blob content as `content_base64`.
4. `artifact.get_attachment` has one output shape for text and binary files.
5. `artifact.get_attachment` rejects unknown `attachment_id` without mutating state.
6. Attachment reads on foreign private drafts are denied.
7. Attachment reads on published track material are allowed for another buddy.

Representative published-read test:

```python
def test_published_attachment_is_readable_by_other_buddy_through_artifact_visibility(self) -> None:
    instance_pm = self._instance_json(instance_id="inst-attach-published", buddy="pm")
    created_track = self._create_track(
        instance_json=instance_pm,
        instance_id="inst-attach-published",
        track_id="track-attach-published",
    )
    self.assertTrue(created_track.get("ok"), msg=created_track)
    created = self._dispatch(
        instance_json=instance_pm,
        instance_id="inst-attach-published",
        buddy="pm",
        tool="artifact",
        action="create_revision",
        args={
            "artifact_id": "art-pm-attach-published",
            "title": "PM brief with attachment",
            "summary": "brief",
            "template": "brief",
            "body": "# Brief",
        },
    )
    self.assertTrue(created.get("ok"), msg=created)
    source = self._runtime_path("tmp/pm/evidence.txt")
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_text("hello from PM", encoding="utf-8")
    imported = self._dispatch(
        instance_json=instance_pm,
        instance_id="inst-attach-published",
        buddy="pm",
        tool="buddybox",
        action="import_file",
        args={
            "logical_name": "evidence/evidence.txt",
            "source_path": str(source),
            "content_type": "text/plain",
        },
    )
    self.assertTrue(imported.get("ok"), msg=imported)
    attached = self._dispatch(
        instance_json=instance_pm,
        instance_id="inst-attach-published",
        buddy="pm",
        tool="artifact",
        action="attach_file",
        args={
            "artifact_id": "art-pm-attach-published",
            "filename": "evidence.txt",
            "source_buddybox_logical_name": "evidence/evidence.txt",
            "content_type": "text/plain",
        },
    )
    self.assertTrue(attached.get("ok"), msg=attached)
    attachment_id = attached["attachment"]["attachment_id"]
    published = self._dispatch(
        instance_json=instance_pm,
        instance_id="inst-attach-published",
        buddy="pm",
        tool="track",
        action="add_material",
        args={
            "track_id": "track-attach-published",
            "artifact_id": "art-pm-attach-published",
            "label": "Brief",
            "summary": "publish",
        },
    )
    self.assertTrue(published.get("ok"), msg=published)

    instance_dev = self._instance_json(instance_id="inst-attach-published", buddy="dev")
    listed = self._dispatch(
        instance_json=instance_dev,
        instance_id="inst-attach-published",
        buddy="dev",
        tool="artifact",
        action="list_attachments",
        args={"artifact_id": "art-pm-attach-published"},
    )
    self.assertTrue(listed.get("ok"), msg=listed)
    self.assertEqual([row["attachment_id"] for row in listed["attachments"]], [attachment_id])

    fetched = self._dispatch(
        instance_json=instance_dev,
        instance_id="inst-attach-published",
        buddy="dev",
        tool="artifact",
        action="get_attachment",
        args={
            "artifact_id": "art-pm-attach-published",
            "attachment_id": attachment_id,
        },
    )
    self.assertTrue(fetched.get("ok"), msg=fetched)
    self.assertEqual(fetched.get("content_base64"), "aGVsbG8gZnJvbSBQTQ==")
```

### 6. Attachment Payload Safety Tests

Modify:

- `tests/test_artifact_env_tool.py`
- `tests/test_env_tool_response_contract.py`

Reject cases:

- Missing `artifact_id`.
- Missing `filename`.
- Filename includes `/`, `\`, leading dot-only name, or path traversal.
- Missing `source_buddybox_logical_name`.
- Providing inline `content` or `content_base64`.
- Buddybox file is empty.
- Invalid or missing buddybox logical name.
- Buddybox logical name outside the active buddy private boundary.
- Unknown artifact.
- Foreign private draft.
- Already published artifact.
- Unknown attachment id.

Every rejection must assert:

- `ok=false`
- `state_changed=false`
- `durability=none`
- no artifact attachment metadata added
- no attachment metadata added and no pinned attachment file created
- structured `permission_boundary`, `why_blocked`, `retry_guidance`, and `correctable_fields` where applicable

### 7. Repository Validation Tests

Modify:

- `tests/test_artifact_env_tool.py`
- `tests/test_env_tool_package_independence.py`
- `tests/test_black_box_tool_runtime.py`

Required coverage:

- Existing artifacts without `attachments` still validate and normalize to `attachments=[]`.
- Artifacts with attachment metadata validate only if each row has required fields.
- Artifact repo rejects attachment metadata with unknown buddy ids, missing hash, bad size, or unsafe filename.
- Artifact tool package still imports only runtime SDK and local modules.
- Artifact tool still mutates runtime state only through `ToolContext` / repo helpers.
- Attachment adoption/pinning is done through repo/runtime helpers, not raw direct state path strings inside tool implementation.

### 8. CLI Contract Tests

Modify:

- `tests/test_env_client_payload_cli.py`
- `tests/test_env_tool_semantic_contract.py`

Required coverage:

- CLI exposes:
  - `python3 scripts/env/client.py buddybox import-file --payload '<json-object>'`
  - `python3 scripts/env/client.py artifact attach-file --payload '<json-object>'`
  - `python3 scripts/env/client.py artifact list-attachments --payload '<json-object>'`
  - `python3 scripts/env/client.py artifact get-attachment --payload '<json-object>'`
- Broker payload action ids remain canonical underscores:
  - `import_file`
  - `attach_file`
  - `list_attachments`
  - `get_attachment`
- Direct env.tool dispatch rejects hyphenated action ids.
- CLI generated hyphen commands are only CLI spelling and dispatch underscore action ids.

### 9. Skill And Guidance Boundary Tests

Modify:

- `tests/test_runtime_skills.py`
- `tests/test_repo_consistency.py`

Required coverage:

- Design skill guidance references `artifact.attach_file`, `artifact.list_attachments`, and `artifact.get_attachment` only as generic artifact actions.
- Design guidance may mention `chrome-devtools-cockpit` screenshot capture, but must not mention a new `capture` env tool.
- Artifact skill/shared tool guidance must not contain Design-specific payload fields or business workflow.
- No active guidance says attachments are Design-only.
- No active code or tests introduce `asset` as a runtime env tool.

### 10. Design Handoff Template Tests

Modify:

- `tests/test_runtime_skills.py`
- Design skill package tests created during the Design skill refactor, if that refactor lands first.

Required coverage:

- The Design handoff body template contains a stable `Assets and Attachments` or equivalent section that records artifact attachment ids and screenshot refs.
- The Design handoff body template does not require attachment content inline.
- The template describes screenshot provenance as Chrome DevTools MCP output attached through artifact, not as a Design-specific env tool.

## Full Verification Commands

Run focused tests during implementation:

```bash
python3 -m pytest tests/test_artifact_env_tool.py -q
python3 -m pytest tests/test_buddybox_env_tool.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py -q
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

Run broader relevant verification before completion:

```bash
python3 -m pytest tests/test_artifact_env_tool.py tests/test_buddybox_env_tool.py tests/test_track_env_tool.py tests/test_env_layer_end_to_end.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py tests/test_black_box_tool_runtime.py tests/test_env_tool_schema_contract.py tests/test_env_tool_package_independence.py -q
python3 -m pytest tests/test_env_client_payload_cli.py tests/test_env_tool_response_contract.py tests/test_runtime_skills.py tests/test_repo_consistency.py -q
```

## Acceptance Checklist

- [x] No `capture` env tool is added.
- [x] No `asset` env tool is added.
- [x] No `design_source`, `a11y_scan`, `component_inventory`, or `ux_signal` tool is added.
- [x] Artifact tool has exactly the generic new attachment actions.
- [x] Attachment actions are discoverable through `context.get.tool_catalog`.
- [x] `buddybox.import_file` imports local tool-output files into active-buddy private buddybox without returning filesystem paths.
- [x] Attachment actions expose stable `attachment_id` references, not readable runtime filesystem paths.
- [x] `artifact.attach_file` promotes active-buddy private buddybox logical names and rejects inline blob payloads.
- [x] Template permission is enforced from active buddy manifest rows.
- [x] Template permission rejections are structured and non-mutating.
- [x] Attach/list/get attachment behavior works for at least two non-Design buddies in tests.
- [x] Foreign private draft attachment read/write is denied.
- [x] Attach writes to already published artifacts are denied; published updates require a new artifact revision.
- [x] Published artifact attachment read follows existing artifact visibility.
- [x] `track.open` exposes enough attachment summary metadata for cross-buddy discovery.
- [x] `artifact.get` returns attachment summaries, not blob bytes.
- [x] `artifact.get_attachment` returns `content_base64` only for exact readable artifact and attachment ids.
- [x] No cross-buddy workflow depends on a returned attachment file path.
- [x] Design skill guidance uses generic artifact attachment actions and Chrome DevTools MCP screenshots.
- [x] No tool implementation contains Design-specific branching or Design-specific schema.
- [x] Full verification commands pass.
