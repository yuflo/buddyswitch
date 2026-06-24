# Browser Tool Page Limit Resource Gate

Date: 2026-06-23
Status: task memo for implementation
Branch: `fea-tool`
Worktree: `.worktrees/fea-tool`

## Summary

Implement browser page-count coordination at the tool boundary.

The goal is to stop actors from endlessly opening browser pages during browser-native research. Do
not solve this with a skill, `innerTUI`, AGENTS prompt bulk, or a separate browser-session prompt.
The browser-opening tool paths must expose the current resource state in their responses and must
refuse to open a new page after the hard limit is reached.

The first limit values are:

```text
page_limit = 10
hint_threshold = 5
```

## Current Status

The requested branch setup is complete:

- local worktree exists at `.worktrees/fea-tool`;
- local branch is `fea-tool`;
- branch tracks `origin/fea-tool`;
- `origin/fea-tool` exists at the current `main` commit baseline.

No implementation code should be changed until this memo is reviewed.

## Current Bottleneck

Actors can already close browser pages when prompted, but the browser-opening flow does not make
page pressure visible and does not prevent more opening.

This causes the actor to keep opening pages because:

- the open operation usually succeeds without telling the actor how many pages are already open;
- there is no hard tool-level refusal that forces a close-or-reuse loop;
- relying on skill descriptions is not reliable once the actor is already inside a browser-heavy
  task;
- adding `innerTUI` would introduce another prompt path before proving that the tool contract itself
  is sufficient.

The current task is therefore a tool-contract task, not a prompt or skill task.

## Design Decision

Use a simple resource gate around browser page creation:

```text
If target URL is already open:
  do not open a duplicate page;
  return a concise reuse response.

If current page_count >= 10:
  block the open operation;
  do not create a page;
  return a concise reason and close/reuse instruction.

If opening would make page_count >= 5 and page_count < 10:
  allow the open operation;
  include a concise page-count hint in the response.

Otherwise:
  allow the open operation without a hint.
```

Canonical soft hint text:

```text
Browser pages: <count>/10. Reuse or close pages before opening many more.
```

Canonical hard block text:

```text
Blocked: browser page limit reached (10/10). Close or reuse existing pages, then retry opening this URL.
```

The wording must stay short and direct. Do not add long coaching text, workflow advice, or prose
that belongs in a skill.

## Scope

The limit must cover the browser-opening paths that can create new browser pages:

- `search.open_browser`, implemented in `scripts/env/tools/search/_impl.py`;
- `chrome-devtools-cockpit` `new_page`, mediated by
  `tools/launcher/chrome_devtools_cockpit_proxy.py`.

Covering only `search.open_browser` is incomplete because an actor can still call the browser MCP
`new_page` path directly.

## Out Of Scope

Do not add `innerTUI` prompts for this task.

Do not create or update browser-management skills.

Do not edit role AGENTS files to explain this behavior.

Do not add a generic resource-management framework, rule engine, or prompt router.

Do not auto-close pages in this task. The tool should block and tell the actor to close or reuse;
the actor should perform close/list/select actions through existing browser capabilities.

Do not add page-content heuristics, stale-page scoring, tab summarization, or policy for which pages
are safe to close. This task only counts pages, allows reuse, hints, and blocks.

## Boundary Requirements

Follow `docs/bitter/2026-05-18-tool-skill-layering-principles.md`:

- tool responses must explain the actual browser-session effect;
- rejected opens must explain why they were blocked;
- rejected opens must guarantee no page was opened;
- skills and AGENTS must not compensate for unclear tool contracts.

Follow `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`:

- do not add two unrelated special cases that each count pages differently;
- keep shared infrastructure stable and boring;
- put browser page-count evaluation in a low-level CDP/browser-session helper, not in a skill, role
  prompt, or search-specific workflow.

The clean boundary is:

```text
CDP page snapshot / open gate helper
  -> search.open_browser response semantics
  -> chrome-devtools-cockpit new_page proxy response semantics
```

The shared helper must not know about roles, tasks, search engines, skills, prompts, or product
objects.

## Suggested Implementation Shape

Add a small low-level helper near the existing CDP helpers, for example:

```text
scripts/env/cdp_browser_session.py
```

Its responsibility should be limited to:

- read `GET <browser-url>/json/list`;
- count targets where `type == "page"`;
- detect whether the requested target URL is already open;
- evaluate whether opening one more page should be allowed, hinted, reused, or blocked;
- return structured data that callers can translate into their own response format.

It should not emit env.tool responses directly and should not import `search` tool modules or
launcher prompt modules.

`search.open_browser` should:

- build the target URL as it does today;
- resolve the browser endpoint as it does today;
- evaluate the browser page gate before calling `cdp_background_page.py`;
- return a rejection before opening when the limit is reached;
- return a reuse success when the exact target URL is already open;
- include the soft hint after an allowed open crosses or reaches `5/10`.

`chrome_devtools_cockpit_proxy.py` should:

- evaluate the same gate before forwarding `new_page`;
- preserve the existing `background=true` behavior;
- preserve the existing `isolatedContext` rejection behavior;
- block locally without forwarding when the page limit is reached;
- return a local reuse response when the URL is already open;
- append the soft hint to the `new_page` tool response when an allowed open reaches the hint
  threshold.

## Response Contract Details

For `search.open_browser`, hard block should use a structured env.tool rejection with:

```text
code = E_SEARCH_BROWSER_PAGE_LIMIT_REACHED
state_changed = false
durability = none
page_opened = false
browser_page_count = 10
browser_page_limit = 10
retry_guidance = Close or reuse existing browser pages, then retry opening this URL.
```

The response should clearly say no page was opened.

For duplicate target URL reuse:

```text
page_opened = false
page_reused = true
reused_target_id = <target id>
```

This is a no-new-page result. The implementation must keep `state_changed` truthful. If existing
response-contract tests assume every successful `browser_session` action mutates state, adjust the
contract test to distinguish an actual open from a reuse/no-op success instead of lying in the
response.

For `chrome-devtools-cockpit` `new_page`, local tool-error text should use the canonical hard block
text. The proxy response must not forward the blocked call upstream.

## Tests Required

Add focused tests before implementation.

For `search.open_browser`:

- below `5/10`, opens normally and returns no hint;
- when an allowed open reaches `5/10`, opens and returns the canonical soft hint;
- at `10/10`, if the target URL is not open, returns `E_SEARCH_BROWSER_PAGE_LIMIT_REACHED` and does
  not call `Target.createTarget`;
- at `10/10`, if the exact target URL is already open, returns a reuse response and does not call
  `Target.createTarget`;
- if `/json/list` cannot be read, the response should be explicit about browser page-count
  verification failure and must not silently claim the limit was checked.

For `chrome-devtools-cockpit` proxy:

- below `5/10`, `new_page` still forwards with `background=true`;
- when an allowed `new_page` reaches `5/10`, the proxy response includes the canonical soft hint;
- at `10/10`, `new_page` is blocked locally and not forwarded upstream;
- at `10/10`, duplicate URL returns a local reuse response and is not forwarded upstream;
- existing focus-control behavior still holds: `select_page` forces `bringToFront=false`, focus RPCs
  are blocked, and `new_page` with `isolatedContext` is rejected.

Run only focused tests first. Do not run broad browser/launcher suites until any service-starting
test path has clear cleanup, following
`docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`.

## Verification

Minimum verification after implementation:

```text
python3 -m pytest tests/test_search_env_tool.py -q
python3 -m pytest tests/test_browser_cockpit_proxy.py -q
python3 -m pytest tests/test_env_tool_response_contract.py -q
python3 -m pytest tests/test_env_tool_semantic_contract.py -q
```

Also inspect:

```text
git diff --check
git status --short --branch
```

The implementation is not complete unless tests prove:

- soft hint starts at `5/10`;
- hard block starts at `10/10`;
- blocked opens do not create pages;
- duplicate URLs are not opened again;
- `search.open_browser` and `chrome-devtools-cockpit new_page` cannot diverge on page-count rules;
- response text is concise and matches the canonical wording.

## Open Design Notes

Page counting should start simple: count CDP targets where `type == "page"`. Do not add exclusions
for search result pages, login pages, blank pages, or stale pages in this task.

Exact URL reuse is enough for the first pass. Do not normalize URLs beyond what the target URL
builder already produces.

If the browser page list cannot be read, do not guess. The tool response should make the failed
resource check visible instead of silently opening as if the limit had been enforced.
