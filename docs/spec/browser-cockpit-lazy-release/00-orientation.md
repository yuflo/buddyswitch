# Browser Cockpit Lazy Release Orientation

## Source Documents Read

- `AGENTS.md`
- `docs/memo/2026-06-30-browser-cockpit-lazy-release-optimization-plan.md`
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`
- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`
- `docs/spec/browser-new-page-ttl-registration.md`
- `docs/spec/browser-cockpit-lazy-release-execution-framework-prompt.md`

## Rebuild-Forward Constraints

- Replace eager browser startup with lazy first-use startup; do not keep eager and lazy modes side by side.
- Keep the actor-facing `chrome-devtools-cockpit` MCP server registered as a stable lightweight surface.
- Do not expose `browser_port`, `browser_endpoint`, `browser_url`, or internal browser URLs in ordinary actor-facing output.
- Keep browser lifecycle ownership inside the browser slice: launcher browser functions, cockpit proxy, CDP lifecycle helpers, browser daemon handlers, browser inbound registration, and search browser projection.
- Do not add compatibility flags, generic resource managers, event buses, plugin systems, or broad abstractions.
- Use tests and scoped residue scans as completion gates; no phase is complete without focused behavior verification, cleanup checks, and residue checks.

## Phase Index

1. Lightweight actor start/resume registration and portless cockpit MCP config.
2. Host browser ensure port ownership and missing-port allocation.
3. Stable lazy cockpit MCP proxy facade.
4. Page idle final-target release scheduling and stale endpoint cleanup.
5. Browser cockpit release handler and launcher release entrypoint.
6. `search.open_browser` ensure-on-demand and endpoint leak removal.
7. Live surface residue removal.
8. End-to-end lazy start, idle release, and restart smoke.
9. Final acceptance evidence and full verification.

## Global Acceptance Gates

- Actor start/resume does not start Chrome or upstream `chrome-devtools-mcp`.
- Browser and search tools remain available to actors after start/resume.
- `tools/list` and status collection do not start Chrome or upstream MCP.
- First real cockpit or search browser use starts the actor-owned runtime and succeeds.
- Page TTL closes or forgets pages and schedules keyed release when no tracked pages remain.
- Release stops upstream MCP and actor-owned Chrome, clears page idle state, and clears `browser_port`.
- Later browser/search use starts the runtime again.
- Foreign endpoints and listeners are not killed.
- Ordinary actor-facing browser/search payloads do not expose internal browser endpoints.
- Focus behavior, background page creation, page-limit gates, `new_page` target reconciliation, and TTL refresh remain covered.
- Service-starting tests clean up process groups, pid files, sockets, and temporary runtime files.
- Scoped live-surface residue scans have no unexplained old eager-start hits.

## Known High-Risk Integration Points

- `buddyswitch-codex` start/resume currently calls `buddyswitch_browser_allocate_instance_port`, `buddyswitch_browser_bootstrap`, and records `browser_port`.
- `tools/launcher/browser_cockpit.sh` currently couples `buddyswitch_browser_bootstrap` to Chrome endpoint startup and cockpit MCP registration.
- `tools/launcher/browser_cockpit.sh` currently writes cockpit MCP args with `--browser-url=http://127.0.0.1:<port>`.
- `tools/launcher/chrome_devtools_cockpit_proxy.py` currently requires `--browser-url`, starts upstream before reading client messages, and exits with upstream.
- `buddyswitch-codex env browser ensure` currently defaults toward `9222` when no `browser_port` is recorded.
- `scripts/env/tools/search/_impl.py` currently treats missing `browser_port` as `E_SEARCH_BROWSER_UNAVAILABLE` and includes `browser_endpoint` in multiple ordinary outputs.
- `tools/launcher/browser_page_expired_handler.py` currently reads cached `context.instance_payload["browser_port"]` and does not forget targets on stale endpoint errors.
- Release must coordinate upstream process markers, Chrome pid markers, `instance.json`, and `runtime/browser/page_idle.json` without killing foreign listeners.
- Tests that start fake Chrome, fake upstream MCP, daemon, app-server, or runtime broker must prove residual cleanup before broad verification.

## Global Residue Search Terms

```bash
rg -n "start.*Chrome|Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|instance browser_port is missing|browser_endpoint|browser_url" \
  buddyswitch-codex tools/launcher scripts/env/tools/search tests tools/launcher/assets/roles framework/contracts docs/spec/browser-cockpit-lazy-release
```
