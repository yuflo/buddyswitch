# S5 C3 Browser Runtime Acceptance

> State: `ACCEPTED`
> Product packet: `BS-MM-S5-BROWSER-RUNTIME-R1-20260806-01`
> Proof repair: `BS-MM-S5-BROWSER-RUNTIME-R2-20260806-01`
> Stage effect: C3 accepted; C4 source refresh and READY preparation unblocked

## Accepted outcome

Browser Runtime is now one Actor-scoped Foundation owner under
`src/buddyswitch/foundation/browser_runtime/**`. Its config, CDP transport,
page lifecycle, runtime process ownership, Daemon handlers, cockpit proxy and
runtime asset moved together. Application, Runtime Broker and Instance Daemon
consume narrow current modules; the former `env/**` and `launcher/**` Browser
implementations and asset are absent with no alias, fallback or package-root
facade.

The cutover preserved the existing shell/application commands, Broker and
Daemon contracts, page/lease state, JSON and exit behavior, MCP proxy behavior,
failure cleanup and child-process ownership.

## Hub review correction

R1 product code and behavior evidence were valid. Its first architecture proof
fixed the exact private file and edge graph. R2 correctly replaced those exact
lists, but returned a 683-line test containing a Python lexical-scope analyzer.
That analyzer was caused by an over-prescriptive hub requirement and was not an
earned product or test framework.

The hub therefore preserved every R1 product, consumer, current-doc and asset
change and reduced the architecture proof to 326 lines. The final test uses
direct AST facts only for current-module discovery, dependency-cycle detection,
public import boundaries and retired residue. It contains no scope/binding
engine and does not freeze the private file set or dependency edge set.

## Frozen evidence

```text
HEAD before acceptance commit: 3664531a06a4a8f5149d78a5a6fdd41d81208795
product/test patch before acceptance records:
  5691506fe816222c6e3b7e3f4e52f9ee3efd8ae971223dad72d10c1238898ecf
index: empty
runtime.verify: ok=true
runtime source:
  1c558a9f5078709228c8847bf0f88e677109a0f871c0c315583ca4907593e6ad
runtime distribution:
  992f5d4dcef9b91fa0a93c4983f48e0ed142adc04ba96732369ed54edacae9eb
```

| Proof | Command/run | Result |
|---|---|---|
| exact architecture | `./buddyswitch-test focused tests/unit/browser/test_cdp_architecture.py`; `2de2ea8507c343a091d264428de13bdd` | 5 passed, 52 subtests |
| affected owners/consumers | explicit current architecture, Daemon, Broker and Browser targets; `02490afae9b54a1d9a49338af9e7373c` | 120 passed, 37 subtests |
| frozen repository acceptance | `./buddyswitch-test full`; `c6a7f1ad14c44df48dea1a96e0a4f5db` | 483 Unit + 1,189 subtests; 147 JavaScript; 771 Integration + 458 subtests; 260 Process + 374 subtests; 22 System; shell syntax and diff check; exit 0 |

No second FINAL ran. The final source identity matched before and after FINAL;
the activated runtime was unchanged because the hub correction modified only
the architecture test. FINAL removed its run root and left no attributable
instance, process, socket, lock or PID state.

## Scope and next gate

Both C3 packets are consumed and must not resume. C3 does not accept S5 as a
whole and does not authorize C4 implementation. It authorizes only a fresh C4
source/consumer refresh, preflight, plan and READY review against the committed
C3 checkpoint.
