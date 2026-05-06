# Market Buddy Browser-Native Investigation Memo

## Context

During product-side acceptance for commit
`c191f9841b9cea101eb26026807bfe6b392d978f`
(`rebuild buddy-run persistence flow`), a Market buddy instance received a
research request about AI scheduling tools:

```text
针对 AI 日程管理工具，目前的核心用户群体，以及对应的定价策略，再做一次深入的调研，我们想关注和捕捉其中的缺口产品
```

The Market buddy read market native skills, prepared the turn context, and then
used ordinary web search repeatedly instead of opening and using the headed
Chrome browser cockpit. The run later persisted research artifacts.

This memo records the code-level investigation into why this behavior appeared
after `c191f984`.

## Findings

### 1. Browser infrastructure was prepared, but not used

The launcher still starts or reuses an instance-bound Chrome endpoint and
registers the `chrome-devtools-cockpit` MCP server:

- `buddyswitch-codex` calls `buddyswitch_browser_bootstrap` during
  buddy-locked instance start/open.
- `tools/launcher/browser_cockpit.sh` starts Chrome with
  `--remote-debugging-port` and an instance browser profile.
- Runtime Codex config contains `mcp_servers.chrome-devtools-cockpit` with the
  instance browser URL.

On the inspected machine, the Market instance browser ports were reachable, but
the open pages were only Chrome profile/new-tab pages. That supports the
conclusion that browser capability existed while the agent did not drive actual
research pages through the browser.

### 2. Market browser rules exist in contracts and skills

The Market contract requires browser-native research:

- use `chrome-devtools-cockpit`;
- keep discovery `browser-native`;
- search in the browser and continue into real result pages;
- do not use silent search API, snippet, or crawler fallback;
- only allow a user-approved one-off downgrade if browser-native access is
  genuinely blocked.

The `research-scan` and `pmf-recon` skill files also begin with an execution
order that requires visible `chrome-devtools-cockpit` browser discovery before
market research.

Therefore the intended contract is present in source files.

### 3. The runtime Market AGENTS prompt does not carry the Market browser contract

The actual instance workspace receives
`tools/launcher/assets/buddies/market/AGENTS.md` as `AGENTS.md`.

That prompt only describes the generic BuddySwitch loop:

- prepare context;
- let Codex use native skills exposed in `.agents/skills`;
- execute any needed native skills;
- build one buddy run commit;
- persist once.

It does not include the Market contract's browser-native requirements or the
no-silent-degrade rule. As a result, the strongest always-visible runtime prompt
does not force Market to use the browser cockpit.

### 4. `c191f984` removed the old selected-skill persistence anchor

Before `c191f984`, persistence required a selected `skill_id`:

- `persist_skill_result(context, skill_id=..., result=...)` rejected missing or
  invalid skill ids.
- Runtime resolved the selected skill from manifest membership.
- Artifact slot, artifact identity, receipt metadata, and run audit all carried
  the selected skill identity.
- Manifest skill rows contained persistence metadata such as `output_slot` and
  `output_schema`.

After `c191f984`:

- top-level `skill_id` is rejected in buddy run commits;
- skill rows are only `id` and `path`;
- buddy rows define `artifact_kinds`;
- native skills are only optional `contributors.skills` audit metadata;
- artifact, receipt, and run audit ownership are buddy-run based.

This was intentional for buddy-run persistence, but it removed the accidental
runtime pressure to stay anchored to one selected native skill contract.

### 5. The new tests deliberately delete old skill-level constraints

The test plan explicitly requires `persist` to commit without requiring or
accepting a selected `skill_id`, and requires artifact/run/receipt state to have
no canonical `skill_id`.

Current repo consistency tests also forbid old strings such as:

- `persist --skill-id`;
- `persist-skill-result`;
- `selected skill_id`;
- `selected_skill_packet`;
- `prepare_context.skills`;
- `instruction_path`.

This means the old selected-skill boundary cannot be reintroduced casually as a
compatibility path. If stricter behavior is needed now, it must be expressed as
buddy-run era constraints, not by restoring old skill-level ownership.

### 6. Ordinary web access remains available and is not guarded

BuddySwitch Codex config enables network access for the runtime workspace.
There is no code-level guard that forbids ordinary web search for Market, and
`persist` does not validate that evidence came from browser-native page
traversal.

The logged behavior shows the agent self-authorized a downgrade when it said it
would continue if browser-side access was unavailable. That conflicts with the
Market contract, which requires explicit user approval for any browser-native
downgrade.

## Root Cause

The direct trigger was `c191f984` changing persistence from a selected native
skill result into a buddy-level run commit. That change removed the old
selected-skill identity from the persist boundary and loosened the behavioral
anchor that had previously kept the run closer to one skill contract.

The deeper root cause is incomplete runtime contract propagation. Market's
browser-native restrictions exist in `framework/contracts/market.md` and the
Market skill files, but they are not present in the copied runtime
`AGENTS.md`, and they are not enforced by launcher, tool policy, or persist
validation.

The enabling factor is that ordinary network/web search remains available while
browser-native evidence capture has no mandatory preflight, no usage proof, and
no persisted evidence-source validation.

## What Was Not The Primary Cause

- The browser cockpit was not simply missing. The launcher still bootstraps
  Chrome and the `chrome-devtools-cockpit` MCP server.
- The Market skill files were not missing browser guidance. They contain strong
  browser-native instructions.
- `prepare` alone did not cause this; before and after `c191f984`, prepare
  returns context and run envelope rather than a selected skill packet. The
  more important change is the removal of selected `skill_id` from persist and
  durable state.

## Implications

- Buddy-run persistence remains the intended product model, but it requires
  explicit buddy-runtime constraints to replace the old accidental
  selected-skill constraint.
- Market needs a runtime-visible browser contract in the instance `AGENTS.md`
  or an equivalent generated prompt section.
- Prompt-only restrictions may still be insufficient because web search remains
  available and accepted by persist.
- Tests currently prove browser docs and skill files mention the cockpit, but
  they do not prove a Market run actually uses browser-native tooling.

## Recommended Follow-Up

1. Add Market-specific browser-native rules to the runtime Market `AGENTS.md`,
   including no silent downgrade and mandatory user approval for fallback.
2. Add a preflight requirement for Market runs: verify
   `chrome-devtools-cockpit` is reachable and make browser-native discovery the
   first execution step before synthesis.
3. Add a product/runtime test that fails if Market runtime `AGENTS.md` omits
   `chrome-devtools-cockpit`, `browser-native`, and no-silent-degrade wording.
4. Add evidence-source metadata to Market artifacts or run audits, then reject
   Market persists that claim browser-native research without browser evidence
   proof.
5. Decide whether ordinary web search should be disabled or treated as an
   explicitly user-approved downgrade for Market product-mode instances.
