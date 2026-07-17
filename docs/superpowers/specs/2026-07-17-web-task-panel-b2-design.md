# Web Task Panel B2 Design

Date: 2026-07-17

Status: Approved direction; awaiting written-spec review before implementation planning

## Acceptance

When a user selects a teammate, the 300px right-rail Task card shows the highest-priority current task and two recent terminal tasks in a default height no greater than 220px, and completed work remains visible after the current task disappears.

Consumer path:

```text
select teammate -> Web Console external-safe Task projection -> B2 Task card -> current and recent terminal state remain observable
```

Implementation baseline:

`docs/memo/2026-07-17-web-task-panel-b2-implementation-baseline.html`

## Product Scope

The Task card is a compact, read-only supervision surface. It answers three questions:

1. Is a task active now?
2. Does a recoverable task need attention?
3. What are the most recent completed or canceled tasks?

The card does not become a task administration interface.

## UI Geometry

- Production right rail: 300px, matching the existing `team-room` third column.
- Rail padding: 12px.
- Task card width: 276px.
- Task card internal width: 252px after existing 12px card padding.
- Default Task card height: no greater than 220px for one current task plus two terminal tasks.
- Expanded history and row details may increase height; the surrounding rail already owns vertical scrolling.
- The Task card must not introduce an internal scrollbar.

## Information Hierarchy

The card header shows total state without another summary block:

```text
Task                              1 active · 5 recent
```

The body uses one continuous ledger:

1. one current row, or a compact no-active row;
2. an integrated `Recent` disclosure header;
3. two terminal rows by default, up to five when expanded.

The current slot selects `recoverable_tasks[0]` when a recoverable task exists; otherwise it selects `active_tasks[0]`. This keeps a task requiring attention from being hidden by another active task. `active_count` remains visible in the header, so the single-row supervision surface does not imply that only one active record exists.

Concurrent active-task browsing is not added in this slice. The current WebUI already presents one current task, and this change remains focused on terminal-history visibility.

## Required States

### Active

- Teal current row.
- Primary text: `source_type`.
- Secondary text: `Now · <status>`.
- Short local time at the right edge.
- Two recent terminal rows remain visible.

### Needs attention

- The recoverable task occupies the current slot.
- Amber row replaces teal; no additional warning strip is added.
- Copy is limited to `Needs attention · <status>` because the external-safe contract does not expose failure detail.
- Two recent terminal rows remain visible.

### No active task

- A 36px compact row says `No active task` and `Recent stays visible`.
- The terminal list stays in the same position.
- When no active or terminal task exists, the body shows one compact `No tasks yet` row instead of an oversized empty state.

## Interaction

### Recent disclosure

- The `Recent` section header is the only list disclosure control.
- Collapsed: show the first two of at most five terminal rows.
- Expanded: show all terminal rows supplied by the Web Console projection.
- The control exposes accurate `aria-expanded` state and text (`Show all` / `Show fewer`).

### Row detail

- Clicking a current or terminal row expands detail directly below that row.
- Only one row detail can be open at a time.
- Detail contains the full `task_id` and full ISO `updated_at` value.
- Clicking the open row closes it.
- Row controls expose accurate `aria-expanded` state and keyboard focus.

## Data Ownership And Contract

### Task Sys

`scripts/env/domain/task_sys.py` remains the sole owner of Task lifecycle status, persistence, and transitions. No Task Sys storage or mutation change is required.

### Task Read

`scripts/env/domain/task_read.py::actor_external_task_projection` adds:

```text
terminal_tasks: completed and canceled external-safe summaries, sorted by updated_at descending
terminal_count: total terminal record count for the actor
```

Terminal classification uses the Task Sys `COMPLETED` and `CANCELED` constants. The external row allowlist remains exactly:

```text
task_id, source_type, status, actor, updated_at
```

Task Read owns terminal classification so the Web adapter and browser do not reproduce lifecycle rules.

### Web Console

`tools/launcher/web_management.py::_actor_console` forwards:

```text
terminal_count
terminal_tasks[:5]
```

It does not filter status or change ordering.

### WebUI

`tools/launcher/assets/web-management/app.js` renders the B2 states and interactions. `styles.css` owns only B2 presentation. The browser may format `updated_at` into a deterministic short local time for the compact row; the full value remains available in row detail.

There is no compatibility fallback to the old active/recoverable-only Task card. The Web Console and consumer cut over together.

## Loading And Failure Behavior

- Existing actor-console loading and error states remain the owner of request progress and failure messaging.
- B2 does not add its own fetch, retry, polling, or error policy.
- A present `task_sys` object with empty arrays renders the compact no-task state.
- Missing required B2 fields are treated as a contract defect and are not hidden by a second legacy renderer.

## Explicit Non-Goals

- pagination, search, filters, or a dedicated task page;
- close, cancel, retry, or other lifecycle mutation controls;
- execution result, events, summary, failure reason, source reference, or internal context exposure;
- concurrent active-task browsing;
- new Task storage, schemas, service boundaries, or background processes;
- an internal scrollbar inside the Task card.

## Proof Strategy

### Contract

- Task Read test: completed and canceled tasks appear in `terminal_tasks`, active tasks do not, sorting is descending, count is exact, and the external allowlist is unchanged.
- Web Console test: terminal fields are forwarded and capped at five without sensitive fields.

### UI

- Web state test: Active, Needs attention, and No active task render the expected row and header count.
- Web interaction test: Recent expands from two to five and contracts; row detail is exclusive and exposes only `task_id` and `updated_at`.
- Negative assertions: no execution, events, failure result, relation, description, mutation control, or legacy Task summary markup.

### Browser

- Exact 300px rail and 276px Task card.
- Default height no greater than 220px in all three required states.
- No horizontal overflow at the Task card and narrow-page boundaries.
- Keyboard focus, `aria-pressed`, and `aria-expanded` states remain accurate.
- No main-path console error after scenario, disclosure, row-detail, copy, and reset interactions.

## Replacement

The existing Task summary renderer is replaced in place. No alternate Task panel, legacy renderer, compatibility alias, fallback response shape, or second status classifier remains live.
