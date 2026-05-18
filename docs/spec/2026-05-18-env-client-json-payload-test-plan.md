# Env Client JSON Payload Test Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove from user-visible behavior that env client `--payload` is an inline JSON object string contract, not a payload-file contract, and that active buddy guidance produces commands that do not trigger the observed sandbox retry failure.

**Architecture:** Tests exercise the CLI as the user-facing boundary, the broker request envelope as the external handoff point, active skills as the instructions buddies read, and product-mode smoke as the real path where the bug appeared. Invalid payload tests assert no broker dispatch, which is the observable guarantee that no runtime state can mutate.

**Tech Stack:** `pytest`, Python `unittest`, `unittest.mock`, subprocess CLI help checks, runtime skill text tests, repository residue scans, launcher-managed product-mode smoke.

---

## Requirements Model

R1. For every payload-bearing env client operation, `--payload` accepts a JSON object string.

R2. `--payload` does not accept payload file paths as an active route.

R3. Malformed JSON, JSON arrays, strings, numbers, booleans, or null reject before env.tool broker dispatch.

R4. CLI help clearly names `--payload JSON_OBJECT` and says it is a JSON object string.

R5. Active shared skills teach the same JSON object string contract that the CLI implements.

R6. Active shared skills do not teach `/tmp/*.json`, `<json-file>`, `<file>`, or "payload file" as the current route.

R7. Existing env.tool semantics, store mutation behavior, permissions, and track/artifact publication contract remain unchanged.

R8. The original Design buddy scenario can create and publish a design artifact with JSON string payloads, without triggering sandbox escalation for payload handling.

R9. Invalid CLI payloads cannot mutate runtime state because they never reach the broker.

## Risk Model

Primary risks:

- Agents continue to generate payload-file commands because skills or help still teach the old shape.
- The CLI accidentally keeps a hidden file-path compatibility route, preserving ambiguity.
- Valid JSON strings work for artifact but not for another payload-bearing command such as message, comment, task, or buddybox.
- Invalid payloads reach broker and produce service-level errors or partial state changes instead of being rejected by CLI parsing.
- Help text remains vague and future buddies repeat the same mistake.
- Product-mode smoke passes automated unit tests but still triggers sandbox approval in a real buddy session.
- Historical docs produce noisy residue failures if the scan does not distinguish active guidance from old memos/specs.

Testing rules:

- Test user-visible CLI behavior, not private helper internals.
- For valid payloads, assert the broker envelope because that is the CLI's external contract.
- For invalid payloads, assert the broker is not called.
- For guidance, scan only active runtime guidance surfaces unless a test explicitly targets historical docs.
- Do not prove success by checking implementation details such as `argparse` type values.
- Do not call or edit `buddyswitch/objects/**` directly in product-mode smoke.

## Test Matrix

| ID | Level | Requirement | File / Method | Main assertion |
| --- | --- | --- | --- | --- |
| C1 | CLI contract | R1/R7 | `tests/test_env_client_payload_cli.py` | Every payload-bearing operation dispatches a JSON object string as env.tool args |
| C2 | CLI contract | R2/R9 | `tests/test_env_client_payload_cli.py` | A path-like payload string rejects and no file is read |
| C3 | CLI contract | R3/R9 | `tests/test_env_client_payload_cli.py` | Malformed JSON rejects before broker dispatch |
| C4 | CLI contract | R3/R9 | `tests/test_env_client_payload_cli.py` | Non-object JSON values reject before broker dispatch |
| H1 | CLI help | R4 | `tests/test_env_tool_router.py` | Payload operation help shows `--payload JSON_OBJECT` and JSON object string guidance |
| S1 | Skill contract | R5/R6 | `tests/test_runtime_skills.py` | Shared tool skills teach JSON object string payloads and no file-path route |
| R1 | Residue | R6 | `tests/test_repo_consistency.py` | Active guidance has no stale payload-file route |
| E1 | Product smoke | R1/R5/R8/R9 | Manual launcher smoke | Design buddy creates, publishes, and verifies a design artifact using JSON string payloads without payload sandbox escalation |
| G1 | Regression | R7 | Full pytest suite | Existing runtime behavior remains intact |

## Detailed Tests

### C1: JSON Object String Dispatches for Every Payload Operation

**Level:** CLI contract

**File:** `tests/test_env_client_payload_cli.py`

**Functional requirement:** A caller can pass one JSON object string to any payload-bearing operation and the CLI sends that object as env.tool `args`.

**Initial state:**

- No live broker is required.
- `env.client.request_runtime_broker` is mocked to return `{"ok": true}`.
- The test calls `env.client.main()` with a realistic `sys.argv`.

**Operation cases:**

- `task create --payload '{"task_id":"task-json","title":"Task","buddy":"dev"}'`
- `task update --payload '{"task_id":"task-json","summary":"Updated"}'`
- `track create --payload '{"track_id":"track-json","title":"Track","outcome":"Outcome","appetite":"1 day","now":{"next":"next","blocker":null}}'`
- `track update-now --payload '{"track_id":"track-json","now":{"next":"next","blocker":null}}'`
- `track add-material --payload '{"track_id":"track-json","artifact_id":"art-json","label":"Brief","summary":"Summary"}'`
- `track add-update --payload '{"track_id":"track-json","summary":"Progress","kind":"progress"}'`
- `track add-proof --payload '{"track_id":"track-json","artifact_id":"art-proof","label":"Proof","summary":"Summary"}'`
- `artifact create-revision --payload '{"title":"Artifact","summary":"Summary","template":"brief","body":"# Body"}'`
- `artifact update-metadata --payload '{"artifact_id":"art-json","summary":"Updated"}'`
- `buddybox write --payload '{"logical_name":"notes.md","content":"hello"}'`
- `message send --payload '{"to_buddy":"design","content":"Please review"}'`
- `comment add --payload '{"target_type":"track","target_id":"track-json","content":"Looks good"}'`

**Assertions:**

- `client.main()` returns `0`.
- stdout JSON is `ok=true`.
- Mocked broker is called once with method `env.tool`.
- Broker params use the expected `tool`, normalized `action`, and exact JSON object as `args`.
- No test case passes a payload file path.

**Regression value:** Prevents fixing artifact only while leaving other payload operations on the old route.

### C2: Path-Like Payload String Is Not a File Route

**Level:** CLI contract

**File:** `tests/test_env_client_payload_cli.py`

**Functional requirement:** `/tmp/payload.json` is not accepted as a payload. The CLI must not try to read it.

**Initial state:**

- No live broker is required.
- `env.client.request_runtime_broker` is mocked.
- `pathlib.Path.read_text` is mocked to raise if called after import.

**Operation:**

```bash
python3 scripts/env/client.py artifact create-revision --payload /tmp/artifact.json
```

**Assertions:**

- Return code is `1`.
- stdout JSON has `ok=false`.
- `error.code="E_ENV_CLI"`.
- Error message contains `--payload must be a JSON object string`.
- Broker is not called.
- `Path.read_text` is not called for the payload value.

**Regression value:** Proves no hidden file compatibility path remains.

### C3: Malformed JSON Rejects Before Broker Dispatch

**Level:** CLI contract

**File:** `tests/test_env_client_payload_cli.py`

**Functional requirement:** Bad JSON syntax is a CLI input error, not a runtime env.tool request.

**Operation:**

```bash
python3 scripts/env/client.py track add-material --payload '{not-json'
```

**Assertions:**

- Return code is `1`.
- stdout JSON has `ok=false`.
- `error.code="E_ENV_CLI"`.
- Error message contains `--payload must be a JSON object string`.
- Error message includes parse context such as `char`.
- Broker is not called.

**Regression value:** Prevents malformed payloads from becoming runtime service errors or mutation attempts.

### C4: Non-Object JSON Rejects Before Broker Dispatch

**Level:** CLI contract

**File:** `tests/test_env_client_payload_cli.py`

**Functional requirement:** `--payload` accepts only a JSON object, never another JSON type.

**Operations:**

```bash
python3 scripts/env/client.py message send --payload '[]'
python3 scripts/env/client.py message send --payload '"text"'
python3 scripts/env/client.py message send --payload 'null'
python3 scripts/env/client.py message send --payload '1'
python3 scripts/env/client.py message send --payload 'true'
```

**Assertions for each case:**

- Return code is `1`.
- stdout JSON has `ok=false`.
- `error.code="E_ENV_CLI"`.
- Error message contains `--payload must be a JSON object string`.
- Broker is not called.

**Regression value:** Protects the env.tool envelope shape from invalid `args`.

### H1: CLI Help Teaches the JSON Object String Contract

**Level:** CLI help

**File:** `tests/test_env_tool_router.py`

**Functional requirement:** A buddy using CLI help sees the correct payload shape before writing a command.

**Operations:**

```bash
python3 scripts/env/client.py task create --help
python3 scripts/env/client.py track add-material --help
python3 scripts/env/client.py artifact create-revision --help
python3 scripts/env/client.py buddybox write --help
python3 scripts/env/client.py message send --help
python3 scripts/env/client.py comment add --help
```

**Assertions for each help output:**

- Return code is `0`.
- stdout contains `--payload JSON_OBJECT`.
- stdout contains `JSON object string`.
- stdout does not contain `--payload PAYLOAD`.
- stdout does not contain `payload file`.

**Regression value:** Prevents vague help text from recreating the incident.

### S1: Shared Tool Skills Teach the Same Payload Contract

**Level:** Skill contract

**File:** `tests/test_runtime_skills.py`

**Functional requirement:** Active skills that buddies read describe the JSON object string route and no file route.

**Files under test:**

- `buddyswitch/skills/shared/task-tool/SKILL.md`
- `buddyswitch/skills/shared/track-tool/SKILL.md`
- `buddyswitch/skills/shared/artifact-tool/SKILL.md`
- `buddyswitch/skills/shared/buddybox-tool/SKILL.md`
- `buddyswitch/skills/shared/message-tool/SKILL.md`
- `buddyswitch/skills/shared/comment-tool/SKILL.md`

**Assertions for each file:**

- Contains `--payload`.
- Contains `JSON object string`.
- Does not contain `--payload /tmp`.
- Does not contain `payload file`.
- Does not contain `payload file path`.

**Regression value:** Catches the exact route by which Design buddy learned or inferred the wrong command shape.

### R1: Active Guidance Residue Scan

**Level:** Repository consistency

**File:** `tests/test_repo_consistency.py`

**Functional requirement:** Active runtime guidance surfaces have no stale file payload route.

**Scan targets:**

- `AGENTS.md`
- `buddyswitch/skills`
- `framework/contracts`
- `tools/launcher/assets/buddies`
- `scripts/env/client.py`

**Pattern:**

```text
payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE
```

**Assertions:**

- `rg` return code is `1` for no matches.
- Any match fails the test with the matching lines.

**Allowed exclusions:**

- Historical `docs/spec`, `docs/memo`, and `docs/bitter` are excluded from this active guidance test.
- The new implementation and test plans may mention the old file route as incident context.

**Regression value:** Ensures old route does not survive in active prompts, skills, contracts, or CLI help.

### E1: Product-Mode Design Buddy Smoke

**Level:** Product smoke

**Functional requirement:** The real Design buddy flow that exposed the bug can complete with JSON string payloads and without a payload-related sandbox retry.

**Initial state:**

- Current worktree is `track-artifact-pm-runtime-repair`.
- PM track and artifacts from the incident may exist:
  - Track: `freecallai-us-eu-landing-page`
  - PRD artifact: `art-1f5257c017`
  - Draft artifact: `art-8bc569a5b9`
- If those objects do not exist in a fresh runtime, create equivalent PM track/materials through env tools before running Design smoke.

**Operation:**

```bash
./buddyswitch-codex instance start --buddy design -- exec "Read track freecallai-us-eu-landing-page and artifacts art-1f5257c017/art-8bc569a5b9. Create a revised design-direction artifact using artifact.create_revision with --payload as a JSON string, publish it to the same track with track.add_material using --payload as a JSON string, then verify with track.open and artifact.get. Do not write raw state files."
```

**Assertions:**

- No payload-related "retry without sandbox" approval appears.
- Design buddy uses `artifact.create_revision --payload '<json object>'` or command substitution that produces one JSON object string.
- Design buddy uses `track add-material --payload '<json object>'` to publish.
- `track.open` shows the new design artifact in `shared_materials`.
- `artifact.get` reads the new design artifact body.
- No raw edits to `buddyswitch/objects/**` are made.

**Blocked handling:**

- If launcher or broker startup fails, record the exact error and run automated gates plus a non-product mocked-broker CLI smoke.
- A blocked product smoke means final acceptance is not complete unless the user explicitly accepts the environment limitation.

**Regression value:** Verifies the change in the same class of session where the issue appeared.

### G1: Full Regression Suite

**Level:** Regression

**Requirement:** Existing runtime behavior remains intact.

**Command:**

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q
```

**Assertions:**

- Full suite passes.
- Existing expected skips are unchanged.
- No unrelated tests fail because of CLI parsing changes.

## Focused Gate Commands

Run these after implementation:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_env_client_payload_cli.py tests/test_env_tool_router.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider tests/test_runtime_skills.py tests/test_repo_consistency.py -q
PYTHONDONTWRITEBYTECODE=1 python3 -m py_compile scripts/env/client.py tests/test_env_client_payload_cli.py tests/test_env_tool_router.py tests/test_runtime_skills.py tests/test_repo_consistency.py
rg -uuu -n "payload file|--payload /tmp|--payload <json-file>|--payload <file>|PAYLOAD_JSON_FILE" AGENTS.md buddyswitch/skills framework/contracts tools/launcher/assets/buddies scripts/env/client.py
```

Expected results:

- Both pytest focused gates pass.
- `py_compile` exits 0.
- `rg` returns no matches.

## Main Verification Commands

Run before final acceptance:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m pytest -p no:cacheprovider -q
git status --short
git branch --show-current
git rev-parse --show-toplevel
git -C /Users/chen/Dev/buddyswitch status --short
```

Expected results:

- Full suite passes.
- Current branch is `track-artifact-pm-runtime-repair`.
- Current toplevel is `/Users/chen/Dev/buddyswitch/.worktrees/track-artifact-pm-runtime-repair`.
- Main checkout has no changes from this work.

## Acceptance Criteria

- C1 through C4 pass.
- H1, S1, and R1 pass.
- E1 product-mode smoke passes, or a concrete environment blocker is recorded and explicitly treated as blocking final acceptance.
- G1 full regression suite passes.
- The final report includes commands run, results, worktree isolation, remaining risks, and whether final acceptance is achieved.

