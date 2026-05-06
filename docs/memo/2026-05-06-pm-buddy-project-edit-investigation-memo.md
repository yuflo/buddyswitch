# PM Buddy Project Edit Investigation Memo

## Context

During product-side acceptance for commit `c191f9841b9cea101eb26026807bfe6b392d978f`
(`rebuild buddy-run persistence flow`), a PM buddy instance received this ordinary
request:

```text
给一款AI日程工具做一个简单的landing page，写一份PRD，然后创建绑定一个track
```

The PM buddy began reading and editing `projects/app`, which is outside the
expected PM role boundary. PM should produce product definition artifacts, create
or bind track state when requested, and hand off implementation or design work to
the appropriate buddy.

## Findings

### 1. The shared project path existed before this commit

The runtime prompt line below existed before `c191f984` and remains present after
it:

```markdown
Use relative `projects/app` from the runtime workspace; launcher projects it to shared project source.
```

This means the incident was not caused by newly exposing `projects/app` in this
commit.

### 2. The commit changed the execution shape from selected skill to buddy run

Before `c191f984`, buddy runtime prompts said to execute a selected native skill,
emit that selected skill's result, and persist with the selected native
`skill_id`.

After `c191f984`, the runtime prompt says:

```markdown
Execute any needed native skills inside this locked buddy session.
Build one buddy run commit with artifacts, state effects, handoff, and contributor audit metadata.
```

This is directionally correct for buddy-run persistence, but it loosened the old
behavioral anchor of "one selected skill owns this run." For a combined request
such as "make a landing page, write a PRD, and create a track," the PM buddy can
now interpret the turn as multiple deliverables inside one session, including a
direct project edit.

### 3. PM-specific role restrictions are not present in the runtime prompt

`framework/contracts/pm.md` explicitly says PM must not implement code:

```markdown
## Must Not Do

- Produce final visual design specs.
- Implement code.
- Expand scope beyond the user request without stating it.
- Emit retired top-level `track_operation` payloads.
```

However, `tools/launcher/assets/buddies/pm/AGENTS.md`, which is what the PM
instance actually receives as workspace `AGENTS.md`, does not include the PM
contract's `Must Do` / `Must Not Do` boundary. It only identifies the active
buddy as `pm`, describes the runtime loop, and exposes shared paths.

### 4. Instance creation is buddy-specific in structure, not fully in behavior

`instance start --buddy <buddy>` does create a buddy-specific instance:

- each instance has its own workspace, home, Codex home, XDG config, and
  `instance.json`;
- launcher copies `tools/launcher/assets/buddies/<buddy>/AGENTS.md` into the
  runtime workspace;
- runtime skills are materialized from manifest membership into
  `.agents/skills/<skill-id>`.

The gap is that the copied buddy `AGENTS.md` files are largely the same template.
They do not currently carry enough buddy-specific role guidance and hard
limitations from `framework/contracts/<buddy>.md`.

### 5. File-system guardrails do not prevent this class of edit

Launcher guardrail hooks block commits, rebases, and pushes from the runtime
workspace. They do not block file edits under `projects/app`.

The runtime projection deliberately maps:

```text
<instance workspace>/projects/app -> <shared root>/project/workspace/projects/app
```

That is appropriate for Dev, and sometimes for Test inspection, but it is too
available for PM unless PM's runtime prompt clearly treats `projects/app` as
read-only context or excludes it from PM work.

## Root Cause

The direct trigger was the `c191f984` shift from selected-skill persistence to
buddy-run persistence. That change removed the old selected-skill behavioral
anchor and made it possible for PM to integrate several perceived deliverables
inside one run.

The deeper root cause is that buddy-specific runtime instructions are incomplete.
The PM instance does not receive PM's role boundary, especially "do not implement
code," even though that boundary exists in `framework/contracts/pm.md`.

The enabling environment factor is that all buddies receive the same
`projects/app` projection guidance, and there is no buddy-specific write guard
for project files.

## Implications

- Buddy-run persistence is not itself the wrong model.
- The old `skill_id` flow was accidentally constraining behavior by forcing a
  selected native skill boundary.
- With buddy-run persistence, role boundaries must move into explicit runtime
  buddy instructions and, where needed, launcher-level write constraints.
- Tests currently verify that buddy prompts are copied and skills are
  materialized, but they do not verify that each buddy prompt contains its
  contract-specific restrictions.

## Recommended Follow-Up

1. Generate or maintain each buddy runtime `AGENTS.md` with explicit
   buddy-specific `Purpose`, `Must Do`, and `Must Not Do` sections from
   `framework/contracts/<buddy>.md`.
2. For PM, Market, Design, and Test, state clearly whether `projects/app` is
   read-only context, inspect-only, or writable. PM should not write it.
3. Add repo or launcher tests that fail if PM runtime `AGENTS.md` omits
   "Implement code" / project-write restrictions.
4. Consider a launcher-level write guard for `projects/app` by active buddy if
   prompt-only restrictions remain too weak for product mode.
