# Scenario Matrix

Use this matrix to choose scenarios. Do not run every row by default; select rows that match the target claim.

The second column names the product entry surface or concrete adapter. Before reporting, map it back to a top-level means family from `simulation-means.md`.

When `G2` includes more than two independent surfaces, split them across bounded sub-agents when tooling is available. Do not share an actor or run root across sub-agents unless the scenario explicitly tests cross-surface interaction.

## Core CLI Lifecycle

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Actor start | CLI | `instance start --role <role> --json`, `status --json` | actor id present; status active; app-server healthy; daemon ready/live; runtime broker healthy; thread id present |
| Task Sys input | CLI | `instance input <actor> --text ... --json` | Task Sys task created; runtime action matches instruction; side task lease exists when `start_side` |
| Host side start | CLI | `instance side <actor> --text ... --json` | side thread id; parent thread id; turn id; one open lease |
| Host side send | CLI | `instance side <actor> --side-thread-id <id> --text ... --json` | same side id; expected turn id used when active; no duplicate lease |
| Host side close | CLI | `instance side close <actor> --side-thread-id <id> --json` | interrupt attempted when turn id exists; lease unregistered; no old turn-discovery RPC |
| Stale side id | CLI | send after close | rejected before steer; no wrong state mutation |
| Cross-actor side id | CLI | actor B sends to actor A side id | rejected before steer; actor B state unchanged |

## Web Management

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Web create/status | HTTP API | `POST /api/instances`, `GET /api/instances/<actor>/status` | response ok; actor id; status mirrors CLI |
| Web side start/send | HTTP API | `POST /api/instances/<actor>/side` with and without `side_thread_id` | Web returns action, side id, parent id, turn id; status refreshed |
| Web side close | HTTP API | `POST /api/instances/<actor>/side/close` | close fields surfaced; cleanup state matches instance record |
| Web invalid input | HTTP API | empty text or missing side id | 400 invalid request; no CLI command or state mutation |
| Web visible lifecycle | Playwright/browser MCP by default; Chrome DevTools MCP only for CDP evidence | open Web management page; create actor; start/send/close side if the UI exposes it | visible state matches API/status; screenshot or page snapshot captured |

## IM Wake

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Message to actor | Web/IM service + daemon wake | create sender/target actors; send message to target; wake target | `im.message.created` source; Task Sys side task; target actor only |
| Wrong target | Daemon wake | wake payload target does not match local actor | failed/ignored; no Task Sys task |
| Reply/ack close | Env tool or native MCP | side handles message then `task_sys.close` | source IM action occurs before close; no duplicate reply on retry |

## Track Comment Wake

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Mention target actor | Track comment + central signal | create track/comment mentioning target; deliver wake | `track.comment.added` source; target side task; source actor captured |
| Reply route | Track comment reply | reply to comment intended for target | recipient logic accepted; task created |
| Wrong recipient | Track comment | comment not intended for target | failed/ignored; no Task Sys task |
| Archived/wrong thread | Track comment | archived track or mismatched thread | rejected; state unchanged |

## Stress And Recovery

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Sequential high-frequency side send | CLI or Web | 10-50 repeated sends to same side id | no duplicate lease; turn id progression expected; no stale steer |
| Small concurrent side send | CLI or Web | 2-5 sends to same side id in parallel | no wrong actor mutation; errors are explicit; final lease valid or explicitly closed |
| Stop/resume existing side id | CLI | side start; stop; resume; status; send or close old side id | expected semantics stated first; either valid send/close or explicit stale rejection |
| Interrupt failure cleanup | Fake Codex failure injection | configure interrupt error; close side | lease unregistered despite interrupt error |
| Daemon/broker unavailable | CLI/env tool | stop runtime component or simulate unavailable | blocked/failed with correct message; no raw object writes |

## Browser Cockpit / Search

| Scenario | Entry surface / adapter | Minimum actions | Required assertions |
| --- | --- | --- | --- |
| Search opens browser URL | Env tool / broker | actor calls search open-browser with no recorded browser port | broker/browser capability used; no source root or launcher CLI path exposed to actor |
| Cockpit first tools call | MCP/cockpit proxy | call first browser tool when upstream is not started | browser acquired through control-plane owner; upstream starts once; no subprocess ensure path |
| Page reuse and limit | CDP/browser session | open same URL twice, then open until page limit | exact URL reuse; hard limit blocks new page without creating target |
| Browser release/restart | browser runtime manager | open page, release/idle, call browser again | resources cleaned; next call reacquires cleanly; no stale pid/socket/page marker |
| Browser residue scan | source/test scan | scan runtime/search/cockpit/release paths | old `env browser ensure/release` subprocess semantics absent from live runtime surfaces |

## Sub-Agent Fit

Use this table when deciding whether to split work.

| Workstream | Sub-Agent Fit | Actor / Run Root Rule | Notes |
| --- | --- | --- | --- |
| Core CLI lifecycle | Main agent by default; sub-agent only for isolated reproducer | Unique actor unless cross-actor rejection is the scenario | Often establishes baseline state for later gates. |
| Web API/UI lifecycle | Good fit | Unique actor and Web server/run root if possible | Browser artifacts and HTTP traces are self-contained. |
| IM wake | Good fit | Source/target actors isolated to the workstream | Use message scripts as `scripted-invocation`, not a separate top-level means. |
| Track comment wake | Good fit | Source/target actors isolated to the workstream | Use comment scripts as `scripted-invocation`, not a separate top-level means. |
| Stress/recovery | Good fit only with isolated resources | One mutating stress runner per actor | Avoid parallel stress writers against the same side thread unless testing concurrency. |
| Static residue audit | Ideal fit | No actor required | Read-only scan can run while runtime simulations execute. |
| Log/state review | Good fit after a run | Read-only after scenario completes | Sub-agent should classify failures and point to evidence, not patch code. |

## Role Defaults

- Use `test` for live smoke unless the target requires source write.
- Use `dev` for source-write or implementation-facing behavior.
- Use `pm -> dev` for Track comment source/target flows.
- Use `market` or role under test for IM wake flows when message behavior matters.
