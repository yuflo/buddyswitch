# Web Open TUI / Independent Copy Command Forward Rebuild Design

**Date:** 2026-07-14

**Status:** Approved design; implementation plan and code changes pending

## 1. Target Outcome

Restore `Copy command` as an independent, minimal manual entry for the selected actor.

The two Tools actions have separate product contracts:

- `Open TUI` asks BuddySwitch to open Terminal.app and attach automatically.
- `Copy command` copies one short, actor-specific public CLI command for the user to paste into Terminal manually.

Neither action observes, triggers, consumes, or reports the other action's state.

## 2. Current Bottleneck

The current implementation serializes the full internal `AttachDescriptor` into one shell command, uses it to open Terminal.app, returns it in `/open-tui` success and error payloads, and renders it as `Copy command` content.

This conflates two different representations:

- an internal execution command containing actor isolation, runtime provenance, socket, thread, and environment details;
- a user-facing public CLI instruction.

The direct Actor Session ownership is correct. The Web presentation contract is not.

## 3. Product Contract

### 3.1 Open TUI

`Open TUI` remains an automatic host action.

- It is enabled only for an attachable selected actor.
- It resolves one `AttachDescriptor` through `ActorSession`.
- It serializes that descriptor only for Terminal.app execution.
- Success reports `Terminal opened.`
- Failure reports `Could not open Terminal.`
- Its HTTP success and error payloads do not expose any command.

### 3.2 Copy command

`Copy command` is an independent manual convenience.

- It is available for the current attachable actor without requiring an `Open TUI` attempt.
- Clicking it fetches and copies one shell-quoted command with the selected actor ID already filled in.
- The command is safe to paste from any current working directory:

```bash
cd '<repo-root>' && ./buddyswitch-codex instance attach '<actor-id>'
```

- Success reports `Command copied.`
- Failure reports `Copy failed.`
- Copy pending and feedback state are independent from Open TUI pending and feedback state.

## 4. Architecture Boundaries

```text
Open TUI button
  -> Web Management open-tui operation
  -> ActorSession.resolve_attach(actor_id)
  -> AttachDescriptor
  -> private terminal execution command
  -> Terminal.app

Copy command button
  -> Web Management read-only attach-command projection
  -> shell-quoted public CLI text
  -> browser clipboard

Pasted public CLI
  -> CLI adapter instance attach
  -> ActorSession.resolve_attach(actor_id)
  -> exec_attach
```

The design keeps one attach owner: `ActorSession`.

The Web automatic path does not execute, import, or shell through the public CLI adapter. Returning public CLI text for a human to copy is a presentation contract, not an adapter-to-adapter runtime dependency.

The public CLI path is not a compatibility fallback. It is an existing first-class external interface. No second attach implementation, descriptor builder, or environment policy is introduced.

## 5. Component Design

### 5.1 Web Management API

Add a narrowly named read-only route:

```http
GET /api/instances/<actor-id>/attach-command
```

Response:

```json
{
  "ok": true,
  "actor_id": "act-pm-example",
  "command": "cd ... && ./buddyswitch-codex instance attach act-pm-example"
}
```

The route validates the actor ID and constructs only the public CLI text. It does not call `ActorSession.resolve_attach`, inspect runtime state, resume a thread, invoke Terminal.app, or call Host Control.

The existing `/api/instances/<actor-id>/open-tui` route continues to own automatic Terminal opening but stops returning `command` in both success and error payloads.

### 5.2 Web UI

Replace the current fallback command block with an independent `Copy command` button in the Tools action row.

Remove:

- `open-tui-fallback`;
- `open-tui-command`;
- `openTuiCommand` state;
- `commandFromError()`;
- Open TUI success/error assignments to command state;
- rendering conditions that couple command visibility to Open TUI state.

Add only the state needed for the independent action:

- `copyCommandPending`;
- `copyCommandMessage`.

Replace the Open-TUI-named runtime predicate with one attach-availability predicate used by both independent buttons. This shares the real actor attach precondition without sharing action state, requests, results, or feedback.

The copy request captures actor selection ownership before awaiting the API or clipboard. A late response or late clipboard completion cannot write feedback into a newer actor selection.

### 5.3 Architecture Tests

Keep the meaningful boundary that Web automatic execution does not call the CLI adapter.

Replace broad source-token assertions that forbid any user-facing `buddyswitch-codex` text with precise checks that prove:

- Web Management does not import the CLI adapter;
- Open TUI uses `ActorSession` and the private descriptor command;
- the attach-command route only returns public CLI text;
- neither route calls Host Control for attach semantics.

Delete `build_open_tui_attach_command()`, which exists only to bridge the old combined execution/display command. `_open_tui()` should call `terminal_command_from_descriptor()` directly for its private execution command. The new public copy builder has one responsibility and does not accept an `AttachDescriptor`.

## 6. Error Handling

- Invalid actor IDs return the existing structured invalid-request error before command construction.
- Clipboard API failure and textarea fallback failure remain UI-local and report `Copy failed.`
- Unsupported platform and Terminal automation failure affect only Open TUI feedback; the independent Copy button remains available when the actor is otherwise attachable.
- Attach failures after the user pastes the command are reported by the public CLI and Actor Session contracts.

## 7. Focused Test Strategy

Testing follows the optimized `./buddyswitch-test focused` entry and does not run the full suite.

### Backend behavior

- public copy command contains the validated, shell-quoted actor ID;
- public copy command is repo-context safe and contains only `instance attach`, not a direct Codex descriptor;
- attach-command GET has no Terminal, Actor Session, or Host Control side effect;
- Open TUI success payload contains no command;
- Open TUI error details contain no command;
- Terminal opener still receives a direct descriptor command and never receives the public CLI command.

### Frontend behavior

- Copy command works without an Open TUI attempt;
- Copy command requests the selected actor's attach-command route and copies the returned value;
- copy pending and feedback do not modify Open TUI pending or feedback;
- Open TUI success and failure do not modify copy state;
- stale API or clipboard completion cannot affect a newer actor selection;
- removed fallback elements and state names are absent from production assets.

### Focused verification scope

Run only the changed and directly dependent files:

- Web service unit tests;
- Web HTTP integration tests;
- external-control architecture tests;
- focused Web UI state tests;
- HTML and JavaScript asset contract tests.

## 8. Rebuild Rules

- Delete the old Open TUI command payload and fallback UI path in the same change.
- Delete old Open-TUI-coupled names such as `copy-tui-command-button`, `openTuiCommand`, `copyOpenTuiCommand`, `commandFromError`, and `build_open_tui_attach_command`; do not alias or wrap them.
- Delete fallback-only CSS and test-harness fields after their production elements are removed.
- Do not retain legacy response fields, hidden fallback elements, compatibility reads, or duplicate state.
- Do not restore Web automatic execution through `buddyswitch-codex`.
- Do not add a generic command registry, attach abstraction, terminal selector, or plugin layer.
- Do not include inherited PATH cleanup in this change.

## 9. Acceptance

The rebuild is accepted when:

1. `Copy command` is usable before any Open TUI attempt and copies one short, paste-ready CLI command for the selected actor.
2. Open TUI never returns or displays an execution command.
3. Copy and Open TUI have independent pending, feedback, request ownership, and rendering behavior.
4. Both automatic and pasted attach paths converge on `ActorSession` without a second attach implementation.
5. Old fallback DTO, DOM, state, and tests are removed rather than preserved.
6. The focused test set passes through `./buddyswitch-test focused`.
7. Review scans show no stale Open TUI command coupling or unrelated worktree changes.
