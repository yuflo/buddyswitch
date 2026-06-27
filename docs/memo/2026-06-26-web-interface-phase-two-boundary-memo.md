# Web Interface Phase Two Boundary Memo

## Purpose

This memo records the phase two design focus for the BuddySwitch Web interface.
It is a task-scoped memo, not the durable call-architecture rulebook.

Phase two should move the Web surface from an instance-centered control room to
an actor-centered console with an independent Track workspace, while preserving
clean layer boundaries.

Guiding rule: do not add new entities or lower-layer interfaces unless they are
needed to avoid a real boundary violation or duplicated domain semantics.

## Current Code Facts Checked

Current Browser calls are still instance/control oriented:

- `tools/launcher/assets/web-management/app.js`
  - calls `/api/health`;
  - calls `/api/roles`;
  - calls `/api/instances`;
  - calls `/api/instances/{actor_id}/status`;
  - calls instance actions such as `interrupt`, `stop`, `clear`, `resume`,
    `open-tui`, and delete;
  - calls `/api/im/external-participants`, `/api/im/messages`, and
    `/api/im/events`.

Current Web HTTP routes are in `tools/launcher/web_management.py`:

- `/api/health`
- `/api/roles`
- `/api/instances`
- `/api/instances/{actor_id}/status`
- `/api/instances/{actor_id}/input|side|side/close|interrupt|resume|stop|clear|open-tui`
- `/api/im/*`

Current IM HTTP routes are in `tools/launcher/im_http_router.py`:

- `POST /api/im/external-participants`
- `GET /api/im/actors`
- `POST /api/im/messages`
- `GET /api/im/events`
- `GET /api/im/conversations/direct`
- `GET /api/im/messages/{id}`
- `GET /api/im/messages/{id}/replies`
- `PATCH /api/im/messages/{id}/disposition`

Current reusable lower capabilities:

- Task domain read model: `scripts/env/domain/task_management.py::current_view`
- Message service: `scripts/env/services/messages.py`
- Host control: `buddyswitch-codex instance ...`
- Runtime context facts: `tools/launcher/daemon_core.py::load_daemon_context`
- Actor runtime tools: `scripts/env/tool_runtime/registry.py::dispatch_env_tool_request`

Track read behavior exists today, but much of the convenient read projection is
inside the actor tool handler:

- `scripts/env/tools/track/_impl.py::list_tracks_for_active_role`
- `scripts/env/tools/track/_impl.py::open_track_for_active_role`
- `scripts/env/tools/track/_impl.py::list_comments_on_track`

That module is a layer 4 actor runtime tool handler, not a Web service boundary.

## Layering Decision

Phase two uses this call shape:

```text
Browser UI
  -> Web-interface API
      -> Host control lower API       # instance/runtime facts
      -> Domain / service layer       # task/track/message semantics
          -> Repo / persistence

Actor runtime product API
  -> Domain / service layer
      -> Repo / persistence
```

The Browser must not call host control, actor runtime tools, repos, taskbox
paths, or JSON files.

The Web-interface API may do interface-specific composition. That composition
must stay inside layer 2 and must not become lower-layer product API.

## Phase Two Web API Gap

Phase two should add these Browser-facing product APIs at layer 2:

| Capability | API | Layer | Decision |
| --- | --- | --- | --- |
| Actor roster | `GET /api/actors` | Web-interface API | Add |
| Actor console | `GET /api/actors/{actor_id}/console` | Web-interface API | Add |
| Track workspace list | `GET /api/tracks` | Web-interface API | Add |
| Track detail | `GET /api/tracks/{track_id}` | Web-interface API | Add |

Existing APIs to reuse:

| Capability | API / Boundary | Layer | Decision |
| --- | --- | --- | --- |
| Actor direct conversation | `GET /api/im/conversations/direct` | Web-interface API | Reuse |
| Web sends message to actor | `POST /api/im/messages` | Web-interface API | Reuse |
| Message disposition | `PATCH /api/im/messages/{id}/disposition` | Web-interface API | Reuse |
| Instance lifecycle/status | `/api/instances/*` | Web-interface API -> host control | Reuse as control plane |
| Actor task state | `task_management.current_view(...)` | Domain / service | Reuse |
| Message semantics | `env.services.messages` | Domain / service | Reuse |

## Interface Composition Boundary

Some ad-hoc composition is expected in layer 2.

Example:

```text
GET /api/actors/{actor_id}/console
  -> instance/runtime facts
  -> task current view
  -> related track summary
  -> direct IM summary
  -> Web DTO
```

This is acceptable because the composition is a Web product view. It should be
implemented as private Web-interface code, not as a new lower-layer entity.

The composition becomes pollution only if it leaks UI concepts downward, such as:

- workspace layout
- sidebar rows
- console cards
- tabs
- badge colors
- selected state
- empty-state copy
- actor-console section names

Those belong in the Web-interface layer.

## Track Boundary Review

Do not introduce a `TrackReadService` entity by default.

The first choice is:

```text
Web-interface API performs Track page composition privately.
```

Only extract lower Track read functions if Web otherwise has to do one of these:

1. import `scripts/env/tools/track/_impl.py` directly;
2. duplicate nontrivial Track read rules already used by actor tools;
3. read Track repos directly and reimplement business filtering/thread grouping.

If extraction becomes necessary, extract only small domain read functions. Do not
create a broad service class or UI-shaped API.

Acceptable domain-level function names:

- `track_summary(...)`
- `track_detail(...)`
- `comment_threads(...)`

Acceptable extracted semantics:

- non-archived Track filtering;
- Track summary normalization;
- Track detail normalization;
- comment thread grouping;
- open/resolved status counts;
- materials/proofs relation classification;
- updates normalization.

Forbidden lower-layer names or concepts:

- `track_workspace(...)`
- `track_panel(...)`
- `track_card(...)`
- `actor_console_track_section(...)`
- layout, tab, badge, sidebar, or selected-row concepts.

This keeps Track extraction as moving existing reusable semantics to the right
layer, not creating a Web-specific lower service.

## APIs Not Split In Phase Two

These are intentionally not first-cut APIs:

- `GET /api/actors/{actor_id}/tasks`
- `GET /api/actors/{actor_id}/tracks`
- `GET /api/tracks/{track_id}/comments`
- lower `actor.tasks`
- lower `track.workspace`

Reason: these are either UI sub-panel boundaries or lower-layer UI-shaped
interfaces. Keep the first cut coarse until independent refresh, permission,
caching, loading, or interaction needs prove a real split.

## Phase Two Target Shape

Actor console:

```text
Browser
  -> GET /api/actors/{actor_id}/console
  -> Web-interface composition
      -> host control for runtime facts
      -> task domain for task state
      -> message service for IM state
      -> Track read semantics only if needed
```

Track workspace:

```text
Browser
  -> GET /api/tracks
  -> GET /api/tracks/{track_id}
  -> Web-interface composition
      -> minimal Track domain read functions
          -> Track repos
```

The risk to avoid is pushing Web shape into lower layers. The practical rule is:

```text
Web shape stays in Web.
Reusable domain semantics may move down.
Storage mechanics stay in repos.
Actor capability stays in runtime tools.
```
