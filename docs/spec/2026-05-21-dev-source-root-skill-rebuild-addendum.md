# Dev Source Root Skill Rebuild Addendum

Date: 2026-05-21
Applies to:

- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-scope.md`
- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-test-plan.md`
- `docs/spec/2026-05-21-dev-source-root-skill-rebuild-implementation-plan.md`

## Purpose

This addendum tightens the implementation details from the architecture review. It keeps the forward direction:

- no AGENTS source-directory prose;
- no project/dev-env configuration tool;
- no source-write tool;
- source write authority from runtime profile plus sandbox;
- Dev workflow in skills;
- exact tool behavior in tool catalog and runtime responses.

It also prevents two failure modes:

- over-restriction that blocks legitimate work inside the locked source root;
- thin skills or tool descriptions that pass keyword tests but do not guide Dev.

## Source Root Contract Correction

The current profile language can imply that Dev writes the whole project workspace. The actual target is narrower: the product source root inside the shared project worktree.

Implement this as a direct semantic replacement:

```json
"filesystem_capability": {
  "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp", "source-root"],
  "source_root": "write",
  "raw_state": "broker-only"
}
```

For non-Dev buddies:

```json
"filesystem_capability": {
  "host_writable": ["home", "codex-home", "xdg-config", "scratch", "temp"],
  "source_root": "read-only",
  "raw_state": "broker-only"
}
```

`project.path` remains the relative product source path inside the shared project worktree. In the current runtime that value is `projects/app`, but the authority is the validated profile field plus workspace projection, not AGENTS and not skill prose.

### Required Code Meaning

- `project.path`: relative product source path inside the shared project worktree.
- `filesystem_capability.source_root`: active buddy's filesystem access to that product source path.
- `BUDDYSWITCH_PROJECT_WORKSPACE_DIR`: shared project worktree container.
- runtime workspace source projection: symlink or projection from instance workspace to the shared product source root.

The launcher should grant filesystem permission to:

```text
<BUDDYSWITCH_PROJECT_WORKSPACE_DIR>/<project.path>
```

It should not grant write permission to:

```text
<BUDDYSWITCH_PROJECT_WORKSPACE_DIR>
```

### Over-Restriction Guardrail

The root boundary is strict. The file-type policy inside that root is not.

Allowed inside the locked source root when scoped:

- app source files;
- package metadata and lockfiles;
- test files and fixtures;
- generated source artifacts produced by the local project toolchain;
- scaffold files when the request, PM scope, or approved artifact clearly asks Dev to create the app/source;
- format/lint/build outputs only if the project normally writes them inside source and they are necessary.

Not allowed:

- raw runtime object state;
- buddybox real filesystem paths;
- launcher/framework/repo source outside the product source root;
- reports or private runtime notes inside source folders;
- source root movement or reconfiguration by the model.

## Context Tool Semantics

`context` remains a read-only orientation tool. It may expose source facts because source-root orientation is runtime context, not business workflow.

### `source_workspace` Fields

`context.summarize` and `context.get` should include:

```json
"source_workspace": {
  "active_buddy": "dev",
  "path": "projects/app",
  "resolved_path": "/runtime/workspace/projects/app",
  "access": "write",
  "can_write_source": true,
  "state": "readme_only",
  "top_level_entries": ["README.md"],
  "top_level_entries_truncated": false,
  "source_of_truth": "env_profile.project + workspace_projection",
  "permission_boundary": "context is read-only; filesystem writes are enforced by sandbox profile"
}
```

Field meanings:

- `active_buddy`: broker-bound buddy id.
- `path`: relative path from the runtime workspace for ordinary source operations.
- `resolved_path`: optional projection-resolved absolute path. Prefer returning it in `context.get` when useful for debugging; it is not a new authority source.
- `access`: profile-derived source root access for active buddy: `write` or `read-only`.
- `can_write_source`: boolean convenience derived from `access`.
- `state`: one of `missing`, `empty`, `readme_only`, `has_source`.
- `top_level_entries`: bounded top-level entry names only; no recursive tree and no file bodies.
- `top_level_entries_truncated`: true when the entry list hit the limit.
- `source_of_truth`: short provenance string so the host knows this came from runtime profile/projection.
- `permission_boundary`: explicit read-only context boundary and no-write guarantee.

`context.list_sources` should include a descriptor:

```json
"source_workspace": {
  "description": "Runtime product source root facts for the active buddy.",
  "scope": "read-only source orientation",
  "source_of_truth": "env profile project.path/access and instance workspace projection",
  "mutates_product_state": false,
  "grants_write_authority": false,
  "configures_source_root": false
}
```

### Tool Definition Content Requirements

The context tool definition should be rich enough that a host model can use source facts without reading service code.

For `context.get`:

- description says it returns full runtime orientation for the active buddy;
- returns metadata names `source_workspace`;
- effect summary says it reads context only and does not mutate product source, runtime state, or permissions;
- error/rejection guidance says profile resolution failures are explicit and should not be interpreted as a missing source root.

For `context.summarize`:

- description says it returns compact orientation for fast startup;
- returns metadata names `source_workspace`;
- returned fields include path, access, write capability, source state, bounded top-level entries, provenance, and permission boundary;
- description says the top-level entries are hints, not a recursive source tree or file content.

For `context.list_sources`:

- include a `source_workspace` entry;
- state that it is read-only orientation data;
- state that it does not configure, create, lock, or grant the source root;
- name env profile and workspace projection as source of truth.

No context action should be described as a source-write operation. If future tools need write behavior, they must be justified as a separate product decision; this task explicitly does not add one.

### Context Failure And Missing States

Use `state = "missing"` when the profile-declared runtime path does not exist or is not a directory. Do not call this "source link missing" in skill or AGENTS text unless the projection itself is actually broken and verified.

Use `state = "has_source"` for a root that exists and is neither empty nor README-only. This means "there is source-root content to inspect"; it does not guarantee that the app is runnable or that the correct framework has been identified.

If the env profile cannot be loaded or validated, context must not guess from AGENTS, cwd, or a literal path string. Prefer an explicit rejection with `why_blocked`/retry guidance, or a clearly marked unavailable source block if that is the established context-tool response style. Do not encode profile-resolution failure as `state = "missing"`, because `missing` only describes the declared source path after the profile was resolved.

## Dev Skill Chain

The new Dev skills should be small but complete. They are not independent slogans; they form a chain.

```text
enter-dev-workspace
  -> read-implementation-context when implementation depends on track/task/request/artifact material
  -> handle-empty-source-root when state is missing/empty/readme_only
  -> debug-regression for bug/regression work
  -> implement-scoped-change for feature/refactor/code work
  -> select-local-verification after source changes or when planning proof
  -> write-implementation-report for durable product-readable implementation result
  -> prepare-review-readiness when handing focused review/test entry points downstream
```

"Lock the source root" is a host-side turn discipline, not a durable runtime state mutation. It means Dev reads `source_workspace.path`, treats that runtime value as the only source edit root for the current turn, and checks changed files against it before reporting. No new lock file, tool state, or buddybox state is required.

### Shared Skill Shape

Every Dev skill should use this shape:

```markdown
---
name: <skill-id>
description: Use when <trigger condition only, no workflow summary>.
---

# <Title>

## Purpose
...

## Use when
...

## Do not use when
...

## Inputs
...

## Steps
...

## Outputs
...

## Guardrails
...

## Verification Or Stop Conditions
...

## Examples
...

## Counterexamples
...
```

Skills may name small required runtime fields such as `source_workspace.path` or `artifact_id`. They must not copy full payload schemas, full returns schemas, or action catalogs. For exact payloads and response shape, skills must point to `context.get.tool_catalog`, `python3 scripts/turn_runtime.py status`, runtime response fields, or the relevant shared tool skill.

## Skill Content Requirements

### `enter-dev-workspace`

Trigger: Dev starts source exploration, implementation, bug fixing, refactoring, or verification planning.

Purpose:

- establish the runtime-provided source root for the current turn;
- classify source root state before reading or editing product code.

Inputs:

- `context.summarize` response;
- `source_workspace.path`;
- `source_workspace.access`;
- `source_workspace.can_write_source`;
- `source_workspace.state`;
- `source_workspace.top_level_entries`.

Steps:

1. Run compact context discovery.
2. Locate `source_workspace`.
3. If `source_workspace` is missing, run `context.get` once for full context.
4. Lock `source_workspace.path` as the turn source root.
5. Record state as `missing`, `empty`, `readme_only`, or `has_source`.
6. Route to the next skill based on state and task type.

State routing:

| State | Meaning | Next |
| --- | --- | --- |
| `missing` | Runtime-declared source root is absent or not a directory. | Report runtime/source blocker. |
| `empty` | Root exists with no visible entries. | Use `handle-empty-source-root`. |
| `readme_only` | Root exists but app source is absent. | Use `handle-empty-source-root`. |
| `has_source` | Source/application files are present. | Use context/implementation/debug skills. |

Guardrails:

- Do not use AGENTS as source-root authority.
- Do not edit outside the locked source root.
- Do not turn README-only into "source link missing."
- Do not create framework defaults from this skill.

Examples:

- "source_workspace says path=projects/app, access=write, state=has_source" means Dev may inspect and edit under that locked root.

- "AGENTS mentions projects/app, so that is the source root" is invalid.

### `read-implementation-context`

Trigger: implementation depends on track, task, request, artifact, message, PRD, design, or test proof context.

Purpose:

- turn upstream product material into an implementation brief without making product decisions.

Inputs:

- task/request/user prompt;
- track id when present;
- artifact ids and readable artifact bodies;
- design or PM decisions;
- acceptance criteria.

Steps:

1. Identify explicit ids from the request and context summary.
2. Use shared tool skills and env tools to read full bodies for required artifacts.
3. Extract implementation brief:
   - scope;
   - non-goals;
   - acceptance criteria;
   - design states/interactions;
   - API/data constraints;
   - verification expectations;
   - unresolved questions.
4. If material conflicts, record the conflict and ask the owner through product channels.
5. If scope is enough, proceed to source state handling or implementation.

Guardrails:

- Do not claim artifact content was read unless `artifact.get` returned the body.
- Do not implement from memory when the prompt references a real artifact id.
- Do not resolve PM/design contradictions silently in code.

Example:

- A PRD and design artifact agree on CTA behavior, so Dev extracts acceptance criteria and proceeds.

Counterexample:

- A request says "use the latest design" but no artifact/message is read; Dev starts coding from memory.

### `handle-empty-source-root`

Trigger: locked source root state is `missing`, `empty`, or `readme_only`.

Purpose:

- distinguish runtime blockage from legitimate app/source creation.

State handling:

| State | Meaning | Allowed | Not Allowed | Escalate To |
| --- | --- | --- | --- | --- |
| `missing` | Runtime path absent or not a directory. | Report runtime/source-root blocker. | Create random directories outside root. | User/supervisor/runtime owner. |
| `empty` | Root exists with no files. | Scaffold only when direct request, PM scope, or approved artifact clearly asks for source/app creation. | Invent product/framework scope. | PM/user if scope unclear. |
| `readme_only` | Root exists but app source is absent. | Treat as present root; scaffold only with approved source creation scope. | Report "source link missing." | PM/user if scope unclear. |
| `has_source` | Source exists. | Continue to implementation/debug. | Stay in empty-root handling. | None. |

Guardrails:

- "Explicit scope" can come from the user, PM decision, PRD, or approved artifact. It does not need to be the literal phrase "create app."
- Framework selection must come from request, artifact, source hints, or local project constraints.
- If scaffold is allowed, keep all generated source under locked source root.

Example:

- User asks "build the landing page" and the root is README-only; scaffold is allowed if no upstream artifact contradicts it.

Counterexample:

- Root is README-only and task asks only to "fix CTA copy"; Dev invents a full app scaffold.

### `implement-scoped-change`

Trigger: Dev has a locked source root, enough implementation context, and scoped feature/refactor work.

Purpose:

- make the smallest source change that implements approved behavior.

Preconditions:

- locked source root exists;
- source state is `has_source`, or scaffold is allowed by `handle-empty-source-root`;
- implementation context is read when required.

Steps:

1. Map requested behavior to source paths.
2. Identify local patterns and project commands.
3. Write or select a failing test first when practical for changed behavior.
4. Implement the smallest direct change.
5. Keep refactors local to the behavior being changed.
6. Flag architecture changes explicitly when they are unavoidable.
7. Record changed files and rationale for the report.

Guardrails:

- Do not change product scope silently.
- Do not edit outside locked source root.
- Do not use Test buddy as a substitute for Dev self-verification.
- Do not introduce platform abstractions unless repeated evidence in the task requires them.

Example:

- Update one component and one focused test to implement an approved CTA change.

Counterexample:

- Replace routing/framework structure because it feels cleaner while implementing a copy change.

### `debug-regression`

Trigger: task is a bug, failing check, or regression.

Purpose:

- fix root cause with evidence rather than symptom patches.

Steps:

1. Reproduce the failure or identify why reproduction is blocked.
2. Localize the failing behavior and likely root cause.
3. Add or select the smallest regression proof when practical.
4. Patch the root cause.
5. Re-run focused verification.
6. Record residual risk when reproduction or regression proof is incomplete.

Order guardrail:

- Reproduction/root cause must come before patching unless the task is an obvious typo or missing import and the verification path is clear.

Example:

- A test fails on form submit; Dev reproduces, finds validation state reset, adds regression test, patches state handling.

Counterexample:

- Add a broad fallback that hides the error without explaining why submit failed.

### `select-local-verification`

Trigger: Dev needs to choose or report verification for source work.

Purpose:

- select proof that matches the changed behavior and local project.

Selection matrix:

| Change | Preferred Proof |
| --- | --- |
| unit logic | focused unit test |
| UI interaction | component/e2e/manual screenshot as locally available |
| build/config/package | typecheck/lint/build/install command |
| bug fix | reproduction or regression test |
| scaffold/new app | install/build/smoke main path |
| docs/report only | markdown/static validation if available |

Steps:

1. Inspect package files, scripts, test config, and changed files.
2. Choose the shortest meaningful check.
3. Run it if possible.
4. If blocked, record exact command, error, and missing prerequisite.
5. Decide whether a broader check is needed due to blast radius.

Guardrails:

- Do not claim success from stale output.
- Do not run huge suites by default when a focused proof is enough.
- Do not skip all verification when a cheap local proof exists.

Example:

- Change a React component and run the closest component test plus build if routing changed.

Counterexample:

- Say "not tested" without checking package scripts or project hints.

### `write-implementation-report`

Trigger: Dev needs a durable product-readable implementation result.

Purpose:

- publish what changed, how it was verified, and what remains risky.

Required report sections:

- task summary;
- implemented behavior;
- acceptance/design traceability;
- changed files with why each matters;
- verification commands and results;
- known risks;
- unverified areas;
- follow-ups;
- artifact/request/track refs when used.

Steps:

1. Collect changed files under locked source root.
2. Summarize implemented behavior in product terms.
3. Map behavior to acceptance/design inputs when available.
4. Include fresh verification evidence or blocked verification reason.
5. Create product-readable durable report through artifact/request/track routes when requested or required by workflow.

Guardrails:

- Do not write implementation reports into source folders.
- Do not omit known limitations.
- Do not mark ready without verification evidence or an explicit blocked reason.

Example:

- Report names `src/App.tsx` because it implements hero CTA behavior and `src/App.test.tsx` because it proves CTA routing.

Counterexample:

- Report says "updated files and tests pass" without file names, behavior, command, or output.

### `prepare-review-readiness`

Trigger: Dev needs to hand work to Test/review or summarize review entry points.

Purpose:

- give Test/reviewer a focused inspection map, not a second implementation report.

Inputs:

- implementation report or local changed-file summary;
- verification output;
- known risks;
- acceptance/design criteria.

Steps:

1. Name the main path under review.
2. Identify blast radius and hotspots.
3. List changed files grouped by behavior area.
4. Provide verification evidence already run.
5. Suggest test focus and edge cases.
6. List open questions or residual risk.

Boundary from `write-implementation-report`:

- `write-implementation-report` is durable product-readable result.
- `prepare-review-readiness` is a downstream review/test entry map. It can reference the report, but should not duplicate full report content.

Example:

- "Test should focus on hero CTA click path and responsive layout because only landing-page files changed."

Counterexample:

- A second full report that repeats all implementation notes but gives Test no focused risk map.

## Test Guardrails For Skill Quality

Use tests that are semantic enough to catch weak skills but not so prescriptive that they freeze prose.

Recommended checks:

- parse markdown headings and require non-empty operational sections;
- check section-local content, not whole-file keyword hits;
- verify state tables or equivalent state handling for empty source root;
- verify order-sensitive terms for debugging: reproduce/root cause before patch;
- verify report headings or equivalent fields for changed files, behavior, verification, risks, follow-ups;
- verify examples and counterexamples exist for judgment-heavy skills;
- verify skills reference runtime discovery and shared tool skills for exact tool details;
- forbid full schema copies, not short field references.

Avoid:

- requiring exact paragraph text;
- banning all mentions of runtime response fields;
- requiring a specific frontend framework;
- requiring scaffold for every README-only case;
- forbidding legitimate generated source files inside the locked source root.
