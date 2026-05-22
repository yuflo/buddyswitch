# Dev Source Root And Skill Rebuild Scope

Date: 2026-05-21
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/clean-runtime-env`

## Goal

Make Dev reliably understand and use the runtime-provided product source root without putting concrete directory instructions in AGENTS, without adding a source-write tool, and without weakening BuddySwitch runtime boundaries.

This is a complete task. It covers runtime source-root facts, source write boundary enforcement, AGENTS slimming, Dev skill rebuild, and regression tests. Do not implement only the skill layer or only the sandbox layer.

## Triggering Incident

The dev buddy runtime log showed B repeatedly concluding that product source was missing because the visible product source root contained only `README.md`.

The correct interpretation is:

```text
source root exists; app source/scaffold is absent or README-only
```

It is not:

```text
source link missing
```

That mistake exposed three weaknesses:

- concrete source directory facts were being taught through AGENTS prose;
- Dev had one coarse `implement-task` skill instead of a stable product-engineering skill chain;
- source write boundary expectations were not fully enforced as the main runtime contract.

## Final Decisions From Discussion

### D1. Do Not Put Concrete Source Directory Guidance In AGENTS

AGENTS must stay a short runtime entry file:

- active buddy identity;
- start with context discovery;
- use env tools for runtime objects;
- do not bypass broker/runtime boundaries;
- short output expectation.

AGENTS must not say the concrete project source path or project access value. That information belongs in runtime profile/context and filesystem enforcement.

### D2. Do Not Add A Project Configuration Tool

Do not add `project.configure`, `dev_env.configure`, or any equivalent tool that configures the development directory.

Reason:

- the source root is launcher/runtime-profile owned;
- a tool must not let the model configure or move the project root;
- directory authority should be fixed before the buddy starts.

### D3. Do Not Route All Source Writes Through A Tool

Do not add P0 source write tools such as:

- `project.write_file`;
- `project.apply_patch`;
- `project.delete`;
- `project.mkdir`;
- a generic source filesystem proxy.

Reason:

- that would turn env tools into a source filesystem broker;
- it would duplicate normal Codex file editing, `apply_patch`, formatters, package managers, and build tooling;
- it is a larger platform direction than the current bottleneck requires.

### D4. Source Write Safety Comes From Runtime Filesystem Boundaries

The required contract is:

- Dev can write only the runtime-provided product source root plus safe instance-local home/config/temp roots.
- Dev cannot write workspace runtime files, raw state, buddybox real filesystem paths, or repository/launcher source outside the product source root.
- Non-Dev buddies can read product source but cannot write it.
- The product source root is the only ordinary filesystem place for product code changes.

The runtime profile/contract language must name this boundary clearly. Do not ship a profile field whose name says project-workspace write when the actual permission target is only the product source root. Replace ambiguous permission wording directly rather than layering explanatory prose over it.

This boundary must not over-constrain normal source work inside the product source root. Dev may edit, create, delete, format, scaffold, install package metadata, and update generated lock/config files inside the locked source root when the task scope and local project tooling justify it. The restriction is about the root boundary, not about micromanaging file types inside source.

### D5. Context Discovery May Expose Read-Only Source Facts

The existing `context` tool may expose compact, read-only project/source facts because context discovery is the runtime orientation surface.

Allowed source facts:

- active buddy;
- runtime source path as a relative workspace path;
- canonical source path only when already runtime-visible and needed for boundary clarity;
- access for the active buddy;
- whether active buddy can write source;
- source root state: `missing`, `empty`, `readme_only`, or `has_source`;
- top-level source hints such as package files or README-only status;
- source fact provenance, such as env profile plus instance workspace projection.

Not allowed:

- source write operations;
- arbitrary root selection;
- workflow routing rules;
- business SOP such as "if landing page then scaffold React".

`source_workspace` is a context fact block, not a new tool capability. Its response semantics must be explicit enough that Dev can lock the source root without reading service code:

- `active_buddy`: the buddy bound by the runtime broker.
- `path`: the relative path Dev should use from the runtime workspace.
- `access`: `write` or `read-only` for the active buddy.
- `can_write_source`: boolean derived from profile access, not from AGENTS.
- `state`: source root classification.
- `top_level_entries`: bounded list of names only, never file bodies.
- `source_of_truth`: short provenance string naming env profile and workspace projection.
- `permission_boundary`: states that context is read-only and does not grant or configure write access.

`context.list_sources` should also describe `source_workspace` as a read-only orientation source. `context.get` and `context.summarize` should include the fact block; tool definition `returns`, action descriptions, and effect summaries should mention it.

### D6. Dev Workflows Belong In Dev Skills

Replace the single coarse Dev implementation skill with a small chain of concrete product-engineering skills. Skills should teach how Dev works, but they should consume runtime source facts instead of hardcoding the directory as authority.

## Scope

### P0. Runtime Source Root Enforcement

Required behavior:

- env profile and contract use unambiguous source-root permission language;
- launcher/codex sandbox profile grants Dev write only to the product source root, not to the whole project workspace if that grants non-source paths;
- non-Dev profiles keep product source read-only;
- temp root selection cannot create write access under source root, state root, instance root, or runtime workspace;
- runtime workspace remains read-only except intended instance-local roots;
- source sparse checkout keeps only the product source tree visible in the shared project worktree.

### P0. Context Source Facts

Required behavior:

- `context.summarize` returns compact `source_workspace` facts;
- `context.get` returns the same facts plus any full context sections already available;
- `context.list_sources` describes `source_workspace`;
- the context tool definition describes the field meaning, read-only boundary, provenance, and no-write guarantee;
- facts are derived from runtime profile/instance state, not from AGENTS text;
- source root state distinguishes README-only from missing root;
- no file bodies are included in context summary;
- no source write operation is added.

### P0. AGENTS Slimming

Required behavior:

- remove concrete source path/access wording from all runtime buddy AGENTS templates;
- keep AGENTS short and startup-oriented;
- keep payload-form env client examples only where they are generic runtime entry examples;
- do not move source directory facts into another prose prompt file.

### P0. Dev Skill Rebuild

Create a new Dev skill set:

1. `enter-dev-workspace`
   - triggered before Dev source exploration, implementation, bugfixing, or refactoring;
   - reads context source facts;
   - records the runtime-provided source root as this turn's locked source root;
   - classifies missing/empty/README-only/has-source state.

2. `read-implementation-context`
   - reads track/task/request/artifact context before coding;
   - verifies PM/design/test inputs are real artifacts or direct request context;
   - rejects implementation from memory when required material is unread.

3. `handle-empty-source-root`
   - handles missing/empty/README-only source root;
   - permits scaffold only when the task explicitly asks Dev to create the app/source;
   - otherwise reports a blocker or asks for scope clarification through product channels.

4. `implement-scoped-change`
   - replaces the implementation part of current `implement-task`;
   - edits only under the locked source root;
   - keeps changes local to approved scope;
   - refuses product-direction changes.

5. `debug-regression`
   - starts bugfixes from reproduction and root-cause evidence;
   - prevents symptom patching and broad fallback masking.

6. `select-local-verification`
   - chooses focused verification from changed files and project hints;
   - prefers existing project commands when discoverable;
   - reports blocked verification plainly.

7. `write-implementation-report`
   - writes changed files, behavior, verification, risks, and follow-ups;
   - uses artifact/request/track tools for product-readable reports;
   - never writes reports into source folders as runtime noise.

8. `prepare-review-readiness`
   - summarizes blast radius, main path, changed files, verification evidence, and residual risks for Test/review.

The existing `skill-creator-importer` remains a platform maintenance skill and is not part of the core product implementation chain.

Every new Dev skill must be operational rather than slogan-like. Each skill should include:

- frontmatter with a trigger-only `description`;
- "Use when" and "Do not use when";
- inputs the skill expects;
- concrete steps;
- outputs;
- guardrails;
- verification or stop conditions.

The skills must remain decoupled:

- workflow skills may say which shared tool skill to use, but must not copy payload schemas or operation catalogs;
- source-root skills may lock the runtime source root, but must not claim that a hardcoded path string is the authority;
- implementation/debug/verification/reporting skills may call each other out as prerequisites, but must each solve one stable problem;
- skills should not encode framework-specific defaults such as React, Next.js, Vite, or Tailwind unless those are discovered from the locked source root or explicit task context.

### P0. Manifest And Materialization

Required behavior:

- register the new Dev skills in `buddyswitch/manifest.toml`;
- Dev receives the new product-engineering skill chain;
- remove or retire `implement-task` from Dev routing once replacement skills exist;
- do not remove `skill-creator-importer`;
- materialization tests prove all registered skill paths exist and parse.

### P0. Verification

Required behavior:

- focused sandbox/profile tests pass;
- true sandbox smoke tests prove writable and non-writable paths when the local Codex sandbox is available;
- focused context discovery tests pass;
- runtime skill/manifest consistency tests pass;
- skill content guardrails prove useful sections and scenario coverage, not only keyword presence;
- AGENTS guardrail tests pass;
- full relevant suite passes before claiming completion.

## Explicit Non-Goals

Do not implement:

- a new project/dev-env tool;
- source write/apply-patch/delete tool;
- workflow engine;
- scheduler or daemon;
- general permission framework;
- compatibility layer that keeps old and new Dev skills active for the same trigger;
- prose mirror of runtime profile schema in AGENTS or skills;
- arbitrary source-root selection by user or model;
- framework defaulting inside skills when the project source root does not provide evidence;
- banning ordinary source-root writes such as scaffold files, lockfiles, generated app files, or test fixtures when the scoped implementation legitimately requires them.

## Definition Of Done

The task is done only when:

- concrete source directory/access prose is removed from AGENTS;
- context exposes compact read-only source facts;
- tool catalog/response semantics explain `source_workspace` without requiring source-code inspection;
- env profile/contract permission wording matches source-root enforcement;
- Dev write permission is limited to the product source root and safe instance-local roots;
- non-Dev buddies cannot write product source;
- README-only source root is represented as a distinct state;
- Dev skills form a clear, sufficiently detailed implementation chain and consume runtime source facts;
- `implement-task` no longer acts as the main catch-all Dev implementation skill;
- no new project/source write tool is shipped;
- tests prove behavior from user-visible requirements, not implementation-shaped shortcuts.
