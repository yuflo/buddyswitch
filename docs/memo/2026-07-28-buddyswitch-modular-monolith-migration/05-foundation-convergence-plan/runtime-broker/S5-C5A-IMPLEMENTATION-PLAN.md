# S5 C5A Runtime Broker Implementation Plan

> **For agentic workers:** use `$buddyswitch-testing`. This plan freezes the
> outcome, owners, protected contracts and proof classes; current repository
> facts determine local edits and valid focused targets.

**Goal:** Give the existing Runtime Broker and shared JSON socket framing one
direct final owner each, update every live consumer, and delete
`runtime_kernel/**` without observable behavior change.

## 1. Frame and trace

- Verify the clean preparation HEAD supplied by the hub, clean index/worktree,
  activated installed-runtime correspondence and zero attributable resources.
- Re-discover direct imports, `from ... import ...` members, patch strings,
  literal paths, subprocess entrypoints and distribution assertions.
- Partition new representations as OWNER, CONSUMER, PROOF, PACKAGE or CURRENT
  DOC. Do not stop for an omitted mechanical representation in those classes.
- Reuse the source-equivalent FINAL and C5A direct baseline; do not run `full`
  before implementation.

## 2. Establish the shared framing primitive

- Extract only the current Content-Length JSON socket read/write behavior and
  limits into one small process-runtime module.
- Preserve byte limits, JSON object requirement, EOF/header/body failure and
  send behavior.
- Make Broker client/server/lifecycle and current Daemon framing consumers use
  that direct primitive.
- Keep Broker version/request/envelope policy in Broker; do not invent a
  transport abstraction, codec registry or protocol hierarchy.

## 3. Converge Runtime Broker

- Create the earned `foundation/runtime_broker/**` physical owner.
- Move or rewrite the current protocol, coordination, dispatch, client/server
  and lifecycle directly inside it.
- Place the Broker-private advisory runtime lock with Broker coordination;
  leave current diagnostics/status behavior intact.
- Update application, ToolHost, Browser, Evidence and other live consumers to
  direct final imports.
- Preserve protocol v2, method set, identity checks, lock semantics, retry,
  feedback, lifecycle and cleanup exactly.

## 4. Replace and document

- Delete the complete `src/buddyswitch/runtime_kernel/**` root after consumers
  move.
- Remove old imports, patch targets, literals and installed-distribution
  expectations; add no alias, re-export, fallback or namespace shell.
- Update the smallest current architecture guidance for Runtime Broker and
  exact affected Browser/packaging statements.
- Add only proportional architecture/replacement proof. Tests cannot preserve
  an otherwise unused helper or old import.

## 5. Verify

- After coherent source mutation, provision/install/activate/verify before the
  next public runner command.
- Dynamically select the nearest exact and affected tests for changed Broker,
  framing and direct consumer boundaries.
- Prove Broker unit/integration/process behavior, shared framing use, package
  correspondence, old-root absence and resource cleanup.
- Review the final diff for semantic drift, Daemon scope expansion,
  speculative layers and proof complexity.
- Freeze and run one `./buddyswitch-test full`.
- If executable/test state changes after FINAL, use only the bounded
  `$buddyswitch-testing` FIX_AFTER_FINAL sequence on the attributable in-scope
  defect.

## 6. Return boundary

Return the required packet and stop. Do not update migration master truth,
commit, push, move/redesign Daemon or begin C5B/C6.
