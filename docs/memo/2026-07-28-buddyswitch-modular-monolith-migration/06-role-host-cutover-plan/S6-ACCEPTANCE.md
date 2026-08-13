# S6 RoleHost Acceptance

> Decision: `ACCEPTED`
> Accepted packet: `BS-MM-S6-ROLE-HOST-R2-20260813-01`
> Consumed packets: `BS-MM-S6-ROLE-HOST-R1-20260813-01`, `BS-MM-S6-ROLE-HOST-R2-20260813-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-13
> Stage effect: S6 accepted; S7 source refresh and READY preparation unblocked

## Accepted outcome

Every current Role is one physically aggregated reviewed package below
`src/buddyswitch/roles/<package_name>/`. The package owns its explicit durable
Role ID, descriptor, AGENTS, private Skills, assets and approved local tests.
Adding the valid `secondary_market_investor` directory made
`secondary-market-investor` available without a central Role enumeration,
host branch or generated catalog.

`foundation/role_host/**` is the only Role host. It validates the trusted
installed package root, exact package entrypoints and assets, selected public
component Skills and the selected Role's private Skills before publishing an
Actor bootstrap. Role-private Skill namespaces are genuinely local: separate
Roles may use the same private ID, while cross-Role selection and a
private/public collision fail closed with the owning Role identified.

Application supplies explicit component Skill exports and Artifact Public's
template vocabulary. Foundation imports no concrete Role or product module,
does not copy Artifact vocabulary and retains only consumer-earned immutable
Role facts. The central manifest, profiles, Role contracts/assets, central
Role-private Skill tree, runtime-support Role loaders/authority/materializer
and live path arguments are deleted without aliases, fallbacks or a second
registry.

The single public test runner discovers module- and Role-local
`unit`/`contract`/`integration` tiers dynamically. Role semantics and result
schemas are asserted by their owning packages; central tests prove generic
discovery and consumer projection rather than freezing the current Role set.
Role-local tests are excluded from the installed wheel.

## R1 review and R2 replacement

R1 produced the broad atomic cutover and a passing repository FINAL, but hub
review rejected it for three architecture defects:

1. all Role-private Skills shared one global lookup, so one Role could select
   another Role's private Skill and two Roles could not independently use the
   same private ID;
2. central tests froze the exact six-Role set and matrices, so directory-only
   extension still required central edits;
3. Foundation retained unused advisory profile fields and duplicated
   Artifact's template vocabulary.

R2 consumed the R1 candidate in place and repaired only these rejected
boundaries. It did not roll back or reimplement the migration, add
compatibility, begin S7, update master truth, stage, commit or push. R1 is not
an executable authority and must never resume.

## Frozen executable candidate identity

```text
execution base HEAD:               166bae7aee6fe7da3adde7e9f69c320f41832d9e
R1 intake tracked patch SHA-256:   30b943e04ff030b503928e4b0285b5cee5f9494eaf921b56c39b71544c34769e
accepted tracked patch SHA-256:    58ce6aa54b04dabb933b02cdafe389867503544d2c6b3bc57392377829f29490
index patch SHA-256:               e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
non-ignored untracked files:       85
untracked path/content SHA-256:    d02dd39613ac7e0309515ae52b437dd03fa298ff55ee01b316e78246cbc634c3
git diff --check:                  clean
```

Accepted installed runtime identity:

```text
activated_at:        2026-08-13T04:26:32.591975Z
source_digest:       28cbef6f68c12b9a9cdddbff94b326eb8b83453f475f1a74f62642cdccc64f38
distribution_digest: b16a15a225b592414e1fcf89347f2f2fc00d5a32750f56d4359a2c51adebf62f
package_version:     0.1.0
runtime.verify:      ok=true
```

The coordinating hub reproduced the HEAD, complete tracked patch, empty
index, untracked count/content identity and installed runtime identity. It
inspected the Role-private lookup, dynamic root/consumer tests, Application
composition, Artifact Public ownership, package projection and current
architecture guidance. Review changed no executable source, test, fixture,
runner or dependency input, so the source-bound R2 evidence remains valid and
was reused without a ritual second FINAL.

## Product and contract proof

| Claim | Evidence | Result |
|---|---|---|
| every installed Role is discovered and projected through list/runtime/bootstrap without a central enumeration | RoleHost/Role-local/owner `08f71401de114c05ab2c6cb9a479d5c9`; affected consumers `af4886c1a3654524804bf5f1315561ca`; FINAL | PASS |
| the real investor Role starts and publishes only its selected AGENTS and Skills | directory-only real Actor `0245baaa9b20402e845d21a77a6dbda6`; FINAL System path | PASS |
| same private Skill ID in different Roles is local, cross-Role selection fails and component/private collision fails before publication | RED `594e9cbdd91341bfbefe03aa6f2677a3`; exact GREEN `285538ef4b7e4c8091d306ab2ea59ab5` | PASS |
| invalid descriptors, assets, paths, templates, Roles and permissions fail closed with no fallback | exact RoleHost proof; affected consumers; FINAL | PASS |
| Actor, Broker, CLI sandbox, Browser/Search, Tool/Context, cleanup and diagnostics preserve consumer-visible behavior | affected `af4886c1a3654524804bf5f1315561ca`; FINAL | PASS |
| clean wheel/runtime contains every Role resource and excludes Role tests and retired central roots | activation/wheel `fd32828193b74698b17bf9d79c884065`; FINAL Process/package | PASS |

The accepted consumer path is:

```text
reviewed Role package + explicit component SkillExports
  -> Application RoleHost activation and authority derivation
  -> selected Role runtime/list/Actor projections
  -> Host/CLI/Broker/Tool/Context/Search/Artifact/cleanup consumers
  -> unchanged observable result with no central Role catalog
```

## Architecture and replacement proof

- `foundation/role_host/**` owns only reviewed Role package validation and
  selected immutable projections.
- `roles/<package_name>/**` owns each Role's descriptor, AGENTS, private
  Skills/assets and semantic tests.
- Application is the sole composition root combining module Skill exports,
  Artifact Public vocabulary and RoleHost.
- Artifact Public owns `VALID_ARTIFACT_TEMPLATES`; Search owns its
  `native_codex_web_search` response fact.
- Foundation imports no Application, product module or concrete Role.
- There is no generic PluginHost, product discovery, entry-point loader,
  provider family, service locator, generic execution hook, generated
  manifest, alias, fallback or compatibility path.
- Central Role exact-set/matrix tests are absent; generic tests derive the
  live set from RoleHost or directory discovery, and Role-specific assertions
  are local.
- `catalog/**`, `runtime_support/**`, central `skills/**`, launcher Role assets,
  old Role contracts/schemas and manifest/profile entrypoints are absent from
  source and the installed distribution.

The narrow-owner RED `bf0f81bdad2d41e298ed1a8f5283fd18` exposed the
unused fields and duplicated Artifact vocabulary. Exact GREEN
`285538ef4b7e4c8091d306ab2ea59ab5`, architecture/owner proof
`08f71401de114c05ab2c6cb9a479d5c9` and FINAL prove their removal.

## Frozen repository acceptance

```text
command: ./buddyswitch-test full
run: 56b2be7f071942b89ffecad5e2891bc9
exit: 0
Python unit: 528 passed, 861 subtests
JavaScript unit: 147 passed
Role-local contract: 8 passed
Integration: 771 passed, 460 subtests
Process: 248 passed, 366 subtests
System: 23 passed
total: 1,725 tests, 1,687 subtests
shell syntax: passed
diff check: passed
```

Post-FINAL source identity matched the frozen pre-FINAL identity. No
`bs-test-*` root, pytest/runner process or attributable runtime resource
remained. The coordinating review independently reproduced `runtime.verify`
and found no test root or attributable process.

## Contrary signals and disposition

- R1's passing FINAL did not override its three architecture findings. R1 was
  rejected and consumed; R2 supplied exact RED/GREEN and one replacement
  frozen FINAL.
- Two wrong activation command paths, one pre-3.10 system-Python compile and
  one zsh unmatched-glob command did not exercise or mutate the candidate.
  Repository-owned Python 3.13 activation and runner paths replaced them.
- One system-proof output was lost during context compaction. Its process and
  run root had ended; the exact proof was repeated and subsequently covered by
  the frozen FINAL.

No unexplained product failure, flake, timeout, contradictory terminal result,
ad hoc dependency or cleanup residue remains.

## Residue and transition

R-ROLE-001 through R-ROLE-007 and R-DOC-004 are closed by the owner,
consumer, package, Actor, runner and retired-path proofs above. Both S6 packets
are consumed and must not resume.

S6's charter acceptance sentence is true on the frozen candidate. S7 source
refresh and READY preparation may begin only from the committed and pushed S6
checkpoint. S7 execution/final acceptance is not authorized by this record.
