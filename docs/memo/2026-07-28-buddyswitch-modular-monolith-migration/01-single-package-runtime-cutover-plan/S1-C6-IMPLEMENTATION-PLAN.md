# S1 C6 Replacement and Final-Acceptance Implementation Plan

> REQUIRED SUB-SKILL: `superpowers:executing-plans`
> REQUIRED TESTING SKILL: `$buddyswitch-testing`
> Packet: `BS-MM-S1-C6-20260729-01`
> Source: `S1-C6-SOURCE-SNAPSHOT.md`

## Goal

Replace the remaining stale current guidance with exact installed-package
owners, add one durable architecture guard, classify all remaining retired
terms, and run the frozen S1 final acceptance gate without reopening accepted
runtime work.

## Acceptance sentence

> BuddySwitch has one current installed-package runtime truth; all active
> guidance names only current owners; every remaining old term is an exact
> negative guard, historical memo or valid unrelated text; the complete
> repository passes its frozen public test gate and leaves no owned resource.

## Task 1 — Verify the frozen start

Read the packet in its required order. Recompute:

```bash
git rev-parse HEAD
git rev-parse HEAD^{tree}
git status --porcelain=v2 --untracked-files=all
git diff -- . ':(exclude)docs/memo/**'
git diff --cached
```

Required result:

```text
HEAD 68e1272eb4dad276c8491f642006bbb24218c3f4
tree 8d01c3cf57d25c4e5472eb58140a23c9efe780c4
non-memo patch empty
index empty
only coordinating C6 memo artifacts differ from HEAD
```

Record the complete coordinating memo path set in
`S1-C6-EXECUTION-STATE.md`. Stop on any non-memo disagreement.

Run the exact pre-mutation baseline:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_external_control.py
```

It must remain green and clean.

## Task 2 — Add the discriminating RED

Edit only:

```text
tests/unit/architecture/test_package_contract.py
```

Add one test named:

```text
test_current_guidance_names_only_current_installed_package_owners
```

Implement the exact scan and required-path map from
`S1-C6-SCOPE-MANIFEST.md` section 4. Keep the test in this existing file; use
`REPO_ROOT` and `Path`; report violations as `(relative_path, token)` tuples in
stable sorted order.

Run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py::test_current_guidance_names_only_current_installed_package_owners
```

Required RED:

```text
one failed test
19 stale occurrences
only the five authorized CURRENT DOC files implicated
```

If the failure count/path set differs, stop before editing guidance.

## Task 3 — Replace exact current guidance

Edit only the five CURRENT DOC files from the scope manifest.

For `README.md`:

1. replace the retired local diagnostic shell/client recipe with:

   ```bash
   ./buddyswitch-codex env status
   ```

2. explain that an active Actor obtains exact Tool schemas through
   `context.get`;
3. replace the canonical runtime-source list with the exact package-source
   owner list in the scope manifest;
4. state that root launchers are thin stable interfaces and `pyproject.toml`
   is the sole package/build declaration.

For `AGENTS.md`, replace only the manifest and Role bootstrap stable paths.
Do not rewrite the constitution.

For the three affected `docs/arch` files, replace only the five source-owner
paths. Do not change architecture semantics.

Do not edit Web architecture, Role AGENTS, Skills, CLI/help or product code.

## Task 4 — GREEN and affected architecture proof

Run the direct GREEN:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py::test_current_guidance_names_only_current_installed_package_owners
```

Then run:

```bash
./buddyswitch-test focused \
  tests/unit/architecture/test_package_contract.py \
  tests/unit/architecture/test_repo_contracts.py \
  tests/unit/architecture/test_demand_sys_boundaries.py \
  tests/unit/architecture/test_external_control.py \
  tests/unit/actor/test_runtime_skills.py
```

Both runs must be green and clean. Record run IDs, counts, durations and
cleanup.

## Task 5 — Freeze and prove the C6 candidate before FINAL

Confirm the only non-memo changed files are:

```text
README.md
AGENTS.md
docs/arch/daemon-service-architecture.md
docs/arch/demand-sys-architecture.md
docs/arch/task-sys-architecture.md
tests/unit/architecture/test_package_contract.py
```

Run the exact active-guidance scan from the Goal Packet. It must emit no
match. Run old-root and production-loader absence checks. Classify every
repository-wide remaining match using the scope manifest; do not delete
negative guards or historical text.

Reverify the unchanged installed runtime:

```bash
BUDDYSWITCH_RUNTIME_DIR="$PWD/.buddyswitch-runtime" \
  .buddyswitch-runtime/venv/bin/python \
  -m buddyswitch.application.entrypoints.runtime_activation verify
```

It must report `runtime.verify`, `ok: true` and the source/distribution
digests in the frozen snapshot.

Run:

```bash
git diff --check
```

Freeze the candidate. No file may change after this point unless the packet
stops and returns.

## Task 6 — Run the one S1 FINAL

Run exactly:

```bash
./buddyswitch-test full
```

This is the only authorized repository-wide run. It must pass Unit, Unit
JavaScript, Integration, Process, System, shell syntax and diff check, with
clean supervisor cleanup.

If any phase fails, do not repair executable code, another test or another
document. Record the run ID/failure/cleanup, mark the packet stopped, and
return for hub replanning. The focused gates make a C6-local failure before
`full` a preparation error; do not patch around a final failure.

## Task 7 — Final residue, cleanup and return

Without changing the candidate:

- repeat the current-guidance no-match scan;
- confirm every required current source path exists;
- confirm every old physical root contains zero file/symlink;
- confirm production source has no retired loader/path;
- confirm runtime verification still passes;
- confirm no packet-owned process, PID, socket, lock, instance, test run root
  or temporary build root remains;
- run `git diff --check`;
- confirm index empty, branch/HEAD unchanged and no commit/push occurred.

Update only `S1-C6-EXECUTION-STATE.md`, then return the exact result packet
required by the Goal Packet and stop.

Do not update the migration ledger, residue register, decision log or an
acceptance record. The hub decides R-PKG-016/R-DOC-001 closure and S1
acceptance.
