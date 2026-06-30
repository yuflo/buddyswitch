# Phase 07 Live Surface Residue

## Phase Objective

Remove or explain live-surface residue from the old eager browser startup contract. Live role guidance, runtime contracts, launcher behavior, search output, and tests must no longer teach actors that startup requires a ready Chrome endpoint, that cockpit MCP config carries a fixed `--browser-url`, or that missing `browser_port` is an ordinary user-facing unavailable state.

This phase covers memo Task 8.

## Exact Source Files To Modify

No runtime or test source changes were needed in this phase.

The live role and contract surfaces scanned cleanly for port/manual-startup guidance.

## Old And New Live Terms

Old live semantics removed from actor-facing surfaces:

- actor start requires Chrome endpoint readiness;
- actor start records `browser_port`;
- cockpit MCP config contains fixed `--browser-url`;
- `search.open_browser` reports missing `browser_port` as normal unavailable state.

New live semantics verified by scans and earlier phases:

- actor start registers browser capability without starting Chrome;
- `browser_port` means an active recorded endpoint only;
- cockpit MCP config is portless;
- browser/search calls ensure runtime on demand;
- TTL final release clears browser runtime.

## Residue Scans

Live eager-start residue scan:

```bash
rg -n "start.*Chrome|Browser cockpit ready:|--browser-url=http://127\\.0\\.0\\.1|instance browser_port is missing" \
  buddyswitch-codex tools/launcher scripts/env/tools/search tests tools/launcher/assets/roles framework/contracts
```

Observed accepted hits:

- `Browser cockpit ready:` remains only in explicit host `env browser ensure/status` output and tests for those commands.
- `--browser-url=http://127.0.0.1` remains only in stale MCP config fixture strings used to prove repair, plus internal upstream argv construction tests.
- `start.*Chrome` remains only in negative tests asserting actor start must not launch fake Chrome.
- `instance browser_port is missing` has no hits.

Role and runtime-contract guidance scan:

```bash
rg -n "browser_endpoint|browser_url|browser_port|manual browser|browser startup|start.*browser|Chrome endpoint|remote-debugging" \
  tools/launcher/assets/roles framework/contracts
```

Observed result: no hits.

Search live-surface scan:

```bash
rg -n "browser_endpoint|browser_url|browser_port|manual browser|browser startup|start.*browser|Chrome endpoint|remote-debugging" \
  scripts/env/tools/search tests/test_search_env_tool.py tests/test_env_tool_response_contract.py tools/launcher/assets/roles framework/contracts
```

Observed accepted hits:

- `browser_port` remains in test fixture setup and internal endpoint construction.
- `browser_endpoint`/`browser_url` remain in internal helper names and no-leak assertions.
- search tool guidance continues to tell actors to use `search.open_browser` and then `chrome-devtools-cockpit`; it does not teach ports, manual startup, or status-query startup.

## Phase Acceptance Checklist

- [x] Old and new live terms are defined.
- [x] Scoped residue scans were run.
- [x] Role AGENTS and contracts do not teach ports, manual browser startup, or status-query startup.
- [x] Remaining hits are accepted as explicit host command output, stale-config repair fixtures, internal upstream argv construction, or negative tests.
- [x] No runtime code change was needed for this phase.

## Plan Self-Review

- Memo coverage: maps to Task 8 residue scan and live guidance cleanup.
- Boundary check: historical memo/spec content was not rewritten; live role and runtime contract surfaces were scanned directly.
- SHARP check: this phase avoided speculative prompt churn because no live role/contract residue existed.
