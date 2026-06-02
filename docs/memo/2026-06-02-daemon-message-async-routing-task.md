# Daemon Message Async Routing Task

Date: 2026-06-02
Status: confirmed architecture memo before implementation planning

## 1. One-Line Decision

Upgrade the actor instance daemon into the local runtime coordinator for message async routing:

```text
target daemon
  -> receive generic message.available signal
  -> inspect local parent thread activity
  -> route through parent or side thread
  -> keep all parent thread control inside daemon-owned actions
```

The daemon is not becoming a message business module, workflow engine, event bus, or attention scoring
system. It owns local runtime coordination only.

## 2. Correct Daemon Positioning

The daemon's clarified positioning is:

```text
actor instance local runtime coordinator
  = presence/lifecycle
  + generic signal ingress
  + handler dispatch
  + controlled app-server thread actions
  + neutral action provenance
```

This is narrower and clearer than calling daemon an "attention" module. The daemon does not decide message
urgency, message content meaning, or whether a reply is semantically safe. Business modules and Codex turns make
those judgments.

What daemon owns:

- actor daemon start/stop/status, ready state, central registration, heartbeat;
- local mailbox socket for generic signal delivery;
- app-server thread state inspection for this actor instance;
- parent thread submit/interrupt actions;
- side thread start/reuse/send/close actions;
- validation that a side thread belongs to this actor instance and parent thread;
- neutral provenance and handler/action status for runtime debugging.

What daemon does not own:

- message inbox reading;
- message reply content;
- case 2 vs case 3 semantic judgment;
- message TUI wording, except sending the prompt supplied by the message handler;
- target actor reachability policy beyond existing central delivery result;
- task checkout business filtering;
- generic workflow/plugin/event abstraction.

## 3. Current Code Facts

The current code already points to this boundary.

Daemon core is business-neutral:

- `tools/launcher/daemon_core.py` owns daemon state, lifecycle, handler dispatch, and `ActionGateway`.
- `ActionGateway.submit_turn(...)` currently submits to the main thread and records daemon-origin turn provenance.
- `DaemonState` stores ready/error/handler status and daemon-origin turn records.

Signal ingress is generic:

- `tools/launcher/daemon_mailbox.py` validates a generic signal envelope.
- It does not understand `message_id`; it dispatches to mailbox handlers.
- `tools/launcher/central_daemon_core.py` only checks online/offline reachability and relays `signal.deliver`.

Business handlers own business semantics:

- `tools/launcher/message_available_handler.py` owns `message.available` payload validation and current message TUI
  prompt submission.
- `tools/launcher/task_checkout_handler.py` owns task checkout notification filtering and task TUI prompting.

App-server primitives already exist:

- `tools/launcher/app_server.py` supports thread read, active turn lookup, input turn, side fork/start, interrupt,
  and side close.
- Existing `/side` launcher behavior stores side thread rows in `instance.json`, but that registry logic is currently
  embedded in shell inline Python inside `tools/launcher/env.sh`.

Codex thread behavior already checked for this design:

- `thread/fork` accepts the same permission override rules as `thread/start`.
- BuddySwitch side fork uses `permissions: buddyswitch-runtime`, `ephemeral: true`, and side developer instructions.
- Ephemeral side threads do not support persisted goal tools, but they still get ordinary runtime/native tools from
  the per-turn tool router when the permission profile exposes them.
- Therefore side triage is expected to use native message tools, but the implementation must still regression-test
  `message__list`, `message__conversation`, and `message__send` availability in a side turn.
- `turn/interrupt` interrupts the current in-flight turn only. It does not pause, clear, or mutate the parent thread's
  active Codex goal.
- After a daemon-submitted parent message TUI turn completes, any active goal continuation behavior remains Codex's
  normal parent-thread behavior. The daemon must not manage goals as part of message escalation.

Launcher/app-server boundary:

- The daemon must not call `codex-remote`, Codex source internals, or ad hoc Codex commands directly.
- Daemon thread control goes through BuddySwitch launcher-owned app-server wrappers and helpers, such as
  `tools/launcher/app_server.py` and `tools/launcher/submit_turn.py`, which speak to the local app-server control
  socket.
- The daemon is itself part of the launcher runtime layer, so it may call launcher Python helpers directly. It does
  not need to shell out to the `buddyswitch-codex instance ...` CLI for internal actions.
- The intended stack is `daemon -> BuddySwitch launcher app-server helper -> local Codex app-server JSON-RPC socket
  -> Codex thread`.

Message send reachability is already separate:

- `message.send` creates a durable message, delivers `message.available`, and cleans up if delivery fails.
- Target daemon offline/unreachable remains a delivery/reachability problem, not one of the runtime routing cases.

## 4. Runtime Routing Cases

After target daemon receives `message.available`, the routing cases are:

### Case 1: parent is idle

The daemon can determine locally that the parent/main thread is not running.

Expected behavior:

```text
message_available_handler
  -> render existing parent message TUI
  -> daemon action submits parent turn
```

This is behavior-equivalent to the current message handler path, but it should be implemented through the new
daemon action contract rather than kept as legacy compatibility logic.

### Case 2: parent is running, side can handle independently

The daemon starts or reuses a side thread for message triage.

Expected behavior:

```text
message_available_handler
  -> daemon action starts/reuses side thread
  -> side reads inbox/conversation with native message tools
  -> side sends a direct reply with message__send when safe
```

The side thread owns the triage judgment. The daemon only provides the side thread and records runtime actions.

### Case 3: parent is running, side needs parent

The side thread determines that the message conflicts with, interrupts, corrects, or otherwise materially affects the
parent's current work.

Expected behavior:

```text
side thread
  -> sends typed parent-required request to local daemon
message handler / daemon dispatch
  -> validates request and side ownership
  -> message handler renders parent message TUI
daemon parent action
  -> interrupts active parent turn when needed
  -> submits parent message TUI
  -> records action provenance/status
```

The side must not directly call launcher interrupt for the parent. It can decide that parent is required, but the
runtime control action stays daemon-owned.

There is no separate "delay for later" case in this iteration.

## 5. Required Daemon Capabilities

### 5.1 Parent Thread Activity Inspection

Add a daemon action/query that returns the local parent thread activity:

```text
idle | running | unavailable/error
```

It should be based on local app-server state, not central daemon reachability. The result may include the active
turn id when running, but final shape belongs to implementation tests.

Purpose:

- route `message.available` to parent when idle;
- route to side when parent is running;
- avoid letting central daemon infer local app-server state.

### 5.2 Explicit Parent Thread Actions

Replace the ambiguous `submit_turn` mental model with explicit parent actions.

Required actions:

- submit parent prompt;
- interrupt parent active turn;
- interrupt-and-submit parent prompt as one controlled gateway operation for case 3.

The composite case 3 action matters because splitting it into "side interrupts parent" and "daemon later submits
prompt" creates broken ownership and failure ambiguity.

Failure handling must be owned by daemon:

- interrupt failed because parent is already idle;
- interrupt succeeded but submit failed;
- submit succeeded and returned a new turn id;
- active turn id disappeared between inspection and interrupt.

The daemon should record these as runtime action facts, not business judgments.

### 5.3 Side Thread Registry Helper

Move side thread registry operations out of shell inline Python into a Python helper that both launcher CLI and daemon
can use.

Required operations:

- register side thread for actor instance and parent thread;
- require/validate side thread belongs to this actor instance and parent thread;
- unregister/close side thread;
- list or find reusable open side thread for the parent when appropriate.

Purpose:

- avoid duplicating side ownership checks;
- make daemon able to safely reuse `/side` infrastructure;
- prevent parent/side thread id confusion.

### 5.4 Side Thread Actions

Expose side actions through daemon `ActionGateway`.

Required actions:

- start side triage turn from parent thread;
- send follow-up input to an existing side thread;
- close/interrupt side thread when needed;
- record side action status and side thread id.

These actions should call existing app-server primitives where possible and preserve the same side runtime constraints
already used by launcher `/side`: parent fork, runtime workspace roots, `buddyswitch-runtime` permissions, ephemeral
thread, and side developer instructions.

The daemon is not implementing a new side runtime. It is making the existing side capability available to daemon
handlers with validation and provenance.

### 5.5 Typed Parent-Required Request

Add a narrow typed ingress for side-to-daemon escalation.

Required semantics:

```text
side can request: "parent is required for this message"
daemon verifies: actor, parent_thread_id, side_thread_id, and message origin
message handler supplies: parent TUI prompt
daemon executes: controlled parent interrupt/submit action
```

This is not a generic event bus. It is one explicit runtime control request needed because a child side turn cannot
own parent thread control directly.

The exact transport can be finalized in the implementation plan, but it must be typed and local-daemon-owned. It must
not rely on:

- parsing side natural language output;
- side directly calling launcher parent interrupt;
- sending a normal message to self;
- adding a broad workflow/event framework.

Allowed transport shapes:

- a new local daemon mailbox/control method with a narrow schema;
- or a generic signal type handled by a message-owned mailbox handler.

In both shapes, daemon core must remain business-neutral. The transport must not become central-daemon routing, normal
self-message delivery, or a generic multi-purpose event bus.

### 5.6 Neutral Action Provenance And Status

Expand daemon state from only daemon-origin turn provenance to neutral daemon action records.

Records should support, at minimum:

- handler name;
- origin id, such as message id or signal id;
- action type, such as parent_submit, parent_interrupt, side_start, side_send, parent_required;
- parent thread id;
- side thread id when relevant;
- action turn id or interrupted turn id when relevant;
- status/error;
- created/updated timestamps.

Purpose:

- debug routing decisions without reading message business content;
- avoid self-loop issues like task checkout;
- make status output meaningful;
- make regression tests deterministic.

## 6. Message Module Responsibilities During This Iteration

The message module will be rebuilt forward to use the new daemon capabilities. No legacy compatibility path is kept.

Message module owns:

- `message.available` payload validation;
- parent idle vs parent running routing policy, based on daemon activity result;
- side triage prompt content;
- side judgment instructions for case 2 vs case 3;
- parent message TUI prompt content;
- native message tool usage instructions for inbox/conversation/reply.

Message module does not own:

- direct parent app-server interrupt;
- side registry mutation;
- parent/side thread ownership validation;
- daemon action provenance shape.

The parent message TUI content for cases 1 and 3 can remain unchanged for this iteration. TUI copy optimization is a
later task.

## 7. Non-Goals

Do not add:

- a delayed/deferred message case;
- central daemon running/idle detection;
- message priority scoring in daemon;
- a general event bus;
- a plugin/workflow engine;
- a second message delivery path;
- fallback compatibility with the old message handler behavior;
- side natural-language output parsing as the escalation mechanism.

Do not move message business logic into daemon core.

## 8. Verification Boundary

This iteration should be test-bound before implementation is considered done.

Required focused tests:

- daemon parent activity inspection: idle, running, unavailable/error;
- parent action gateway: submit, interrupt, interrupt-and-submit;
- side registry helper: register, validate, reject main thread as side, unregister;
- side action gateway: start side, send existing side, close side;
- parent-required typed request: accepts valid side request, rejects wrong actor/parent/side;
- action provenance/status records for parent and side actions.

Required boundary tests:

- daemon core still does not import message domain logic;
- daemon mailbox remains generic except typed local control request support if implemented there;
- central daemon still only owns reachability/delivery, not thread activity;
- message handler owns `message.available` payload semantics;
- message module does not call launcher parent interrupt directly;
- message escalation does not clear, pause, or otherwise mutate the parent thread goal.

Required integration-style tests:

- `message.available` with parent idle submits parent message TUI;
- `message.available` with parent running starts/reuses side triage;
- side triage has native message inbox/conversation/send tools available;
- side independent handling can reply through native message tools;
- side parent-required request interrupts parent and submits parent TUI;
- target daemon offline remains message.send delivery failure and cleanup.

## 9. Final Architecture Highlight

The key boundary is:

```text
message/side owns judgment
daemon owns runtime control
message handler owns business TUI
daemon state owns neutral provenance
central daemon owns reachability only
```

That is why case 3 should not be implemented as:

```text
side directly calls launcher interrupt
  -> daemon later submits a prompt
```

That split makes parent control distributed and makes failures hard to attribute.

The cleaner design is:

```text
side requests parent
  -> daemon validates local runtime ownership
  -> message handler provides prompt
  -> daemon performs controlled interrupt-and-submit
```

The added daemon surface is therefore not business complexity. It is a narrow runtime control contract that keeps
thread ownership, action ordering, and provenance in one place.
