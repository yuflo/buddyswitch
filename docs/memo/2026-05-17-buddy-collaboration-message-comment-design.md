# Buddy Collaboration Tooling: Message & Comment Design Memo

Date: 2026-05-17
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: design convergence memo only. Do not treat this document as implementation. Refined after
user approval to optimize the design; implementation still requires code changes and verification.

## Background

BuddySwitch currently provides strong individual buddy capabilities (PM/Design/Dev/Market/Test each
with clear scope, skills, permissions) and a solid object model (Track → Task → Artifact). However,
the collaboration layer between buddies is absent: buddies write to their own tasks and artifacts in
parallel, but have no mechanism to communicate, discuss, or coordinate with each other.

The original exploration surveyed a broad collaboration capability landscape (signals, comments,
whiteboards, handoffs, reviews, task dependencies, iterations, knowledge base, retrospectives,
metrics). After convergence with the user, the scope narrowed to two atomic tools: `message` and
`comment`.

## Architecture Constraint: Tool Layer is Atomic, SKILL Layer Composes

BuddySwitch enforces a strict layering:

```
SKILL Layer (上层，编排原子工具形成工作流)
  └─ write-prd, shape-prototype, implement-task...
  └─ message-tool, comment-tool  ← shared skills (tool usage manuals)

Tool Layer (原子层，不耦合任何 SKILL)
  └─ task.*, track.*, artifact.*, buddybox.*, context.*, evidence.*, search.*
  └─ message.*, comment.*  ← new
```

KEY RULE: Tool layer describes atomic capability semantics. It explains what an action reads,
writes, validates, returns, and what its authority boundary is. It must not encode business
processes, workflow steps, or "after X do Y" guidance. Business workflows live in skills.

KEY RULE: Each new tool follows the exact same registration pattern as existing tools: contracts.py
(registry) → semantics.py (descriptions) → dispatch.py (routing) → services/*.py (implementation).

## Converged Scope

Only two new tools are in scope for this design pass:

### 1. `message` — Pure IM Channel

Buddy-to-buddy messaging. No association with track, task, or artifact. Flat and minimal.

**Actions:**

| Action | Semantics |
|--------|-----------|
| `message.send` | Send a message to a target buddy |
| `message.list` | List messages in current buddy's inbox |

**message.send payload:**
```json
{
  "to_buddy": "dev",
  "content": "<text>",
  "reply_to": "<message_id>"   // optional, for threading
}
```

`to_buddy` must be a declared buddy id and must not equal the active buddy in this pass.

**message.list payload:**
```json
{
  "buddy": "design"    // optional, filter by sender
}
```

**Message object shape:**
```json
{
  "id": "msg-<uuid>",
  "from_buddy": "design",
  "to_buddy": "dev",
  "content": "<text>",
  "reply_to": null,
  "created_at": "<iso-timestamp>"
}
```

**Permissions:**

| Action | Permission | Boundary |
|--------|-----------|----------|
| `send` | `message.send` | any buddy can send |
| `list` | `message.list` | only returns messages where to_buddy matches active buddy |

**Storage:** `buddyswitch/objects/messages/<message-id>.json`

`message.list` returns only messages where `to_buddy` equals the active buddy. It is a pull-only
inbox read, not a read-receipt system. There is no message status in this pass because no action
exists to mutate read state.

### 2. `comment` — Cross-Object Comments

Comments attached to track and artifact objects. Task commenting is excluded for now.

**Actions:**

| Action | Semantics |
|--------|-----------|
| `comment.add` | Add a comment to a target track or artifact |
| `comment.list` | List all comments on a target track or artifact |

**comment.add payload:**
```json
{
  "target_type": "artifact",
  "target_id": "<artifact-id>",
  "content": "<text>",
  "reply_to": "<comment-id>"   // optional, for threading
}
```

`target_type` ∈ `{"track", "artifact"}`

**comment.list payload:**
```json
{
  "target_type": "artifact",
  "target_id": "<artifact-id>"
}
```

**Comment object shape:**
```json
{
  "id": "comment-<uuid>",
  "target_type": "artifact",
  "target_id": "<artifact-id>",
  "author_buddy": "design",
  "content": "<text>",
  "reply_to": null,
  "created_at": "<iso-timestamp>"
}
```

**Permissions:**

| Action | Permission | Boundary |
|--------|-----------|----------|
| `add` | `comment.add` | buddy must have read permission on target object |
| `list` | `comment.list` | buddy must have read permission on target object |

**Storage:** `buddyswitch/objects/comments/<comment-id>.json`

Read-boundary detail:

- `target_type="track"` reuses the same readable-track boundary as `track.get`: the track must
  exist and must not be archived.
- `target_type="artifact"` reuses `artifact_visibility.artifact_read_decision()`: owners can read
  their artifacts, and foreign artifacts are readable only through the active non-archived track
  collaboration relation and current-artifact rule.
- Rejections must preserve the underlying permission boundary (`track.lifecycle_status`,
  `artifact.currentness`, `artifact.track_relation`, etc.) so comment tools do not become a second,
  inconsistent authorization surface.

### Target Object Interface Support

Track and artifact objects must expose a `comment_ids` field so the comment tool can attach and
retrieve comments:

**Track object** — new field:
```
"comment_ids": ["comment-xxx", "comment-yyy"]
```

**Artifact object** — new field:
```
"comment_ids": ["comment-zzz"]
```

`comment.add` service logic writes the comment object, then appends the comment id to the target
object's `comment_ids` list.

`comment.list` service logic reads the target object's `comment_ids`, then returns all referenced
comment objects.

Existing track/artifact objects that do not yet have `comment_ids` should normalize to
`comment_ids: []` when read through `env_store`; new writes should persist the field.

`reply_to` validation:

- `message.send.reply_to` may reference only a message visible to the active buddy in the same
  sender/recipient pair.
- `comment.add.reply_to` may reference only an existing comment attached to the same target object.

Task objects are NOT modified and do NOT support comments in this pass.

## Full Change Surface

| Layer | File | Change |
|-------|------|--------|
| Tool registry | `scripts/env/tools/contracts.py` | Add `message` and `comment` to `TOOL_REGISTRY` |
| Tool semantics | `scripts/env/tools/semantics.py` | Add capability rows and action rows for message/comment |
| Tool dispatch | `scripts/env/tools/dispatch.py` | Add message/comment to `HANDLERS_BY_TOOL` |
| Tool CLI | `scripts/env/client.py` | Add message/comment subcommands routed through `env.tool` |
| Service | `scripts/env/services/messages.py` | New: `send_message`, `list_messages` |
| Service | `scripts/env/services/comments.py` | New: `add_comment`, `list_comments` |
| Object store | `scripts/env_store.py` | Add message/comment dirs, path helpers, validators, list/get/save helpers; add `comment_ids` to track/artifact validation and creation |
| Object schema | track object shape | Add `comment_ids` field, defaulting missing values to `[]` on read |
| Object schema | artifact object shape | Add `comment_ids` field, defaulting missing values to `[]` on read |
| Projection implementation | `scripts/runtime_store/projections.py` | Add `comment_ids` to track/artifact views |
| Projection contract | `framework/contracts/workspace-projection.json` | Add `comment_ids` to track/artifact view shapes; include message/comment data sources only if exposed in `/api/workspace` |
| Context discovery | `scripts/env/services/context.py` | Include message/comment tool semantics; expose comment ids only through target object views, not task views |
| Manifest validator | `scripts/env_manifest.py` | Add `message` and `comment` as supported permission objects |
| Permissions | `buddyswitch/manifest.toml` | Each buddy: `message.send`, `message.list`, `comment.add`, `comment.list` |
| Shared SKILL | `buddyswitch/skills/shared/message-tool/SKILL.md` | New: how to use message tool |
| Shared SKILL | `buddyswitch/skills/shared/comment-tool/SKILL.md` | New: how to use comment tool |
| Launcher state projection | `tools/launcher/workspace.sh` | Add `buddyswitch/objects/messages` and `buddyswitch/objects/comments` to runtime-managed/projected state paths |
| Cleanup | `scripts/env_cleanup.py` | Include message/comment object dirs in all-data cleanup and skeleton handling where applicable |
| Tests | `tests/test_message_env_tool.py`, `tests/test_comment_env_tool.py` | New focused service/dispatch/permission-boundary tests |
| Tests | existing registry/projection/manifest/runtime tests | Update expected tool sets, projected state dirs, shared skill requirements, and runtime sandbox patches |

## Explicitly Excluded (Non-Goals)

Decisions made during convergence that must NOT creep into this implementation pass:

- **No track association on message** — message is pure buddy-to-buddy IM; `track_id` field rejected
- **No task commenting** — `target_type` only supports `"track"` and `"artifact"`; task support is
  deferred
- **No broadcast / group messaging** — `to_buddy` is a single buddy string; broadcast can be
  composed by a SKILL calling `message.send` multiple times
- **No read receipts / online status** — flat pull model only; `message.list` has no `status`
  filter because no action mutates read state
- **No message editing or deletion** — messages and comments are immutable after creation
- **No comment status / resolution field** — comments have no `status` in this pass; resolution
  workflow is a future concern
- **No rich text or attachments** — `content` is plain text
- **No handoff tool** — handoff design was tabled as "not yet clear"; do not design or implement it
- **No review/approval workflow** — out of scope for this pass
- **No whiteboard** — out of scope for this pass

## Design Principles for This Pass

1. **Atomic tools, not workflows** — `message.send` sends a message, nothing more. It does not
   notify, escalate, or trigger side effects. `comment.add` adds a comment and updates one
   `comment_ids` list, nothing more.
2. **Keep it simple** — two actions per tool. `send`/`list` for message, `add`/`list` for comment.
   Nothing more until proven necessary.
3. **Retrofit minimally** — the only semantic change to existing product objects is adding
   `comment_ids: []` to track and artifact. Supporting validators, projections, launcher state
   paths, cleanup, and tests must change because those are the runtime contract surfaces.
4. **Follow existing patterns** — same registry format, same response envelope, same storage path
   convention, same SKILL.md structure.

## Implementation Order Recommendation

1. Tests first: add focused failing tests for message send/list, comment add/list, reply validation,
   archived-track rejection, artifact read-boundary reuse, registry coverage, manifest permissions,
   projection shape, launcher projected state paths, and cleanup coverage.
2. Object store: add message/comment dirs and helpers; add `comment_ids` normalization/persistence to
   track and artifact.
3. Services: implement `messages.py` and `comments.py`, reusing existing track/artifact read-boundary
   helpers instead of duplicating permission logic.
4. Registry/CLI/semantics: register both tools in `contracts.py`, `semantics.py`, `dispatch.py`, and
   `scripts/env/client.py`.
5. Runtime surfaces: update manifest validator, `manifest.toml`, context discovery, workspace
   projection, launcher state projection, cleanup, and test sandbox patches.
6. Shared SKILLs: write `message-tool/SKILL.md` and `comment-tool/SKILL.md`.
7. Verification: run focused tests first, then relevant registry/manifest/projection/launcher
   contract tests.

## Open Follow-Up

After `message` and `comment` land and prove useful in practice:

- Revisit `handoff` design — whether it is a new tool, an extension of `task`, or a SKILL-level
  composition of `message` + `task.update`
- Consider `comment` support for `task` objects
- Consider comment status and resolution workflow
- Consider `message` broadcast/multi-recipient support
- Whiteboard and other Layer 2-4 collaboration capabilities from the broader exploration
