# S5 C6D R1 Return Review

> Packet: `BS-MM-S5-HOST-CONTROL-R1-20260812-01`
> Disposition: `REJECTED — BOUNDED R2 CONTINUATION REQUIRED`
> Candidate: HEAD `e11ddccf9740268f327d215f4b6e11f3adae6283`, tracked patch `b2afa3e665b9e3d7957123ecfcd6ee5e740e44841b103bc92f2e4fab8d02afc3`

## Accepted candidate facts

- the returned source, index and untracked identities reproduce exactly;
- the complete Host Control lifecycle and state implementation moved under
  `foundation/host_control/**` rather than leaving a Launcher facade;
- the shared global lifecycle lock moved to
  `foundation/process_runtime/runtime_lock.py`;
- application assembly supplies one current Role catalog/start input and CLI
  and Web receive the assembled capability explicitly;
- retired Launcher Host Control, service-shell and runtime-lock paths are absent
  from source and the installed runtime;
- direct, affected, package, System and final repository evidence is
  source-bound; FINAL `66352702fd534bea944ca3da7797b435` passed all tiers;
- the activated runtime verifies with source digest
  `e963db28bf2b774ac55c64ce05b76cb8e55ea98ba2becfe656d625f38f78736e`
  and distribution digest
  `edcacab07b6da016a0b98c08f5698875ff4000f688eb993ae047e390e01c2204`;
- no attributable process, socket, lock, test root or generated build residue
  remains.

These facts remain reusable while the R1 candidate identity is unchanged.

## Blocking finding

The claimed Foundation boundary is not yet true across every executable
representation. Two owner-local helper shells still hard-code concrete
application entrypoints:

```text
foundation/host_control/shell/daemon.sh
  -> buddyswitch.application.entrypoints.central_daemon
  -> buddyswitch.application.entrypoints.instance_daemon

foundation/host_control/shell/runtime_broker.sh
  -> buddyswitch.application.entrypoints.runtime_broker
```

This is an upward runtime dependency even though it is not a Python import or
shell `source`. It means an application entrypoint change still requires a
Foundation edit, contradicting the C6D acceptance sentence and S5 dependency
law.

The new architecture proof inspected Python imports and only the primary
`host_control.sh`. It did not inspect every helper shell, so it could not detect
the escaped dependency.

## Responsibility and quality ratchet

The primary cause is preparation-side proof incompleteness: the R1 packet and
READY review said “no reverse dependency” but did not enumerate executable
module invocations as a representation class and did not require recursive
shell coverage. The executor and its reviewers had secondary responsibility
for accepting a syntactically clean but semantically upward invocation.

The durable rule is:

> A dependency proof covers every executable representation owned by the
> boundary: Python imports, shell sources, executable module invocations,
> embedded module/path strings and package projections. Scanning only a primary
> facade or one language is insufficient.

The lowest enforceable owner is the Host Control architecture test. R2 must
make it inspect all owner-local shell files without building a general static
analysis framework.

## Continuation decision

R1 is consumed and may not resume. The current dirty candidate is preserved;
no rollback, reimplementation, patch transplant or broad redesign is needed.
R2 changes only the escaped dependency boundary and its nearest proof. All
accepted lifecycle semantics, current state locations and later Web/CLI/Role
boundaries remain protected.
