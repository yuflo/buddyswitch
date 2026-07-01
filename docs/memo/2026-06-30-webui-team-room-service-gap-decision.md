# WebUI Team Room Service Gap Decision

Artifact:

- `docs/memo/2026-06-30-webui-team-room-service-gap-decision.html`

Job:

- Help review the Team Room redesign by mapping desired UI areas to current WebUI endpoints, DTO fields, service gaps, and UI cuts.
- Confirm the implementation boundary before coding: no backend additions, and product code changes stay inside the WebUI module.

Main decision:

- Build Team Room v1 as a frontend projection over existing Web-interface APIs.
- Do not add a new Team Room backend service for v1.
- Do not add backend routes, DTOs, persistence, env tools, or runtime services for this slice.
- Keep implementation work scoped to `tools/launcher/assets/web-management/` plus focused WebUI tests when behavior changes.
- Keep only `Team room` and `Tracks` as top-level tabs.
- Use D-style Track Studio as the `Tracks` tab, backed by current read-only Track list/detail APIs.

Current API coverage is enough for v1:

- `GET /api/actors`
- `GET /api/roles`
- `GET /api/actors/:actor_id/console`
- `GET /api/tracks`
- `GET /api/tracks/:track_id`
- Unified `/api/im/*`
- Existing `/api/instances/*` lifecycle and TUI actions

Cut or defer now:

- Artifacts top-level tab
- Runtime health top-level tab
- Workstream OS
- Capacity/workload metrics
- Side-thread UI
- Track comment composer and Track write actions
- Fake unread counts, fake load percentages, fake teammate profile fields

Need test attention:

- Rename visible copy contract from Actor Console/Actors to Team room/Tracks.
- Add supported-data-only roster tests.
- Add rapid actor switching race coverage.
- Add Track Studio read-only render tests.
- Keep route/residue gates against mock controls, old IM routes, and subpanel APIs.
