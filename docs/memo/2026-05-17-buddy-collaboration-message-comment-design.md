# Buddy Collaboration Tooling: Message & Comment Design Memo

Date: 2026-05-17
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/dev_buddy_mem`
Branch: `dev_buddy_mem`

Status: design convergence memo only. Do not treat this document as implementation. Awaiting user
approval before any code changes.

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

**message.list payload:**
```json
{
  "buddy": "design",    // optional, filter by sender
  "status": "unread"    // optional, filter by status
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
  "status": "unread",
  "created_at": "<iso-timestamp>"
}
```

**Permissions:**

| Action | Permission | Boundary |
|--------|-----------|----------|
| `send` | `message.send` | any buddy can send |
| `list` | `message.list` | only returns messages where to_buddy matches active buddy |

**Storage:** `buddyswitch/objects/messages/<message-id>.json`

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
  "status": "open",
  "created_at": "<iso-timestamp>"
}
```

**Permissions:**

| Action | Permission | Boundary |
|--------|-----------|----------|
| `add` | `comment.add` | buddy must have read permission on target object |
| `list` | `comment.list` | buddy must have read permission on target object |

**Storage:** `buddyswitch/objects/comments/<comment-id>.json`

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

Task objects are NOT modified and do NOT support comments in this pass.

## Full Change Surface

| Layer | File | Change |
|-------|------|--------|
| Tool registry | `scripts/env/tools/contracts.py` | Add `message` and `comment` to `TOOL_REGISTRY` |
| Tool semantics | `scripts/env/tools/semantics.py` | Add capability rows and action rows for message/comment |
| Tool dispatch | `scripts/env/tools/dispatch.py` | Add message/comment to `HANDLERS_BY_TOOL` |
| Service | `scripts/env/services/messages.py` | New: `send_message`, `list_messages` |
| Service | `scripts/env/services/comments.py` | New: `add_comment`, `list_comments` |
| Object schema | track object shape | Add `comment_ids` field |
| Object schema | artifact object shape | Add `comment_ids` field |
| Projection | `framework/contracts/workspace-projection.json` | Add `comment_ids` to track/artifact view shapes |
| Permissions | `buddyswitch/manifest.toml` | Each buddy: `message.send`, `message.list`, `comment.add`, `comment.list` |
| Shared SKILL | `buddyswitch/skills/shared/message-tool/SKILL.md` | New: how to use message tool |
| Shared SKILL | `buddyswitch/skills/shared/comment-tool/SKILL.md` | New: how to use comment tool |

## Explicitly Excluded (Non-Goals)

Decisions made during convergence that must NOT creep into this implementation pass:

- **No track association on message** — message is pure buddy-to-buddy IM; `track_id` field rejected
- **No task commenting** — `target_type` only supports `"track"` and `"artifact"`; task support is
  deferred
- **No broadcast / group messaging** — `to_buddy` is a single buddy string; broadcast can be
  composed by a SKILL calling `message.send` multiple times
- **No read receipts / online status** — flat pull model only; `message.list` with `status` filter
  is sufficient
- **No message editing or deletion** — messages and comments are immutable after creation
- **No `resolved` status for comments** — comments have `status: "open"` only; resolution workflow
  is a future concern
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
3. **Retrofit minimally** — the only change to existing objects is adding `comment_ids: []` to track
   and artifact. No other existing field, permission, or service logic is modified.
4. **Follow existing patterns** — same registry format, same response envelope, same storage path
   convention, same SKILL.md structure.

## Implementation Order Recommendation

1. Object schema: add `comment_ids` to track and artifact shapes (including projection contract)
2. Services: implement `messages.py` and `comments.py`
3. Registry: register both tools in `contracts.py`, `semantics.py`, `dispatch.py`
4. Permissions: add new permissions to `manifest.toml` for all buddies
5. Shared SKILLs: write `message-tool/SKILL.md` and `comment-tool/SKILL.md`
6. Tests: verify tool registration, action dispatch, permission boundaries, object coupling

## Open Follow-Up

After `message` and `comment` land and prove useful in practice:

- Revisit `handoff` design — whether it is a new tool, an extension of `task`, or a SKILL-level
  composition of `message` + `task.update`
- Consider `comment` support for `task` objects
- Consider `resolved` status and resolution workflow for comments
- Consider `message` broadcast/multi-recipient support
- Whiteboard and other Layer 2-4 collaboration capabilities from the broader exploration
