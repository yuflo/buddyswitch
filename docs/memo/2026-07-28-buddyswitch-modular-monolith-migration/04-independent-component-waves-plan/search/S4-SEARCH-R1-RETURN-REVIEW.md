# S4 Search R1 Return Review

> Decision: `R1 REJECTED AND CONSUMED`
> Candidate decision: `PRESERVE FOR CONTINUATION`
> Successor: `BS-MM-S4-SEARCH-R2-20260730-01`

## Outcome

The executor stopped correctly before test collection. Search implementation
did not fail. The R1 packet supplied this invalid focused directory:

```text
src/buddyswitch/modules/search/tests
```

The current runner recognizes co-located module tests only at:

```text
src/buddyswitch/modules/<module>/tests/unit
src/buddyswitch/modules/<module>/tests/contract
src/buddyswitch/modules/<module>/tests/integration
```

For Search, the one current equivalent is:

```text
src/buddyswitch/modules/search/tests/integration
```

`tests/runner.py::_module_test_tier_roots` and
`_validate_focused_targets` own this rule.

## Candidate identity

```text
R1 preparation HEAD:
  9b8e2efd8db21082403dfdafeb4fff09d90c3f1d
Tracked candidate patch:
  144a55b06bf89be3b2850baca89976dbeb61bf6ba3154a9467f5f87bbefbe059
Index:
  e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
Untracked candidate manifest:
  2f76f0d1c69a1289d87e8172859a6808344e935ae45b431c0877be30cd0641b1
Untracked candidate count:
  13
```

The changed paths remain within R1's OWNER, COMPOSITION, HOST, PROOF and
CURRENT DOC classes. The old Search owner is deleted, the new owner is
physically aggregated, composition selects it once, and no additional S4 lane
was touched.

The installed candidate reported:

```text
activated_at:
  2026-07-30T05:15:04.307720Z
source_digest:
  1ac19eb878ec0ff8989836280710d9c2b6ea9d00972295430f57548cb74742a9
distribution_digest:
  81f301201e85a5e3d7008dc4ca853804d93dbf863b6b6987a1b468f5c851d4fa
runtime.verify:
  ok=true
```

Run `69e82249c86343c19bf4bf792b2bb151` exited before collection. No candidate
GREEN, affected proof or FINAL exists, so the lane is not accepted.

## Root cause

R1 over-specified local execution mechanics. It correctly fixed the Search
outcome and boundary, but also made a suggested command immutable. That
converted a mechanically obvious coordinator error into a task-wide stop and
prevented a capable executor from using the runner's own contract.

This is a coordination-protocol defect, not a Search architecture defect.

## Ratchet

D-051 now separates authority:

- the hub freezes outcome, architecture boundary, protected contracts,
  classified writes, evidence classes and dependency order;
- the executor owns dynamic target discovery, compatible grouping, local
  command construction and in-scope owner-correct repair;
- an invalid instruction with one runner-proved equivalent may be corrected
  and recorded without replanning;
- ambiguity, reduced proof, semantic or protected-contract change, new write
  scope or cross-lane impact still stops.

## Continuation decision

Do not roll back, replay or patch over the Search implementation. R2 consumes
the current candidate and resumes at focused proof. R1 remains historical
evidence and may not execute again.
