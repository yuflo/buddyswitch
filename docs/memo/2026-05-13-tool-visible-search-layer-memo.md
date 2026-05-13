# Tool-Visible Search Layer Memo

Date: 2026-05-13
Worktree: `dev2258`
Scope: BuddySwitch env tool layer, Codex native web search boundary, browser/search capability visibility, and cross-buddy tool convergence.

## Background

A Market run showed a concrete product problem: the Market buddy was expected to keep research browser-native, but later used Codex host-native search API instead of continuing through the browser cockpit path.

The root cause is not just a Market skill wording issue. BuddySwitch currently has two different tool surfaces:

- BuddySwitch-managed tools exposed through `env.tool`, such as task, track, artifact, context, evidence, handoff, and run.
- Host-native Codex tools, especially `web_search`, which can be exposed directly by `codex-cli` and bypass BuddySwitch's env tool layer.

When both surfaces are visible, the model can select host-native search even when BuddySwitch intends search-like work to be represented, described, and guided by the BuddySwitch runtime environment.

The desired direction is to make BuddySwitch's env layer the primary visible tool layer, not to add more after-the-fact rule checks.

## Task Goal

Build a clearer BuddySwitch tool layer that can actually pull tool usage into a unified, runtime-visible surface.

For this iteration, use search as the vertical slice:

1. Disable or block host-native Codex `web_search` as a bypass path inside BuddySwitch-launched sessions.
2. Expose search/research capability through BuddySwitch `env.tool`.
3. Make the tool layer explicit and actionable: available tools, callable actions, backend capability, permission boundary, unavailable reasons, downgrade path, and next actions should come from tool descriptions and structured feedback.

The goal is not to implement a full search product in one step. The goal is to establish the right control surface and make search one more BuddySwitch-managed tool capability.

## Product Principle

The system should converge on a clear, tool-visible environment:

- Tools should be first-class runtime surfaces.
- Skills should explain when and why to use a tool, but should not be the only enforcement point.
- Prompt text should not be the main mechanism for controlling backend selection.
- Runtime feedback should help the host recover and choose the next action.
- Permission and availability information should be returned as structured tool feedback.
- Buddy-specific workflow choices should live in buddy skills.
- Env profiles should provide machine-readable capability boundaries, not workflow instructions.
- Tool responses should expose runtime facts and next actions, not rely on hidden special cases.

This is an env-layer product direction, not a rules-engine direction.

## Non-Goal

Do not add a separate P2 governance loop for this task.

Specifically, do not make the next step:

- a persist-time provenance audit system;
- a hidden rule that rejects research after the fact;
- another prompt-only constraint;
- a Market-only patch;
- a search-specific workflow router;
- a broad policy engine.

Those may look safer locally, but they keep the architecture fragmented. The current bottleneck is that BuddySwitch does not yet provide a strong enough visible tool layer for search-like work.

## P0: Close The Native Search Bypass

BuddySwitch launcher should ensure Codex native search is not independently available in BuddySwitch product sessions.

Current Codex facts from source inspection:

- `codex-cli --search` maps to `web_search = "live"`.
- Codex config supports `web_search = "disabled" | "cached" | "live"`.
- Tool registry injects native `web_search` when mode is cached or live.
- `cached` still exposes a native search tool; it is not a BuddySwitch-managed tool.

Expected BuddySwitch behavior:

- Launcher-managed Codex config should set `web_search = "disabled"`.
- BuddySwitch should prevent obvious startup escapes such as `--search` and `-c web_search=...` in product sessions.
- The user-facing explanation should point to the BuddySwitch search tool path, not merely say "blocked".

This is not a search policy for Market only. It is a foundation-layer boundary: inside BuddySwitch-launched sessions, search should be mediated by BuddySwitch's tool layer.

## P1: Add A Tool-Visible Search Surface

Add `search` as an `env.tool` resource.

The first version should be intentionally narrow and visible:

```json
{"tool":"search","action":"status","args":{}}
{"tool":"search","action":"request","args":{"query":"...","backend":"browser|search_api","engine":"google|x|reddit|web"}}
{"tool":"search","action":"open_browser","args":{"query":"...","engine":"google|x|reddit|web"}}
```

The exact action names can change if the existing env tool naming style suggests better names. The important part is that the model sees a single BuddySwitch search surface instead of choosing between hidden host capabilities and local browser instructions.

Avoid an implicit `auto` mode in the first slice. The skill or host should choose the intended tool action explicitly, and the tool should respond with capability facts, rejection reasons, or next actions.

## Expected `search.status` Output

`search.status` should answer the host's practical question: "What search/research path am I allowed to use right now?"

Useful fields:

- `native_codex_web_search`: `disabled`
- `active_buddy`
- `available_backends`
- `backend_status.browser.available`
- `backend_status.browser.browser_url`
- `backend_status.search_api.available`
- `backend_status.search_api.reason`
- `capability_boundary`
- `permission_boundary`
- `allowed_next_actions`
- `command_hint`

`search.status` should not encode a Market workflow default. For Market, it should report facts such as browser cockpit availability and search API approval boundary. The Market research skill should choose the browser-native action directly, for example `search.open_browser`, because that is the domain workflow choice.

## Expected `search.request` Behavior

`search.request` should not try to become a full browser automation framework immediately, and it should not silently choose a backend.

First acceptable behavior:

- If backend is `browser`, return an actionable browser instruction payload:
  - browser URL if available;
  - suggested search URL or query URL;
  - required cockpit tool path;
  - next action such as opening or selecting a browser page.
- If backend is `search_api`, return unavailable feedback until a real BuddySwitch-managed provider exists.
- If the capability boundary requires user approval for `search_api`, return structured feedback explaining that approval is required.
- If backend is omitted or unknown, reject with allowed backend values and a command hint.

This keeps behavior concrete and testable without prematurely building a generic search platform.

## Expected `search.open_browser` Behavior

`search.open_browser` is the first real bridge between search intent and browser cockpit execution.

First acceptable behavior:

- Build a search URL from `query` and `engine`.
- Use the instance-bound browser endpoint when available.
- Return structured feedback with:
  - target URL;
  - browser endpoint;
  - whether a page was opened;
  - next action for browser traversal.

If direct page opening is not yet wired, it can initially return the prepared URL and next command/hint. But the tool response should make the browser path explicit and visible.

## Profile Model

Do not make `search` a Market-only tool.

Also do not use `env profile` as a prose description of how Market should research. Profile is a machine-readable capability boundary. It should answer what the buddy is allowed to access, not which workflow step the buddy should prefer.

Add search capability to the shared profile vocabulary only for static boundaries, for example:

```json
"search": {
  "native_codex_web_search": "disabled",
  "browser_cockpit": "required",
  "search_api": "user-approved-only"
}
```

This does not need to be the final shape. The principle is:

- all buddies have a search capability boundary;
- profiles do not decide workflow defaults;
- Market can require browser cockpit capability and restrict search API usage;
- other buddies can be more permissive;
- the env tool returns those facts directly.

## Env Profile, AGENTS.md, Skills, And Tools

These layers should stay separate:

- `env profile`: machine-readable static boundaries used by launcher, prepare, and env tool services.
- instance `AGENTS.md`: host-readable projection of the current buddy runtime, generated from contracts, profile facts, and shared runtime guidance.
- buddy skills: domain workflow choices and concrete tool usage, such as Market choosing browser-native search actions.
- `env.tool`: executable tool surface and structured runtime feedback.

The direction should be:

```text
manifest + env profile + contracts + skills
        -> runtime projection
instance workspace / AGENTS.md
        -> host reads guidance
buddy skill chooses concrete tool action
        -> env.tool executes or returns structured feedback
```

`AGENTS.md` can say that search must go through BuddySwitch tools and that native Codex `web_search` is unavailable. It should not be the only place where this is true.

For search specifically:

- `env profile` records whether browser cockpit and search API are available, disabled, or approval-gated.
- instance `AGENTS.md` tells the host that BuddySwitch search is under `env.tool search`.
- Market research skill directly calls the browser-native search action.
- `env.tool search.status` and `search.open_browser` return the real runtime state and next actions.

## Skill And Tool Description Relationship

Skills should not carry the whole burden of controlling tools.

Expected division:

- `prepare.runtime_context.env_tools.search_manager` describes the tool envelope, operations, payload fields, backend model, and feedback source.
- Search-related skills reference the `search_manager` tool surface.
- Market research skills should directly select the browser-native search action instead of relying on profile text to imply a default.
- Tool feedback should provide next actions when the host asks for a backend that is unavailable or requires approval.

This makes skills lighter and the env layer stronger.

## Why This Is Better Than P2 Governance

Persist-time checks can catch bad outcomes, but they do not create a better operating environment.

The desired system should make the right action obvious before the host acts:

- The native search bypass is unavailable.
- The env tool list includes search.
- `search.status` explains the available path.
- `search.request` gives concrete next steps.
- Rejections include permission boundary and allowed next actions.

This is stronger product design than relying on later rejection, because it improves the host's decision surface.

## Minimal Acceptance Criteria

The first implementation slice is acceptable when:

1. BuddySwitch-launched Codex sessions do not expose native `web_search`.
2. Obvious native search startup escapes are blocked or neutralized.
3. `prepare.runtime_context.env_tools` includes `search_manager`.
4. `env.tool` router accepts `tool = "search"`.
5. `search.status` returns structured capability and backend feedback.
6. Market research skill directly uses the browser-native search tool path for discovery.
7. Env profiles provide capability boundaries only; they do not encode workflow defaults.
8. Non-Market profiles can share the same tool with their own capability boundary.
9. Tool responses include `permission_boundary`, `allowed_next_actions`, and `command_hint` where useful.
10. Existing env tool response contracts remain consistent.

## Verification Direction

Use focused tests before implementation:

- launcher config patch test: managed config contains `web_search = "disabled"`;
- launcher wrapper test: `--search` and `-c web_search=...` cannot start native Codex search in product mode;
- prepare context test: `search_manager` appears in `runtime_context.env_tools`;
- router test: `search.status` dispatches through `env.tool`;
- response contract test: search success and rejection responses include machine-readable feedback;
- profile test: all buddies expose a coherent search capability boundary;
- skill/projection check: Market skill points at the browser-native search tool path, and instance `AGENTS.md` points search usage to BuddySwitch `env.tool`.

Then run the focused test set plus relevant existing env tool contract tests.

## Important Boundaries

Do not change main. Work in `dev2258`.

Do not mix this task with runtime broker v2 refactors unless unavoidable. There are already unrelated worktree changes in `dev2258`; this memo describes the search/tool-visible direction and should remain readable independent of those changes.

Do not implement hidden routing rules that decide research flow for the model. The point is to make tool capabilities visible and feedback-rich enough that a competent host can choose the right action.

## Recommended Next Step

Implement the narrow P0 + P1 vertical slice:

1. Add tests for native search disablement and `search_manager` visibility.
2. Patch launcher-managed config and startup argument handling.
3. Add `scripts/env/tools/search_manager.py` and `scripts/env/services/search.py`.
4. Register `search` in `scripts/env/tools/router.py`.
5. Add `search` CLI support in `scripts/env/client.py`.
6. Add `search_manager` to `turn_runtime._build_env_tools_desc()`.
7. Add profile capability boundary fields and validation.
8. Update the Market research skill and runtime `AGENTS.md` projection so tool choice is explicit at the skill/tool layer.
9. Run focused tests.

The implementation should stay small: status and actionable browser/search feedback first, real search API provider later.
