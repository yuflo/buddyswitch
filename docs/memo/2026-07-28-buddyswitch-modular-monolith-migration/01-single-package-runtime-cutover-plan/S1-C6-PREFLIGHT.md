# S1 C6 Evidence-Backed Preflight

> Evidence ID: `C6P-68e1272-20260729`
> Source: `S1-C6-SOURCE-SNAPSHOT.md`
> Result: DESIGN FEASIBLE

## 1. Bottleneck and observable claim

The installed runtime cutover is accepted through C5, but current root and
architecture guidance still teaches deleted implementation paths. S1 cannot
be accepted while the retired model remains discoverable.

Observable acceptance:

> A developer reading any current BuddySwitch guidance reaches only existing
> installed-package source owners, and a focused architecture test rejects a
> reintroduced retired path before final acceptance.

## 2. Alternatives evaluated

### A. Edit the five documents only

Rejected. It fixes the present text but leaves the same drift class
undetectable.

### B. Add a generalized document schema, linter or generated-doc pipeline

Rejected. C6 has one concrete topology rule. A new framework would duplicate
ownership and expand final-stage scope.

### C. Update exact documents and extend the existing package contract

Selected. One local test scans current guidance and asserts exact current
owners. This is the smallest enforceable owner for recurring architecture
drift.

## 3. Current-source trace

The hub scanned root guidance, all `docs/arch`, every packaged Role AGENTS,
every packaged Skill, production source, public wrappers and tests.

Results:

```text
old-root files or symlinks:
0

production src retired loader/path matches:
0

Role AGENTS retired path matches:
0

packaged Skill retired path matches:
0

current root/docs stale path occurrences:
19

historical memo matches:
allowed historical record

test matches:
negative guards or environment isolation, classified in the scope manifest
```

The exact 19 occurrences and all valid exceptions are frozen in
`S1-C6-SCOPE-MANIFEST.md`.

## 4. Required-target proof

Every selected replacement target exists as a regular tracked file:

```text
src/buddyswitch/catalog/manifest.toml
src/buddyswitch/env/domain/demand_sys.py
src/buddyswitch/env/repos/demands.py
src/buddyswitch/env/domain/task_sys.py
src/buddyswitch/launcher/task_goal_handler.py
src/buddyswitch/launcher/instance_daemon.py
src/buddyswitch/env/tool_runtime/definition.py
src/buddyswitch/env/tool_runtime/context.py
src/buddyswitch/env/tool_runtime/results.py
src/buddyswitch/env/tool_runtime/registry.py
src/buddyswitch/runtime_kernel/protocol.py
src/buddyswitch/runtime_kernel/dispatcher.py
src/buddyswitch/contracts/prepare-turn-context.json
```

All five current Role contract markdown files and all five Role bootstrap
AGENTS files also exist below the package source.

No replacement names a future S2–S6 module boundary. C6 documents the current
S1 truth only.

## 5. Preservation and runtime evidence

Focused pre-mutation architecture proof:

```text
run ID:
978f3133b7dc4a689527ebc0e4262187

result:
29 passed, 59 subtests

cleanup:
clean
```

Runtime verification:

```text
kind:
runtime.verify

ok:
true

source_digest:
0240a6d6897a96fc2538f8b883eee4a48f5830c2deb9928e4d9ccaf44809445f

distribution_digest:
02344c6d8e7edd0489cf02f69a28c991fc7364d833f1c1c72f04348a2505f0d7
```

Accepted C2–C5 evidence already proves clean build/install, exact
source/distribution correspondence, public and child-process provenance,
code-free Actor projection, representative Actor lifecycle, Web/IM/Browser/
Daemon consumers and cleanup. C6 changes no executable package input, so this
evidence remains source-bound. The frozen `full` run will independently
exercise every repository tier after the document/test candidate freezes.

## 6. Positive, negative and adversarial judgment

Positive case:

- every proposed current path exists;
- the selected existing test tier can read all current guidance;
- current architecture tests are green before mutation.

Negative case:

- the selected future test sees all 19 known stale occurrences;
- it scans Role/Skill guidance too, so a later old-path regression there is
  caught;
- old physical roots are already absent.

Most plausible adversarial case:

- a global scan sees `PYTHONPATH`, `buddyswitch/skills/**` or an old path in a
  negative test and misclassifies it as live residue.

The manifest prevents that false simplification by classifying matches by
consumer meaning. Acceptance requires zero retired terms only in current
guidance and production loading paths, not zero historical/negative text
across the repository.

## 7. READY judgment

Remaining work contains only:

- one private test implementation matching an exact specified contract;
- five exact current-document edits;
- focused GREEN, one frozen full run and cleanup/reporting.

No semantic owner, public/foundation contract, state identity, package
mechanism, compatibility decision or file-selection judgment remains for the
executor. C6 may proceed to Goal Packet READY review.
