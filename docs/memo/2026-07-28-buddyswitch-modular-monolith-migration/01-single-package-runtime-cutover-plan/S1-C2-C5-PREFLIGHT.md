# S1 C2–C5 Atomic Cutover Preflight

> Decision: DESIGN_FEASIBLE
> Evidence: `C2C5P-d24c5a85fec6b34a`
> Authority: coordinating hub
> Source: `S1-C2-C5-SOURCE-SNAPSHOT.md`

## 1. Boundary matrix

| Claim | Evidence | Result |
|---|---|---|
| positive current consumer behavior | complete Unit, Integration, Process and System preservation groups in the source snapshot | PASS |
| negative standalone-C2 case | `S1-C2-READY-PREFLIGHT.md` traces root wrappers, child processes and Actor copies that a source-only move would break | PASS — standalone C2 rejected |
| exact move correspondence | isolated current-source partition classified 228/228 paths into 223 unique moves and 5 deletes with zero collision | PASS |
| distribution/resource correspondence | isolated final topology built one wheel, installed non-editably and activated through exact source/install comparison | PASS after frozen F-037 package-data addition |
| forbidden distribution content | isolated wheel contained zero package tests, cache paths or bytecode | PASS |
| old-root removal | all seven moved directory roots were absent in the isolated candidate before build | PASS |
| cleanup | every test run root and isolated preflight tree absent; no BuddySwitch process/resource | PASS |

## 2. Representative final-topology fixture

The hub created a temporary copy outside the repository and:

1. applied the deterministic map in
   `02-source-and-asset-move-map.md` to all 228 tracked inputs;
2. created only the five required target package `__init__.py` files;
3. built with the current `setuptools.build_meta` configuration;
4. installed the wheel non-editably into a fresh venv;
5. invoked the installed activation entrypoint against the moved source;
6. asserted exact required resources and forbidden test/cache content;
7. removed the complete temporary tree.

Canonical result:

```json
{
  "evidence": "C2C5P-d24c5a85fec6b34a",
  "classified": 228,
  "moves": 223,
  "deletes": 5,
  "uniqueTargets": 223,
  "wheelFiles": 238,
  "requiredAssets": 7,
  "forbiddenWheelContent": 0,
  "packageDataAddition": "assets/**/LICENSE*",
  "activationKind": "runtime.activate",
  "oldRootsAbsent": true,
  "cleanup": "complete"
}
```

## 3. Preflight discoveries

### F-036 — stale process fixture

The complete process baseline initially failed because one cheap-action sample
still used retired `task_sys.close`. Production correctly rejected it. The
one-line proof correction now uses `task_sys.list`; exact and complete
process/system evidence is green. No product behavior changed.

### F-037 — extensionless launcher license resources

The first isolated direct-move build failed activation correspondence with
four source-only paths:

```text
launcher/assets/web-management/vendor/dompurify/LICENSE
launcher/assets/web-management/vendor/dompurify/LICENSE-MPL
launcher/assets/web-management/vendor/highlightjs/LICENSE
launcher/assets/web-management/vendor/markdown-it/LICENSE
```

The current explicit package-data allowlist recognizes only named extensions.
Adding the single launcher pattern `assets/**/LICENSE*` made all four
resources ship and made exact activation pass. No custom build backend,
generated manifest or broad wildcard is required. This implementation fact is
frozen in the packet; the executor does not choose a remedy.

## 4. Architecture result

D-038 is coherent:

```text
source/resources move once
  + every process consumer changes in the same candidate
  + Actor implementation publication disappears in the same candidate
  + complete lifecycle proof runs before return
```

The selected mechanism requires no compatibility owner, intermediate source
copy, alternate package, plugin system, bus, registry or canonical state
migration. C6 can remain a separate final gate because it changes current
repository guidance and performs final residue/full acceptance, while the
C2–C5 candidate itself is runnable.

## 5. Residual implementation risk

The remaining private risk is the volume of import/resource/process call-site
rewrites inside the frozen scope. It is implementation work, not an undecided
boundary. The packet controls it with:

- cross-boundary RED before movement;
- one exact move transaction;
- installed-runtime re-provision before any GREEN claim;
- unit, integration, process and system milestones;
- stop on an unmanifested consumer or changed public contract.

No material architecture question remains for the executor.
