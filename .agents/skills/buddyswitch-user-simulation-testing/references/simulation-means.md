# Simulation Means

Use this reference to choose how BuddySwitch simulated-user tests should be performed.

First choose the **performance means family**: how the user behavior is simulated and evidenced. Then choose the concrete adapter: CLI command, HTTP call, helper script, browser tool, fake Codex, live Codex, IM message script, Track comment script, etc.

Do not promote adapter names such as Web API, IM wake, Track wake, or Chrome DevTools MCP into top-level means. They are implementation choices under a broader means family.

## Table Of Contents

- [Means Families](#means-families)
- [Adapter Map](#adapter-map)
- [Effect-To-Means Rules](#effect-to-means-rules)
- [Selection Rules](#selection-rules)
- [Browser Adapter Notes](#browser-adapter-notes)
- [Output Labels](#output-labels)
- [Evidence By Means Family](#evidence-by-means-family)

## Means Families

| Means Family | What It Represents | Typical Adapters | Best For | Does Not Prove |
| --- | --- | --- | --- | --- |
| `visible-operation` | A visible user-like operation on a page or desktop surface | Playwright/browser MCP, screenshots; Chrome DevTools MCP only for CDP-specific evidence; Desktop `@Chrome` or Computer Use only when required | What a user sees, clicks, types, and navigates through | route payload correctness, daemon internals |
| `scripted-invocation` | A script drives the same product entry a user or external system would hit | `./buddyswitch-codex`, HTTP requests, Python/shell helpers, env tools, IM message creation, Track comment creation, fake Codex calls | CLI/API flows, event entrypoints, actor lifecycle, wake routing | visible layout or human visual perception |
| `state-log-audit` | Inspect product state and logs after a user-like action | status JSON, runtime snapshots, fake calls JSONL, daemon/app-server logs | target routing, lease ownership, stale rejection, no leaked source paths | behavior by itself without a preceding action |
| `stress-recovery-drive` | Repeated, concurrent, interrupted, or resumed use | loops, small concurrency scripts, stop/resume/restart scripts, cleanup failure probes | stability claims, ordering, stale state, resource reuse | broad production soak |
| `live-dependency-smoke` | The flow crosses a real external/runtime dependency | live Codex app-server, signed-in Chrome profile, real browser extension connection | real service/profile compatibility | full coverage across all entrypoints |
| `static-residue-audit` | Static scan proves old live surfaces or guidance are gone | scoped `rg`, asset scan, role guidance scan, test scan | rebuild/replace claims, stale UI/API/path removal | runtime behavior |

## Adapter Map

Use these adapters under the families above:

| Adapter | Means Family | Use When | Minimum Evidence |
| --- | --- | --- | --- |
| Playwright/browser MCP page operation | `visible-operation` | visible WebUI behavior matters in Codex CLI | URL, viewport, actions, screenshot/snapshot, console/server notes |
| Desktop/Chrome profile operation | `visible-operation` + `live-dependency-smoke` | logged-in Chrome, extension, profile, or desktop GUI state matters | explicit authorization, Codex App/Desktop backend proof, screenshots/tool trace |
| CLI command | `scripted-invocation` | actor lifecycle or command-facing user flow matters | command, JSON output, status/log evidence |
| HTTP/API request | `scripted-invocation` | Web route behavior, payload shape, or error mapping matters | method/path/body/status/response, server log |
| IM message script | `scripted-invocation` | IM entrypoint must wake the target actor | message/source/target ids, wake payload, resulting task/status, wrong-target negative |
| Track comment script | `scripted-invocation` | Track comment entrypoint must wake the target actor | track/comment/thread/source/target evidence, resulting task/status, wrong-recipient negative |
| Fake Codex harness | `scripted-invocation` + `state-log-audit` | deterministic host orchestration or RPC choices matter | fake state file, calls JSONL, forbidden RPC assertions |
| Live Codex app-server | `scripted-invocation` + `live-dependency-smoke` | claiming real Codex compatibility | proof fake `codex` is not in `PATH`, live command/logs, cleanup |
| Browser cockpit/search tool | `scripted-invocation` + `state-log-audit` | browser capability ownership, page reuse, or proxy lifecycle matters | broker request, manager status, target state, proxy logs, cleanup |
| Residue scan | `static-residue-audit` | old paths/UI/API/guidance must be absent | exact `rg` command, allowlist, output, interpretation |

## Effect-To-Means Rules

Infer the required means from the target effect before choosing concrete adapters.

| Effect Signal | Required Means / Gates | Typical Adapters | Downgrade If Skipped |
| --- | --- | --- | --- |
| lifecycle, lease, turn id, target, stale state, cross-actor, cleanup ownership | `scripted-invocation` + `state-log-audit`; usually `G1`, plus `G2` if the effect names a user entry surface | CLI, HTTP API, fake Codex harness, status JSON, calls JSONL, daemon logs | Cannot claim target/lease/lifecycle stability. |
| stable, high-frequency, concurrent, repeated use, restart, stop/resume, recovery, interrupt failure | `stress-recovery-drive` + `state-log-audit`; `G3` | loop/concurrency scripts, stop/resume scripts, failure injection with fake Codex | Cannot claim stability under repeated, concurrent, or recovered use. |
| Web, CLI, IM wake, Track comment wake, browser/cockpit, user entry | `scripted-invocation` or `visible-operation`; `G2` | HTTP request, CLI command, IM message script, Track comment script, browser/page operation | Cannot claim multi-entry or that named entry surface. |
| visible UI, browser page state, human operation | `visible-operation`; `G2` | Playwright/browser MCP, Chrome DevTools MCP when CDP evidence is required, Desktop `@Chrome` only when authorized | Cannot claim user-visible behavior. |
| live Codex, real service, signed-in Chrome profile, extension backend, external profile state | `live-dependency-smoke`; `G4` | live Codex app-server, Desktop `@Chrome` from Codex App/Desktop, real extension/profile proof | Cannot claim live-service or signed-in profile compatibility. |
| remove, replace, converged, no old path, no fallback, no residue | `static-residue-audit`; often `G0` plus runtime gates | scoped `rg`, role guidance scan, UI/API scan, test scan | Cannot claim convergence/removal of the old path. |

## Selection Rules

- User-provided surfaces are hints, not the source of truth. The source of truth is the expected product effect inferred from the memo, commit, or target claim.
- For visible UI claims, include `visible-operation`. Unit/static tests or API calls alone are not enough.
- For product entrypoint claims, include `scripted-invocation`. CLI, HTTP API, IM wake, and Track wake are adapters under this family.
- For lifecycle/target/stale-state claims, pair the invocation with `state-log-audit`.
- For "stable" claims, include `stress-recovery-drive` that matches the claim: repeated sends, small concurrency, stop/resume, restart, release/reacquire, or cleanup failure.
- For real Codex, signed-in Chrome, extension, or external profile claims, include `live-dependency-smoke` and get explicit user authorization when required.
- For rebuild/replace claims, include `static-residue-audit` over live code, role guidance, tests, and UI assets.
- If a required means family is target-relevant but skipped, downgrade the result and never report `FULL PASS`. Do not replace a skipped family with a lower-level adapter.

## Browser Adapter Notes

- Browser tools are adapters, not top-level means. A browser tool usually supports `visible-operation`; it may also support `state-log-audit` through console/network/DOM inspection.
- Codex CLI default for local/public pages: use Playwright/browser MCP. This is the practical default because current CLI sessions can have `browser@openai-bundled` and `chrome@openai-bundled` installed while the Chrome extension backend remains unavailable.
- Use Chrome DevTools MCP for console, network, performance trace, DOM/style inspection, heap/target state, or other Chrome/CDP-specific checks. Do not use it as the default page-clicking adapter just because it is available.
- Treat the Codex Chrome extension backend as unavailable in CLI unless the current session proves `agent.browsers.list()` includes a backend and `agent.browsers.get("extension")` succeeds.
- Do not loop on reinstalling Chrome/browser plugins when CLI reports `Browser is not available: extension`, `agent.browsers.list()` returns `[]`, or Codex App logs show `browser-use native pipe rejected socket peer reason=untrusted-code-signing-identity`; record the limitation and use Playwright/browser MCP or Chrome DevTools MCP according to the claim.
- CLI Chrome DevTools MCP setup: `codex mcp add chrome-devtools -- npx chrome-devtools-mcp@latest`, then start a new Codex CLI session. If already listed by `codex mcp list` and `list_pages` works, no user install is needed for CLI browser probing.
- Desktop `@Chrome` / `chrome:control-chrome` setup: use the skill entry when it is listed in a Codex App/Desktop session. Do not hard-code a versioned cache path; prefer the session skill or the `latest` plugin symlink. Do not claim Chrome profile coverage until the session can actually operate the Chrome backend.
- Environment mismatch is a blocker: if the current session only exposes Chrome DevTools MCP or Playwright/browser MCP, do not use `chrome:control-chrome`; use the available browser adapter and downgrade signed-in Chrome claims.
- Desktop Developer mode/full CDP: enable Settings > Browser > Developer mode only when performance traces, network/console inspection, DOM/style inspection, or CDP-level debugging is required. Organization policy can block this.
- File uploads through Desktop `@Chrome`: user may need to allow file URL access for the Codex Chrome extension.

## Output Labels

Use these top-level labels in checkpoints and reports:

- `visible-operation`
- `scripted-invocation`
- `state-log-audit`
- `stress-recovery-drive`
- `live-dependency-smoke`
- `static-residue-audit`

When useful, append the adapter in parentheses:

- `scripted-invocation (CLI + fake Codex)`
- `scripted-invocation (IM message script + Track comment script)`
- `visible-operation (Playwright/browser MCP)`
- `state-log-audit (Chrome DevTools MCP)`
- `live-dependency-smoke (Desktop @Chrome)`

## Evidence By Means Family

| Means Family | Minimum Evidence |
| --- | --- |
| `visible-operation` | target URL/app, viewport/window state, user actions, screenshot/snapshot, visible assertions. |
| `scripted-invocation` | script/command/request, inputs, output/status, relevant server or runtime logs. |
| `state-log-audit` | snapshots/logs/calls inspected after the action, expected and negative assertions. |
| `stress-recovery-drive` | iteration/concurrency/recovery plan, final state, rejected stale operations, no leaked resources. |
| `live-dependency-smoke` | live dependency proof, auth/profile/plugin status when relevant, command/tool trace, cleanup. |
| `static-residue-audit` | exact scan command, scope, allowlist, output, interpretation. |
