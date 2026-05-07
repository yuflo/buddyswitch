# Switch Command Residue Cleanup Test Plan

**Goal:** Verify that product-mode `prepare` treats switch-prefixed user text as ordinary request text, while locked launcher instance metadata remains the only source of active buddy identity.

**Testing Principle:** Tests must start from product behavior and functional requirements. Do not build tests around private helper names, branch names, or implementation internals just to prove a deletion. The observable contract is prepared context, run reservation, active buddy authority, help/docs surface, and launcher command boundary behavior.

---

## Functional Requirements Under Test

FR1. A launcher-managed buddy instance accepts any non-empty ordinary request text, including text that starts with `switch <word>:` and has a body.

FR2. `prepare` preserves the exact input string in `context.request_text` and in `run_envelope.turn_identity.request_text`.

FR3. `active_buddy` is resolved only from locked instance metadata. User text that names another buddy must not switch, route, recommend, or reject.

FR4. A switch-prefixed ordinary request creates the same kind of reserved run envelope as any other ordinary request.

FR5. The prepared context must not expose switch-router concepts such as `recommended_switch`, `reference_switches`, selected skill packets, or command grammar fields.

FR6. Existing prepare safety failures remain intact: empty input, missing product session, inconsistent task/track binding, and forbidden legacy output paths still fail without partial state.

FR7. Retired top-level launcher commands remain separate public CLI guards and still fail closed before invoking Codex.

FR8. Active user-facing docs, launcher help, buddy templates, framework docs, and skill docs must not teach `switch <buddy>:` as command syntax.

FR9. The cleanup must remove the retired rejection behavior rather than adding an allowlist for only the known example string.

## Coverage Matrix

| Requirement | Test Group | Observable Proof |
| --- | --- | --- |
| FR1 | TG-01, TG-02 | `prepare` returns `ok=true` for switch-prefixed text with a body |
| FR2 | TG-01, TG-03 | context and turn identity preserve the exact input |
| FR3 | TG-02 | active buddy equals product session buddy even when text names another buddy |
| FR4 | TG-01, TG-04 | one reserved run envelope and reservation record are created |
| FR5 | TG-03, TG-08 | context has no switch-router fields; active surface scan finds no router field names |
| FR6 | TG-05 | existing negative prepare tests still fail without writes |
| FR7 | TG-06 | retired launcher commands return failure and fake Codex capture is not created |
| FR8 | TG-07, TG-08 | help output and active docs do not contain switch command examples |
| FR9 | TG-02, TG-08 | multiple prefixes work; active runtime scan finds no retired rejection path |

## Test Data Rules

Use product-shaped request text:

- Primary PM instance request: `switch market: do competitor scan`
- Market instance authority case: `switch dev: summarize positioning gaps`
- Dev instance authority case: `switch pm: implement launcher cleanup`
- Ordinary control request: `Draft the MVP PRD for onboarding rewrite`

Do not use fake strings whose only purpose is to hit a private branch. If a negative test needs bad data, use product-meaningful invalidity: empty input, no launcher-managed session, wrong task binding, wrong track binding, forbidden output path request, or retired top-level CLI command.

## Test Groups

### TG-01: Switch-Prefixed Text Prepares Successfully

**Purpose:** Prove the main user-visible behavior: text that resembles old switch syntax is ordinary request text.

**Scenario:**

1. Create a product-mode PM session through the existing test session fixture.
2. Call public `prepare_turn_context` with `switch market: do competitor scan`.
3. Assert `ok=true`.
4. Assert `active_buddy="pm"`.
5. Assert `request_text` exactly equals the input.
6. Assert `run_envelope.status="reserved"`.
7. Assert `run_envelope.turn_identity.active_buddy="pm"`.
8. Assert `run_envelope.turn_identity.request_text` exactly equals the input.

**Primary test:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_accepts_switch_prefixed_text_as_ordinary_request \
  -q
```

**Expected proof:**

- The test passes.
- No error payload is returned.
- The context looks like a normal prepared buddy run.

### TG-02: Locked Buddy Metadata Overrides Text Prefix

**Purpose:** Prove user text cannot switch the active buddy.

**Scenario:**

Run product prepare cases where the text prefix names a different buddy than the locked session:

| Locked session buddy | Request text | Expected active buddy |
| --- | --- | --- |
| `pm` | `switch market: do competitor scan` | `pm` |
| `market` | `switch dev: summarize positioning gaps` | `market` |
| `dev` | `switch pm: implement launcher cleanup` | `dev` |

For each case:

1. Prepare the request in a product session for the locked buddy.
2. Assert `ok=true`.
3. Assert `active_buddy` and `turn_identity.active_buddy` equal the locked session buddy.
4. Assert `request_text` and `turn_identity.request_text` equal the original input.
5. Assert a new reservation appears.

**Primary test:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py::TurnRuntimeBuddyRunTests::test_prepare_uses_locked_buddy_for_switch_prefixed_text \
  -q
```

**Expected proof:**

- All cases pass.
- No case routes to the buddy named in text.
- No case rejects because the text resembles retired syntax.

### TG-03: Context Contract Has No Switch Router Output

**Purpose:** Prove the prepared context does not leak old router semantics.

**Scenario:**

1. Use the TG-01 prepared context.
2. Inspect top-level context keys and `run_envelope.turn_identity`.
3. Assert the context contains ordinary prepare fields: `active_buddy`, `request_text`, `current_task_id`, `current_track_id`, `run_envelope`, `task_context`, and `warnings`.
4. Assert the context does not contain `recommended_switch`, `reference_switches`, selected skill packet fields, or command grammar fields.

**Primary test location:**

- Include these assertions in `test_prepare_accepts_switch_prefixed_text_as_ordinary_request` or a focused neighboring test if the assertion block becomes noisy.

**Expected proof:**

- Prepared context remains buddy-run oriented.
- No switch-router contract is reintroduced.

### TG-04: Switch-Prefixed Text Creates a Normal Run Reservation

**Purpose:** Prove success is not only an `ok=true` shell; it creates the same reservation state as other ordinary requests.

**Scenario:**

1. Start from an empty runtime test workspace.
2. Prepare `switch market: do competitor scan` in a PM product session.
3. Read runtime reservation state through the existing test workspace snapshot helper.
4. Assert exactly one reservation exists.
5. Assert the reservation `run_id`, `status`, `turn_identity.active_buddy`, and `turn_identity.request_text` match the prepared context.

**Primary test location:**

- Include this in `test_prepare_accepts_switch_prefixed_text_as_ordinary_request`.

**Expected proof:**

- A reserved run exists.
- The reservation matches the context.
- The request follows the normal prepare lifecycle.

### TG-05: Existing Prepare Rejections Still Protect State

**Purpose:** Prove cleanup does not weaken unrelated prepare guardrails.

**Scenarios:**

1. Empty input still returns an empty-input error.
2. Missing product-mode session still returns product-mode-required failure.
3. Task/track binding conflict still fails without creating an inconsistent reservation.
4. Forbidden legacy output path requests still fail before writes.

**Primary command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py -k "prepare and not switch_prefixed_text_as_ordinary_request and not uses_locked_buddy_for_switch_prefixed_text" \
  -q
```

**Expected proof:**

- Existing negative prepare tests pass.
- Their state snapshot assertions remain unchanged.

### TG-06: Retired Top-Level Launcher Commands Still Fail Closed

**Purpose:** Prove runtime request text cleanup does not reopen old public CLI commands.

**Scenario:**

Run existing launcher tests for retired commands:

- `buddyswitch-codex start`
- `buddyswitch-codex buddy`
- `buddyswitch-codex cleanup`
- `buddyswitch-codex reset`
- `buddyswitch-codex browser`
- `buddyswitch-codex workspace`

Each command must:

1. Return the expected failure status.
2. Print the modern replacement hint where one exists.
3. Not invoke fake Codex.

**Primary test:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_buddyswitch_launcher.py::BuddySwitchLauncherTests::test_legacy_public_commands_fail_closed_with_hints \
  -q
```

**Expected proof:**

- The test passes.
- Public CLI cleanup guards remain separate and intact.

### TG-07: Help and Active Docs Do Not Teach Switch Command Syntax

**Purpose:** Prove the product no longer instructs users to use `switch <buddy>:` as a command.

**Scenarios:**

1. Launcher `--help` still lists `instance`, `data`, and `env` namespaces.
2. Launcher `--help` does not include `switch pm:` or `switch market:`.
3. Active README/framework/skill/buddy-template surfaces do not contain `switch <buddy>:`, `switch pm:`, `switch market:`, or `switch dev:` as user command examples.

**Primary tests:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_launcher_help_keeps_instance_data_env_namespaces \
  tests/test_repo_consistency.py::RepoConsistencyTests::test_active_product_paths_exclude_legacy_switch_wire \
  -q
```

**Expected proof:**

- Help remains modern.
- Active docs and skill surfaces do not re-teach retired command syntax.

### TG-08: Active Surface Residue Scan

**Purpose:** Prove the retired rejection path is removed from active runtime/test/spec surfaces, while archive memos are not treated as product behavior.

**Scenario:**

1. Scan `scripts`, `tests`, the active buddy-run persist test plan, README, framework docs/contracts, launcher buddy templates, and first-party skill docs.
2. Search for the retired rejection code, retired detector name, old rejected wording, switch recommendation fields, and reference switch fields.
3. Exclude `docs/memo` because memos intentionally record historical context.

**Primary command:**

```bash
python3 - <<'PY'
from __future__ import annotations

from pathlib import Path

patterns = [
    "E_" + "LEGACY_COMMAND_INPUT",
    "_is_" + "legacy_command_shaped_request",
    "Legacy command-shaped request remains " + "rejected",
    "recommended_switch",
    "reference_switches",
]
roots = [
    Path("scripts"),
    Path("tests"),
    Path("docs/spec/2026-05-06-buddy-run-persist-test-plan.md"),
    Path("README.md"),
    Path("framework"),
    Path("tools/launcher/assets"),
    Path("buddyswitch/skills"),
]

matches: list[str] = []
for root in roots:
    paths = [root] if root.is_file() else [path for path in root.rglob("*") if path.is_file()]
    for path in paths:
        if path.suffix not in {".md", ".py", ".json", ".toml", ".sh"}:
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in patterns:
            if pattern in text:
                matches.append(f"{path}: {pattern}")

if matches:
    print("\n".join(matches))
    raise SystemExit(1)
PY
```

**Expected proof:**

- Command exits `0`.
- No output.
- Archive memo files may still mention history, but active behavior surfaces do not.

## Anti-Cheat Guardrails

- Do not write tests that call or assert private request-shape helpers. The desired proof is public prepare behavior.
- Do not make the runtime accept only `switch market: do competitor scan`; any switch-prefixed text with a body must be ordinary request text.
- Do not parse the buddy named in text and then compare it with the locked buddy. Text is not a router input.
- Do not keep a rejection branch and bypass it with an allowlist.
- Do not remove launcher fail-closed tests to make runtime cleanup look green.
- Do not satisfy docs checks by hiding switch command syntax in another active help surface.
- Do not declare completion from `ok=true` alone; assert text preservation, active buddy authority, and run reservation.

## Final Verification Command Set

Run from `/Users/chen/Dev/buddyswitch/.worktrees/dev0210`:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider \
  tests/test_turn_runtime.py tests/test_repo_consistency.py tests/test_buddyswitch_launcher.py \
  -k "switch or legacy_command or launcher_help or prepare" \
  -q
```

Then run TG-08 residue scan.

Expected result:

- Selected tests pass.
- Active residue scan exits `0`.
- `git status --short` shows only intended source/test/doc changes and any pre-existing unrelated untracked memos.
