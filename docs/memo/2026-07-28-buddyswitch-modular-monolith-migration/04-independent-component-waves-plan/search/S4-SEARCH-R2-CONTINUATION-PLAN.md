# S4 Search R2 Continuation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: use
> `superpowers:executing-plans` and `$buddyswitch-testing`.

**Goal:** Prove and, only when evidence requires it, repair the preserved
Search cutover candidate without replaying its implementation.

**Architecture:** R2 resumes from the R1 candidate at focused verification.
The hub fixes the acceptance boundary; the executor owns current target
discovery, command construction and owner-correct repair inside the existing
manifest.

**Tech Stack:** Python 3.13, BuddySwitch installed runtime, the public
`./buddyswitch-test` runner, Git source identities.

---

## 1. Fixed outcome and boundary

Acceptance remains:

> Search is physically aggregated under one capability root, selected exactly
> once by application composition through the existing Tool contribution,
> preserves its non-opening URL-planning behavior, and leaves no Search
> implementation or Search-specific placeholder in the generic Tool host.

Protected contracts remain those in `S4-SEARCH-IMPLEMENTATION-PLAN.md` §2.
Allowed writes remain exactly those classified by
`S4-SEARCH-OWNER-CONSUMER-MANIFEST.md`.

R2 does not authorize a new architecture, another S4 lane, a Public service,
Browser action, compatibility path, registry/host contract change, plugin,
bus, DI container or service locator.

## 2. Checkpoint R2.0 — Consume the preserved candidate

- [ ] Confirm the hub-supplied preparation commit.
- [ ] Confirm the tracked candidate patch is
      `144a55b06bf89be3b2850baca89976dbeb61bf6ba3154a9467f5f87bbefbe059`.
- [ ] Confirm the index is empty and the 13-file untracked candidate manifest
      is `2f76f0d1c69a1289d87e8172859a6808344e935ae45b431c0877be30cd0641b1`.
- [ ] Confirm no unclassified candidate path exists.
- [ ] Confirm the installed runtime still corresponds to the candidate. If
      correspondence has changed, reprovision through the declared PEP 517
      path before public proof.
- [ ] Record R1 run `69e82249c86343c19bf4bf792b2bb151`
      as a diagnosed no-collection signal caused by the invalid parent
      directory. Do not hide or rerun that command.

Identity mismatch or an unclassified write stops. A stale installed runtime is
an execution prerequisite to repair, not a Search redesign.

## 3. Checkpoint R2.1 — Direct and affected focused proof

The executor performs dynamic target discovery from the complete current diff,
changed tests, live references and runner contract, following
`$buddyswitch-testing`.

The direct claim must cover:

- the two co-located Search integration tests;
- Search physical ownership and old-path absence;
- one explicit application contribution and no discovery duplicate;
- removal of `BrowserAccess.request`;
- current package and repository guidance/boundaries;
- shared Tool response behavior affected by Search relocation.

The known valid co-located directory target is:

```text
src/buddyswitch/modules/search/tests/integration
```

It replaces the rejected parent-directory spelling; it is not permission to
omit other changed direct tests.

The affected claim must additionally cover:

- application Tool registry and generic env-tool response behavior;
- Tool active-Task gate and semantic/schema contracts;
- runtime and native-MCP projections;
- package independence, router, distribution installation and CLI Search
  behavior;
- unchanged Demand/Task and Daemon order where the shared proofs changed.

The executor owns exact file/node targets and compatible grouping. Before
running, inspect `tests/runner.py` target semantics. If a suggested target is
mechanically invalid and the repository proves one equivalent with unchanged
proof breadth, correct it and record:

```text
original instruction:
repository/runner authority:
replacement:
why the claim and breadth are unchanged:
```

Every failure, timeout, flake, no-test or cleanup signal remains evidence.
Diagnose it before rerun. Repair an owning defect without replanning only when
every write is already classified and the acceptance boundary is unchanged.
After any `src/buddyswitch/**` repair, reprovision and verify before another
public-runner command.

## 4. Checkpoint R2.2 — Replacement and operations audit

- [ ] Prove retired checkout and installed Search paths are absent.
- [ ] Prove module-local tests are excluded from the installed wheel.
- [ ] Prove Search imports only allowed public/runtime surfaces.
- [ ] Prove generic hosts import no Search private module.
- [ ] Prove exactly one Search Tool and one selected Search module.
- [ ] Prove no current guidance teaches the retired owner path.
- [ ] Confirm `git diff --check`.
- [ ] Confirm no attributable process, socket, lock, test root, instance,
      Browser or hidden environment mutation remains.

These are acceptance claims. The executor chooses the shortest repository
proof that detects each claim; do not invent a second test entry or evidence
framework.

## 5. Checkpoint R2.3 — Frozen FINAL

When direct and affected proof is GREEN and cleanup is clean:

- [ ] Freeze HEAD, tracked/index/untracked and activation identities.
- [ ] Run `./buddyswitch-test full` once on that frozen candidate.
- [ ] Preserve the complete result and cleanup identity.

A FINAL failure is evidence, not an automatic coordination stop. Diagnose it.
If its owner and every required write are already classified, repair the
owner, run the exact regression and affected focused proof, reprovision when
package source changed, freeze a new candidate and run FINAL once for that
new candidate. Never blind-rerun an unchanged candidate.

Stop when the cause is unexplained, requires unclassified or cross-lane
writes, changes a protected contract/accepted mechanism, needs an undeclared
environment mutation, or repeats without an owning diagnosis.

## 6. Return

Return one result packet containing:

```text
Packet and preparation identity:
Preserved candidate identity:
Any mechanically corrected instruction and authority:
Exact focused commands selected, run IDs and results:
Affected proof and result:
Every contrary signal and owning disposition:
Every frozen FINAL identity, command and result:
Changed files after R1, or none:
Consumer-observed Search result:
Architecture/replacement/operations proof:
Runtime and cleanup identity:
Omitted checks and residual risk:
Proposed ACCEPTED / REJECTED:
```

Do not commit, push, update migration master truth or start another S4 lane.
