# S5 C4 Source and Consumer Snapshot

## 1. Entry identity

```text
branch:                       fea-tool
executable base HEAD:         c573b8b3bd0d3bc5e0496f8bd8d7ae227e3d3b66
worktree/index/untracked:     clean before preparation
owner manifest SHA-256:       0462cf2d789f36cfc46ad36a4c77c69098fa30123fa8206d66df5086e17e6bee
runtime source digest:        1c558a9f5078709228c8847bf0f88e677109a0f871c0c315583ca4907593e6ad
runtime distribution digest:  992f5d4dcef9b91fa0a93c4983f48e0ed142adc04ba96732369ed54edacae9eb
runtime.verify:               ok=true
active instances:             0
source-equivalent FINAL:      c6a7f1ad14c44df48dea1a96e0a4f5db; exit 0
```

The C3 FINAL covers the same executable and test tree. C3 acceptance and this
preparation change only memo/current-truth records, so the FINAL remains valid
as C4 entry evidence.

The C4 refactor baseline is run `64a171bd1ff847e1b4e25136c8c46eb3`:

```text
24 passed in 16.83s
cleanup: clean
```

It directly covers identity payloads and profile persistence, state-root
refresh, Actor-private cleanup ownership, stale PID/start-identity refusal and
runtime activation correspondence.

## 2. Current owner fragments

| Current file | LOC | Current responsibility | SHA-256 prefix |
|---|---:|---|---|
| `env/domain/identity.py` | 171 | Actor/external identity model, validation and payloads | `f23b06cc8436` |
| `env/repos/identities.py` | 75 | persisted Actor/external identity profiles | `89f83193447b` |
| `env/repos/runtime_files.py` | 217 | canonical roots, write guards, ID/time and atomic JSON primitives | `ec9ce569846e` |
| `env/repos/actor_private_files.py` | 228 | one live cleanup delete boundary plus retired file-service helpers | `7512fc75b4c8` |
| `env/domain/actor_private_workspace.py` | 40 | zero-production-consumer retired descriptor helper | `f8da06fd80ce` |
| `runtime_kernel/process_identity.py` | 186 | exact process-start records and safe liveness | `78f0369ff49c` |
| `foundation/process_runtime/activation.py` | 607 | already-final installed runtime activation owner | `beedf720994c` |
| `foundation/process_runtime/invocation.py` | 129 | already-final verified invocation owner | `6ee10e0e5970` |

The current `env/**` tree contains no other live implementation. C4 can delete
that retired technical root after its live consumers move. Activation and
invocation are already correctly placed; C4 protects them rather than
manufacturing a rewrite.

## 3. Semantic owners and protected behavior

### Identity

- exact `actor` and `external` identity kinds and ID patterns;
- `IdentityRef`, `ActorIdentityProfile` and `ExternalIdentityProfile` payload
  shapes, validation and errors;
- profile persistence below
  `buddyswitch/objects/identities/{actors,externals}`;
- current actor/external profile reads, lists and writes.

`role_id` on an Actor identity is current host metadata. C4 does not acquire
Role catalog, Role selection or authorization policy; those remain S6-owned.

### State

- default shared/state/workspace root derivation and environment overrides;
- `OBJECTS_ROOT`, `LOCAL_ROOT` and the current Central IM state root;
- runtime-workspace and shared-state write guards;
- current root refresh behavior;
- ID normalization, timestamps, JSON object validation and atomic
  temporary-file-plus-`os.replace` writes;
- `$BUDDYSWITCH_ACTOR_PRIVATE_DIR == <active workspace>/private`;
- effect-time Actor-private deletion safety used by generic cleanup.

No path, schema, environment variable or write authority changes in C4.

### Process

- platform-specific process start identity;
- PID plus `.identity` record shape;
- exact match/liveness/reap/remove behavior;
- stale PID refusal across App Server, Browser, Daemon and Runtime Broker;
- installed runtime activation and verified invocation semantics.

Broker lifecycle, protocol, client, server, coordinator, dispatcher and Daemon
host behavior remain in their current C5-owned paths.

## 4. Representation-complete consumer classes

The current source has 68 direct old-owner import representations and 63
direct test/support files. C4 scope is classified by meaning rather than a
frozen path transcription:

| Class | Current consumers | C4 disposition |
|---|---|---|
| Foundation | ToolContext/registry and Browser runtime/proxy | update direct primitive imports only |
| Product modules | Demand, Task, Track, Artifact and Communication domain/state/adapters/tests | mechanically call the new direct Foundation owners; no Public or product behavior change |
| Runtime support | cleanup and turn runtime | update locators/private-delete owner only |
| Current hosts | Web, Daemon, App Server and central/instance lifecycle files | update direct identity/state/process primitive imports only; do not move or redesign hosts |
| Runtime Kernel | dispatcher and Broker lifecycle/server | update state/process primitive imports only; C5 files remain physically in place |
| Tests/support | direct imports, patches, path assertions, package topology and resource harnesses | follow current owners; tests do not earn aliases or dead surfaces |
| Current docs | new Foundation-primitives truth and exact affected references | name only implemented final paths after cutover |

Searches must include direct imports, `from package import member`, literal
paths, package-owner tuples, mocks/patch targets and installed-distribution
assertions. Newly discovered representations in these classes are in scope and
must be reported.

## 5. Dead surfaces do not migrate

`actor_private_workspace.py` has no production consumer. In
`actor_private_files.py`, only the cleanup delete boundary and its boundary
error remain production-consumed; the list/read/write/import/descriptor service
helpers have no current product consumer. Several unused `runtime_files`
helpers likewise have test-only or no consumers.

Under D-059, C4 must not preserve these surfaces through aliases, package-root
re-exports or copied modules merely because a test can name them. The executor
must retain the smallest live primitive surface proved by current production
consumers and revise tests that only preserve dead APIs.

## 6. Preparation contrary signals

Three preparation signals are fully diagnosed and changed no product state:

1. `./buddyswitch-codex runtime verify` was rejected as an unknown public CLI
   command; the installed runtime activation module is the actual owner and
   then returned `ok=true`.
2. baseline run `3695d50e29094261930c3a137d11db9d` collected no tests because
   the coordinator guessed the wrong cleanup class name; current-source
   discovery corrected it in run `64a171bd...`.
3. the first topology script used system Python 3.9 and could not parse current
   `match` syntax; the verified Python 3.13 preflight completed successfully.

None is product failure or reusable proof. All are disclosed so the execution
task does not inherit them as unexplained evidence.
