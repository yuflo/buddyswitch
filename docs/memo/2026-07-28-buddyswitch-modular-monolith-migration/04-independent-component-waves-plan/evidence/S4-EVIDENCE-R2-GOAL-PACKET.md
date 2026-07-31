# S4 Evidence R2 Continuation Goal Packet

> Packet state: `READY`
> Packet ID: `BS-MM-S4-EVIDENCE-R2-20260731-01`
> Predecessor: `BS-MM-S4-EVIDENCE-R1-20260731-01` consumed and rejected

## 1. Independent-task request

```text
Create and pursue this goal:

Execute BuddySwitch packet BS-MM-S4-EVIDENCE-R2-20260731-01 in
/Users/chen/Dev/buddyswitch/.worktrees/fea-tool from the exact coordinating
checkpoint supplied by the hub.

Read root AGENTS.md, use superpowers:executing-plans, read the complete
$buddyswitch-testing skill and routed references, then read the Evidence lane
README, S4-EVIDENCE-R1-RETURN-AND-ROOT-CAUSE-REVIEW.md,
S4-EVIDENCE-R2-CONTINUATION-PLAN.md and
S4-EVIDENCE-R2-READY-REVIEW.md.

Preserve the existing dirty R1 structural candidate. Do not roll it back,
replay the cutover, recreate structural RED, or resume R1. Verify candidate,
installed runtime and cleanup identity, then add assertion-level process proof
in tests/process/browser/test_browser_evidence_cli.py using the installed
stable command and a real Runtime Broker. The proof must cover successful
issue, successful approve-downgrade, business rejection, unavailable Broker,
canonical JSON, exit mapping and cleanup.

First run the new consumer proof as RED on the preserved candidate. It must
fail because successful canonical ToolResult has tool_evidence but no
feedback, causing the stable command to exit 1. Then modify only
src/buddyswitch/modules/evidence/entrypoints/browser_evidence.py so successful
responses validate tool_evidence and return the canonical Broker ToolResult.
Do not synthesize feedback or modify Evidence Tool, Artifact, Runtime Broker,
Browser, host or composition behavior.

After the source change, rebuild/install/activate/verify before another public
test. Run exact GREEN, dynamically selected direct and affected focused proof,
replacement/package/cleanup checks, then freeze and run ./buddyswitch-test
full once. After FINAL make no executable, test or package mutation and do not
rerun. Return the complete result packet and stop.

Only the module-owned command adapter and the named root process test are
authorized executable writes. Stop once for any additional required path,
semantic/boundary/protected-contract change, ambiguous proof, invalid
source/runtime identity, unexplained focused failure, cleanup residue or FINAL
failure. Do not edit migration master acceptance, commit, push, change branch,
start Communication/Context/S5, create compatibility, or issue another
Evidence repair.
```

## 2. Source handoff

```text
Preparation checkpoint:
  supplied by the coordinating hub after R2 coordinating documents are committed

Preserved candidate base HEAD:
  4184211435778e2168bd198215ea4ad730d31cf4

Preserved candidate tracked binary patch:
  2fc9cb4e249da3d8affc4c81ae7241253be2e82ebdb23b6cda757ffb209a6d5e

Preserved candidate index:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855

Preserved candidate untracked count:
  11

Preserved candidate newline path-list SHA-256:
  a357d1fef183de927c4cd468c91260092591d889d0b687ae589ab8011bcaf703

Preserved candidate sorted content-SHA/path manifest:
  26262898c0263407ead137c9b1e1c740240217f1f6f12777e7f6ee3a10409ccd

Installed candidate source digest:
  1f9765b7f4bbf1b9236ec7340279eaf84cf693f4aeebee78b6cc875064b13010
```

Identity algorithms:

```text
tracked binary patch:
  SHA-256 of exact `git diff --binary` bytes after coordinating memo changes
  are committed

index:
  SHA-256 of exact `git diff --cached --binary` bytes

untracked path list:
  SHA-256 of LF-terminated, bytewise-sorted output from
  `git ls-files --others --exclude-standard`, excluding `docs/memo/**`

untracked content manifest:
  for those same sorted paths, concatenate the standard
  `<file SHA-256><two spaces><path><LF>` rows and SHA-256 the exact bytes
```

There is no opaque aggregate material manifest.

The coordinating checkpoint may add or modify only migration memo documents.
Any other executable/test/current-architecture delta beyond the preserved R1
candidate stops.

## 3. Authority

Allowed executable writes:

```text
src/buddyswitch/modules/evidence/entrypoints/browser_evidence.py
tests/process/browser/test_browser_evidence_cli.py
```

Protected and selected behavior is exact in the R2 plan. The executor owns
test-local fixture organization, current runner-valid target construction and
private code expression inside that boundary. It does not own another product
response schema or another write path.

## 4. Verification and return

Use only:

```bash
./buddyswitch-test focused <executor-selected current targets>
./buddyswitch-test full
```

`full` is authorized once only after RED/GREEN, affected proof,
source/runtime correspondence and cleanup are clean on a frozen candidate.

Return the result fields in `S4-EVIDENCE-R2-CONTINUATION-PLAN.md` and stop.
Only the coordinating hub may accept Evidence, update migration truth, commit
the candidate, push it or authorize another lane.
