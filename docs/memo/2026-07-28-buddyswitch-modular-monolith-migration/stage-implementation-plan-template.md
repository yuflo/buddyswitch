# Stage Implementation Plan Template

> This file defines the required shape of a stage plan. It is not executable by
> itself. A stage is not READY until every `[REQUIRED: ...]` field has been
> replaced by exact current-source content.

Every generated plan starts with:

```markdown
# [Stage ID and Name] Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` or
> `superpowers:executing-plans` to execute this plan task by task. Follow root
> `AGENTS.md` and `$buddyswitch-testing`.

**Goal:** [one observable stage outcome]

**Architecture:** [two or three sentences naming owner, Public boundary,
composition path, and direct replacement]

**Tech stack:** Python, existing BuddySwitch launcher/runtime contracts,
existing `./buddyswitch-test`
```

## 1. Stage identity

```text
Stage:
Charter:
State:
Source commit:
Source dirty diff:
Owning module/capability:
Stage executor:
Migration lead:
Integration owner:
Plan review date:
```

Every field must contain an exact value before execution.

## 2. Acceptance sentence

Copy the stage charter acceptance sentence exactly. Do not paraphrase it into
a task list.

Then state the consumer path:

```text
consumer action
  -> owning module/capability
    -> host/runtime boundary
      -> observable result
```

## 3. Current-source trace

Name exact:

- semantic owner;
- canonical state and write path;
- public consumers;
- daemon/tool/web/CLI/Role adapters;
- composition entry;
- assets and Skills;
- tests and proof gaps;
- current docs;
- old-path residue IDs.

Every path includes current line references where stable enough for review.

## 4. Scope ledger

| File/path | Class | Why this stage changes it | Final disposition |
|---|---|---|---|
| `[REQUIRED: exact path]` | OWNER / CONSUMER / HOST CONTRACT / COMPOSITION / PROOF / CURRENT DOC | `[REQUIRED: exact reason]` | CREATE / MODIFY / MOVE / DELETE |

No touched file may remain unclassified.

Separately list:

```text
Forbidden files/roots:
Shared files requiring integration-owner approval:
Unrelated dirty files to preserve:
```

## 5. Protected contracts and frozen behavior

List exact consumer-visible behavior:

- command/tool/route name;
- input schema;
- authority;
- success result;
- failure result;
- persisted effect;
- restart/recovery effect;
- cleanup effect.

If no external contract is protected, say:

```text
No internal Python import path is protected; stage uses direct Forward cutover.
```

Do not infer Protected mode.

## 6. Decisions frozen for the stage

Copy only applicable decision IDs from `decision-log.md`.

State:

- final source root;
- Public boundary;
- module/Role identity;
- host-owned contract types;
- state identity;
- test placement;
- composition behavior;
- failure behavior;
- exact old path to remove.

## 7. Accepted pre-READY evidence

Record, do not defer:

| Boundary claim | Hub preflight identity | Result | Remaining private implementation risk |
|---|---|---|---|
| positive required case | `[REQUIRED: exact source-bound evidence]` | PASS | `[REQUIRED: none or exact risk]` |
| negative forbidden case | `[REQUIRED: exact source-bound evidence]` | PASS | `[REQUIRED: none or exact risk]` |
| correspondence/mutation/cleanup | `[REQUIRED: evidence or exact inapplicability]` | PASS / INAPPLICABLE | `[REQUIRED: none or exact risk]` |
| representative final topology | `[REQUIRED: exact fixture and toolchain]` | PASS | `[REQUIRED: none or exact risk]` |

The hub preflight proves the specification and selected mechanism are
coherent. It does not replace the executor's source-bound RED/GREEN. An
unresolved semantic owner, public/foundation contract, state identity or
boundary mechanism is a plan failure, not an executor task.

For every protected consumer interface, add an assertion inventory:

| Observable result | Exact current assertion or hub probe | Can it fail when the terminal loop is broken? | Required write already classified? |
|---|---|---|---|
| success | `[REQUIRED]` | YES | YES / INAPPLICABLE |
| business rejection | `[REQUIRED]` | YES | YES / INAPPLICABLE |
| transport/runtime error | `[REQUIRED]` | YES | YES / INAPPLICABLE |

Do not substitute a test filename, collected-test count or suite GREEN for
this table. Finish the proof-gap audit before freezing the scope ledger.

## 8. Proof map

| Claim | RED or preservation proof | Exact target | Expected initial result |
|---|---|---|---|
| `[REQUIRED: claim]` | `[REQUIRED: test/assertion]` | `[REQUIRED: file/nodeid]` | FAIL for intended reason / PASS baseline |

Use only:

```bash
./buddyswitch-test focused <exact-file-or-nodeid>...
./buddyswitch-test full
```

`full` appears only for a frozen merge/release candidate or an explicitly
required repository-wide gate.

## 9. Task sequence

Each task is a coherent implementation block. Every step is a checkbox and
contains exact files, code/contracts, commands, and expected results.

Required task shape:

````markdown
### Task N: [exact owner-correct outcome]

**Files**

- Create: `exact/path`
- Modify: `exact/path:line`
- Delete: `exact/path`
- Test: `exact/test/path::exact_case`
- Residue: `R-...`

- [ ] **Step 1: Write or select the exact RED**

```python
# complete assertion or contract shape used by this task
```

- [ ] **Step 2: Run the focused proof**

Run:

```bash
./buddyswitch-test focused exact/test/path::exact_case
```

Expected: FAIL for the named current behavior, or PASS as a preservation
baseline.

- [ ] **Step 3: Make the smallest owner-correct implementation**

```python
# complete relevant type/function/assembly shape
```

- [ ] **Step 4: Make the declared runtime current**

If `src/buddyswitch/**` changed, rebuild/install/activate/verify the declared
runtime. If it did not, record exact inapplicability. No
`./buddyswitch-test` command may precede this gate after that source mutation.

- [ ] **Step 5: Run focused GREEN**

Run:

```bash
./buddyswitch-test focused exact/test/path::exact_case affected/test/path
```

Expected: PASS with run identity and clean residual state.

- [ ] **Step 6: Refactor without changing behavior**

Name the exact duplication, old owner, or private assembly being removed.

- [ ] **Step 7: Make the declared runtime current after refactor**

If the refactor changed `src/buddyswitch/**`, repeat
rebuild/install/activate/verify. Otherwise record exact inapplicability.

- [ ] **Step 8: Re-run GREEN**

Record exact public command, run ID, result, duration, and cleanup.

- [ ] **Step 9: Commit the coherent checkpoint**

List exact files to stage. Do not stage unrelated work.
````

The plan must not say:

- “write appropriate tests”;
- “handle edge cases”;
- “move similar files”;
- “update docs as needed”;
- “clean up later”;
- “repeat for other modules.”

## 10. Replacement task

Every stage plan contains a dedicated replacement task with:

- exact old files to delete;
- exact imports/callers to update;
- exact registrations to remove;
- exact tests/assets/docs to move or delete;
- residue assertions;
- proof that old paths are unreadable, unwritable, and undiscoverable.

No implementation task is complete while this task is deferred.

## 11. Current-document task

Name exact `docs/arch`, root guidance, Skill, help, or fixture text that becomes
incorrect when the executable stage cuts over.

Historical memos remain historical. Current guidance must teach only the
stage's accepted live path.

## 12. Verification and acceptance tasks

Select applicable classes:

| Proof class | Exact claim | Exact check | Cleanup |
|---|---|---|---|
| Product | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` |
| Contract | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` |
| Architecture | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` |
| Replacement | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` |
| Operations | `[REQUIRED]` | `[REQUIRED]` | `[REQUIRED]` |

Name omitted proof and risk explicitly.

## 13. Stop and replan conditions

Copy applicable charter conditions and add current-source discoveries that
would change:

- semantic owner;
- Public contract;
- foundation host contract;
- persisted state;
- protected external behavior;
- another stage's scope;
- migration law.

When triggered, stop code work and set the stage to `REPLANNING`.

The packet is permanently retired after a specification contradiction. A
second contradiction at the same boundary forbids another patch-on-patch
implementation plan until architecture alternatives and an end-to-end
preflight are accepted.

## 14. Final handoff

The plan ends with:

```text
Exact accepted source/diff:
Acceptance record:
Closed residue IDs:
Current docs changed:
Remaining risk:
Next stage inputs:
Resources cleaned:
```

An executor never continues into the next stage under the same plan.
