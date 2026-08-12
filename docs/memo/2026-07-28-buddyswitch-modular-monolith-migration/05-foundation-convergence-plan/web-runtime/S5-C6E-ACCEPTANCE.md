# S5 C6E Web Runtime Acceptance

> Decision: `ACCEPTED`
> Packet: `BS-MM-S5-WEB-RUNTIME-R2-20260812-01`
> Authority: coordinating hub
> Acceptance date: 2026-08-12
> Stage effect: C6E accepted; C6F source refresh and READY preparation unblocked

## Accepted outcome

The generic Web host, passive Web contracts and packaged Web UI now have one
direct owner at `foundation/web_runtime/**`. The complete shared machine-first
CLI envelope and passive contribution contract have one sibling owner at
`foundation/cli_runtime/contracts.py`. Both package roots are inert.

Application is the sole concrete composition point for the public attach CLI
module. It supplies that immutable fact through the required Web Runtime input;
Foundation owns runtime-executable selection, argument construction, shell
quoting, Copy-command projection and Terminal invocation without importing or
embedding an Application, Launcher, product-module or runtime-support path.

The retired Launcher Web runtime/contracts, shared CLI contract and Web asset
tree are absent from source and the installed distribution. No compatibility
alias, fallback, second invocation path, registry, provider family, locator,
container or generalized command abstraction was introduced.

## Frozen identity

```text
execution HEAD/upstream:         d34cd4cd2370606bdc0c8dea97e4f380c36b8b3e
non-memo patch SHA-256:          05fc4a92a807f898d87c5560537f1590e3126aa201c99ca5dd14540e5df3f73c
index patch SHA-256:             e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855
untracked files:                 20
untracked manifest SHA-256:      ec83df6aedc150f19489e4025ba9868005e9e38195c81b2049bd72d1daab783c
git diff --check:                clean
```

Final installed runtime identity:

```text
activated_at:        2026-08-12T09:55:37.911933Z
source_digest:       f7a7b8d0522aac21c767d9b3db5deb3de956518e6976e1e2977b49e710dc0ca4
distribution_digest: b78b994ef00911097202f929dc11293b993177113854cf03c8ed9f1c5bcb1033
wheel SHA-256:       df3fd92c92095b13347a0651e9ab6697bb23ff95842daae3d5d1e89c6fe006ed
runtime.verify:      ok=true
```

The coordinating hub reproduced HEAD/upstream, patch, empty index and the
20-file content manifest; reviewed the owner, Application input, consumers,
package projection and bounded architecture guard; reproduced the exact
155-byte attach command with SHA-256 `467a9f792bc281bb76447429b843213b742e9cdf09ee2dd2a9ee8fdca765bc21`;
and independently passed the escaped-dependency proof plus exact assembly and
command boundaries as focused run `f223f61392f44d0aa50084a0e980f4bc`
(9 passed). Review changed no executable state, so the source-bound R2 affected
and FINAL evidence remains valid.

## Verification evidence

| Proof | Command/run | Result |
|---|---|---|
| escaped embedded dependency RED | exact architecture/command/input nodes; `fb3e791a175345ccb820127c3013d865` | 3 intended failures |
| exact R2 GREEN | same nodes; `86da140393914f188867b7223d90df88` | 3 passed |
| affected unit/architecture | focused owner, service, entrypoint and contribution targets; `6d8712a7db474cd289fac83631ba5a22` | 30 passed, 33 subtests |
| affected Web/IM integration | focused Web/IM files; `522f76b3dd6a48239b8d12575f74364c` | 76 passed, 95 subtests |
| package/runtime correspondence | distribution install; `93105c415e2b4e5e8f094db34c959e0f` | 3 passed |
| real Web lifecycle | focused System; `37969f678597402ab914b864db613bdd` | 1 passed with parent-known process identity |
| dotted/slash dependency guard | RED `6d4b2741633b4abbba1779b2760409e6`; GREEN `8596b84f5d724ce988bf40b657a49f7f` and `74e3cd74f64d404c85dc8db2f872cae5` | escaped slash form detected; complete proof 6 passed |
| hub finding-specific review | `f223f61392f44d0aa50084a0e980f4bc` | 9 passed; cleanup clean |
| frozen repository acceptance | `./buddyswitch-test full`; `69dd48e9e39e48c5bf232e4a8dd4552d` | all tiers, shell and diff gates passed; exit 0 |

The FINAL passed 542 Unit tests with 1,197 subtests, 147 JavaScript tests,
771 Integration tests with 458 subtests, 258 Process tests with 374 subtests,
and 22 System tests. Parent-known process/socket identities, every test root and
all attributable resources were absent at terminal capture.

## Contrary signals and disposition

The affected unit run exposed one mechanically stale test call and was closed
by exact then whole-affected GREEN. The first real-Web pass lacked external PID
sampling and was replaced by an observation-complete run. Review found missing
slash-path coverage; the bounded owner guard proved the miss RED and then
passed in full. Pre-execution command/probe mistakes changed no repository or
runtime state. The post-FINAL wheel metadata question was resolved against the
current non-editable `archive_info` contract and matching wheel hash.

No product failure, timeout, flake, contradictory terminal result, unexplained
scope drift or cleanup residue remains.

## Scope and next gate

Product, Contract, Architecture, Replacement, Operations and Correspondence
proof pass. R-FND-019 is closed. C6E R1 and R2 are consumed and must not resume.

The only unlocked action is:

```text
commit and push the C6E safe checkpoint
  -> refresh the remaining CliHost/shell/config/Role-dependent surfaces from
     that exact committed source
    -> issue C6F implementation authority only after source-bound READY review
```

C6F implementation, C7 and S6 remain unauthorized until their own gates pass.
