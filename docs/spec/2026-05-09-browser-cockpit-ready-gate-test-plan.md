# Browser Cockpit Ready Gate Test Plan

**Goal:** Verify from functional requirements that a launcher-managed buddy instance gives codex-cli a browser cockpit that is already usable by `chrome-devtools-cockpit`, without host-side browser diagnosis or prompt workarounds.

**Testing principle:** Tests must be requirement-driven. They should validate public commands, broker outputs, CDP-visible browser state, Codex launch ordering, and user-visible failure behavior. They must not assert private helper branch names, copied implementation prose, or artificial markers that could pass while the browser remains unusable.

---

## Functional Requirements

FR1. A fresh browser-required buddy instance must not open codex-cli until browser cockpit readiness is true.

FR2. Browser readiness means a Chrome DevTools endpoint is reachable and has at least one MCP-usable page target.

FR3. A browser whose only page is a Chrome initialization, sign-in, welcome, or other filtered `chrome://` page is not ready.

FR4. New Chrome launches must avoid first-run UI and open a normal browser page by default.

FR5. If an endpoint exists but has no usable page, launcher/runtime must create `about:blank` before declaring readiness.

FR6. If no usable page can be created, browser-required buddies fail closed before codex-cli launch.

FR7. `instance open` must enforce the same ready page gate as `instance start`.

FR8. `browser-cockpit-preflight` evidence must be issued only after browser ready page is true.

FR9. Browser preflight failure must return structured feedback that tells the host the runtime boundary and launcher-level recovery command, without requiring browser internals.

FR10. Browser-available buddies may continue without a browser only according to their env profile, but any reported ready browser must satisfy the same ready page definition.

FR11. The fix must not add business-specific browser debugging guidance to runtime `AGENTS.md` or market skill prompts.

FR12. The rebuild assumption means no old-instance migration or compatibility transition is required.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
|---|---|---|
| FR1, FR6 | TG-01 Start Gate | fake codex is not invoked until browser ready page succeeds |
| FR2, FR3, FR5 | TG-02 Ready Page Semantics | endpoint-only and intro-only states are not treated as ready |
| FR4 | TG-03 Chrome Launch Contract | fake Chrome records first-run suppression flags and `about:blank` |
| FR7 | TG-04 Open Gate | existing instance open repairs or blocks before codex launch |
| FR8, FR9 | TG-05 Broker Evidence Gate | token issuance requires usable page and failures are structured |
| FR10 | TG-06 Browser-Available Profiles | optional-browser buddies do not falsely report endpoint-only readiness |
| FR11, FR12 | TG-07 Drift And Residue Guards | prompt assets and docs do not move browser debugging to host text |
| FR1-FR12 | TG-08 Manual Rebuild Flow | fresh market instance completes browser-native research without `No page selected` |

---

## Test Harness Requirements

Use public entry points wherever possible:

- `./buddyswitch-codex env browser ensure --instance <instance-id>`
- `./buddyswitch-codex env browser status --instance <instance-id>`
- `./buddyswitch-codex instance start --buddy <buddy>`
- `./buddyswitch-codex instance open <instance-id>`
- `scripts/browser_evidence.py issue --mode browser-cockpit-preflight`
- `scripts/runtime_kernel.broker.dispatch_runtime_request` through existing runtime test helpers

Use a CDP test double rather than testing private shell helpers. The test double should model browser-observable behavior:

- `GET /json/version` can succeed or fail.
- `GET /json/list` can return empty pages, `chrome://intro`, `about:blank`, or normal http(s) pages.
- `PUT /json/new?about:blank` can create a page or fail.
- `GET /json/new?about:blank` should not be accepted as the successful creation path.

The fake Chrome binary may record its argv and start or notify the CDP test double. Tests should prove behavior through public CLI results and recorded process calls, not direct helper invocation.

## TG-01 Start Gate

**Purpose:** Prove a browser-required buddy cannot expose codex-cli before browser ready page is true.

**Primary files:**

- `tests/test_buddyswitch_launcher.py`
- `tests/test_browser_cockpit_launcher.py`

**Scenarios:**

1. Fresh market start with ready page succeeds
   - Setup: fake Chrome starts a CDP endpoint whose `/json/version` succeeds and whose `/json/list` includes `about:blank`.
   - Action: run `instance start --buddy market -- debug prompt-input "browser gate smoke"`.
   - Expected:
     - command exits 0
     - fake codex is invoked
     - recorded codex environment contains `BUDDYSWITCH_ACTIVE_BUDDY=market`
     - browser port recorded in instance JSON matches MCP config

2. Fresh market start with endpoint-only browser blocks codex
   - Setup: `/json/version` succeeds, `/json/list` is empty, and `PUT /json/new?about:blank` fails.
   - Action: run `instance start --buddy market -- debug prompt-input "browser gate smoke"`.
   - Expected:
     - command exits non-zero
     - fake codex capture file does not exist
     - stderr names browser readiness, not a generic Codex launch failure
     - instance is not left active

3. Fresh market start with intro-only browser repairs before codex
   - Setup: first `/json/list` returns one `type=page` entry with `url=chrome://intro/`; `PUT /json/new?about:blank` succeeds; next `/json/list` returns `about:blank`.
   - Action: run `instance start --buddy market -- debug prompt-input "browser gate smoke"`.
   - Expected:
     - command exits 0
     - fake codex is invoked only after the test double observed `PUT /json/new?about:blank`
     - no downgrade prompt or user approval is requested

**Anti-cheat guard:**

- Do not pass by touching a ready marker without modeling `/json/list`.
- Do not assert private shell function names.
- Do not allow fake codex invocation when the CDP test double never reported a usable page.

## TG-02 Ready Page Semantics

**Purpose:** Prove the readiness contract is page usability, not endpoint liveness.

**Primary file:** `tests/test_browser_cockpit_launcher.py`

**Scenarios:**

1. `/json/version` success alone is not ready
   - Setup: CDP endpoint returns version but `/json/list` returns `[]`.
   - Action: run `env browser status --instance <id>`.
   - Expected: status exits non-zero or reports not ready.

2. filtered Chrome pages are not ready
   - Setup: `/json/list` returns only pages with URLs `chrome://intro/`, `chrome://signin/`, `chrome-untrusted://blocked`, and `devtools://devtools/bundled/inspector.html`.
   - Action: run `env browser ensure --instance <id>` with page creation disabled.
   - Expected: ensure fails for browser-required mode or strict ensure.

3. normal pages are ready
   - Setup: `/json/list` returns `about:blank`.
   - Action: run `env browser status --instance <id>`.
   - Expected: status succeeds and identifies the browser as ready.

4. http(s) pages are ready
   - Setup: `/json/list` returns a page with `https://example.com/`.
   - Action: run `env browser status --instance <id>`.
   - Expected: status succeeds.

**Anti-cheat guard:**

- The test should vary page URLs so implementation cannot special-case only one exact fixture string.
- Assertions should be about ready/not-ready behavior, not the internal parser implementation.

## TG-03 Chrome Launch Contract

**Purpose:** Prove newly created instance browsers start in a normal page and do not show first-run UI.

**Primary file:** `tests/test_browser_cockpit_launcher.py`

**Scenarios:**

1. launch argv includes first-run suppression
   - Setup: fake Chrome records argv.
   - Action: run `env browser ensure --instance <id>` with no existing endpoint.
   - Expected argv contains:
     - `--remote-debugging-port=<port>`
     - `--user-data-dir=<instance browser profile>`
     - `--no-first-run`
     - `--no-default-browser-check`
     - final URL argument `about:blank`

2. launch waits for ready page, not only endpoint
   - Setup: fake Chrome starts an endpoint that initially exposes version only, then exposes `about:blank`.
   - Action: run `env browser ensure --instance <id>`.
   - Expected: ensure returns only after `about:blank` appears in `/json/list`.

**Anti-cheat guard:**

- Test must inspect recorded argv from the process invocation.
- Test must model delayed page readiness, not only process start.

## TG-04 Open Gate

**Purpose:** Prove existing inactive instances cannot be reopened into a bad browser/MCP state.

**Primary file:** `tests/test_buddyswitch_launcher.py`

**Scenarios:**

1. open existing instance with ready page succeeds
   - Setup: instance JSON has a browser port; CDP test double reports `about:blank`.
   - Action: run `instance open <id> -- debug prompt-input "continue"`.
   - Expected: fake codex runs and MCP config points to the stored browser port.

2. open existing instance with intro-only endpoint repairs before codex
   - Setup: stored port endpoint returns `chrome://intro/`, then accepts `PUT /json/new?about:blank`.
   - Action: run `instance open <id> -- debug prompt-input "continue"`.
   - Expected: fake codex runs only after `about:blank` is visible.

3. open existing market instance with unrepairable endpoint blocks codex
   - Setup: stored port endpoint has no usable page and refuses page creation.
   - Action: run `instance open <id> -- debug prompt-input "continue"`.
   - Expected: non-zero exit, no fake codex invocation, instance is not marked active.

**Anti-cheat guard:**

- Do not rely on deleting the instance to pass. The scenario is about reusing an inactive instance created under the new contract.
- Do not skip MCP config assertions; open must still point `chrome-devtools-cockpit` at the active instance port.

## TG-05 Broker Evidence Gate

**Purpose:** Prove market evidence tokens represent a usable browser, not a live port.

**Primary files:**

- `tests/test_market_browser_evidence.py`
- `tests/test_runtime_tool_feedback.py`
- `tests/test_turn_integration.py`

**Scenarios:**

1. ready browser gets token
   - Setup: market context matches active instance; CDP endpoint returns version and `about:blank`.
   - Action: issue `browser-cockpit-preflight`.
   - Expected:
     - response `ok is true`
     - `tool_evidence.browser_cockpit_token` exists
     - evidence record includes browser URL and run scope

2. endpoint-only browser does not get token
   - Setup: `/json/version` succeeds, `/json/list` empty, page creation fails.
   - Action: issue `browser-cockpit-preflight`.
   - Expected:
     - response is an error
     - no token file is written
     - feedback includes browser-ready boundary and launcher recovery command

3. intro-only browser can be repaired before token
   - Setup: `/json/list` initially returns `chrome://intro/`, `PUT /json/new?about:blank` succeeds, second `/json/list` returns `about:blank`.
   - Action: issue `browser-cockpit-preflight`.
   - Expected:
     - token is issued only after repair
     - test double records a PUT, not a GET, to `/json/new?about:blank`

4. wrong instance still fails before browser repair
   - Setup: context does not match active instance.
   - Action: issue `browser-cockpit-preflight`.
   - Expected:
     - active-instance boundary error
     - no browser CDP calls are made

**Anti-cheat guard:**

- Do not issue handwritten token strings.
- Do not assert exact human prose. Assert structured fields and absence or presence of token files.
- Do not bypass the broker by writing evidence token JSON directly.

## TG-06 Browser-Available Profiles

**Purpose:** Preserve env profile semantics without allowing false readiness.

**Primary file:** `tests/test_buddyswitch_launcher.py`

**Scenarios:**

1. browser-available buddy may continue when browser cannot launch
   - Setup: use a non-market buddy with `browser_cockpit=available`; Chrome binary fails.
   - Action: run `instance start --buddy pm -- debug prompt-input "draft"`.
   - Expected:
     - fake codex may run
     - stderr includes warning that browser cockpit is unavailable
     - no browser-ready success message is printed

2. browser-available buddy with endpoint-only browser does not claim ready
   - Setup: `/json/version` succeeds, `/json/list` empty, repair fails.
   - Action: run `instance start --buddy pm -- debug prompt-input "draft"`.
   - Expected:
     - fake codex may run because browser is optional
     - output does not claim browser is ready
     - MCP setup is not treated as ready if page readiness failed

**Anti-cheat guard:**

- This group must not weaken Market required behavior.
- Optional-browser continuation must be explicitly tied to env profile, not to generic best effort.

## TG-07 Drift And Residue Guards

**Purpose:** Prove the fix remains in launcher/runtime surfaces and does not drift into prompt instructions or compatibility baggage.

**Primary file:** `tests/test_repo_consistency.py`

**Scenarios:**

1. no prompt-based browser diagnosis
   - Scan `tools/launcher/assets/buddies/*/AGENTS.md` and `buddyswitch/skills/market/*/SKILL.md`.
   - Expected: no instructions telling the host to handle `chrome://intro`, `PUT /json/new`, `No page selected`, or first-run Chrome.

2. docs use ready page contract
   - Scan public browser docs and launcher help.
   - Expected: no public statement says `/json/version` or endpoint reachability alone is enough for browser readiness.

3. no old-instance compatibility path
   - Scan launcher code and docs for compatibility marker names or migration wording introduced by this fix.
   - Expected: no old-profile migration or transition marker is present.

**Anti-cheat guard:**

- Text scans are secondary drift guards. They cannot replace functional tests in TG-01 through TG-06.

## TG-08 Manual Rebuild Flow

**Purpose:** Prove the user-facing rebuilt instance experience works end to end.

**Setup:**

- Close active BuddySwitch Codex and Chrome sessions.
- Delete existing BuddySwitch instances before the test.
- Use the `dev0210` worktree.

**Scenario: Fresh market research browser-native flow**

1. Run:

```bash
./buddyswitch-codex instance start --buddy market
```

2. Before typing a task into codex-cli, observe Chrome:
   - Expected: Chrome shows a normal browser window, with `about:blank` acceptable.
   - Not acceptable: Chrome first-run intro, login-only intro, or a window without normal browser controls.

3. Enter a market research task requiring browser-native discovery.

4. Expected execution:
   - `prepare` succeeds.
   - `browser_evidence issue --mode browser-cockpit-preflight` succeeds.
   - `chrome-devtools-cockpit` can create or navigate pages.
   - No `Error: No page selected` appears.
   - No request for ordinary web fallback appears.
   - final persist includes broker-issued browser evidence.

5. Failure capture if the scenario fails:
   - Save launcher stdout/stderr.
   - Save instance `browser/chrome.log`.
   - Save `/json/version` and `/json/list` outputs.
   - Save the codex-cli log lines around the first browser tool call.

**Anti-cheat guard:**

- Manual success requires actual browser-native navigation, not only token issuance.
- Do not approve a web-search downgrade during this verification.

## Required Automated Commands

Targeted during implementation:

```bash
python3 -m unittest tests.test_browser_cockpit_launcher tests.test_buddyswitch_launcher
python3 -m unittest tests.test_market_browser_evidence tests.test_runtime_tool_feedback tests.test_turn_integration
python3 -m unittest tests.test_repo_consistency
```

Final:

```bash
python3 -m unittest discover -s tests
```

## Pass Criteria

The test plan passes only when:

- browser-required `start` and `open` cannot launch codex-cli with endpoint-only or intro-only browser state
- intro-only state is repaired by creating `about:blank`
- Chrome launch suppresses first-run UI and opens a normal page
- market preflight evidence cannot be issued for endpoint-only state
- failures return structured runtime feedback instead of asking codex-cli to infer browser internals
- prompt assets remain free of browser-debugging instructions
- fresh market manual flow reaches browser-native search without `No page selected`
