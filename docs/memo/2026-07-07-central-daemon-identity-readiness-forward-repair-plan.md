# Central Daemon Identity Readiness Forward Repair Plan

Date: 2026-07-07
Status: repair plan, not yet implemented.

## 任务目标

修复 `fea-tool` 与 `fea-im` 合并后暴露的 central daemon 启动阻塞：

```text
./buddyswitch-codex web --port 8766
central daemon did not become ready; see .../central-daemon.log
```

目标不是回退 `fea-im` 的 identity-first 更新，也不是在 service 层补旧协议兼容。目标是把 central daemon readiness probe 前进到当前唯一契约：`actor.check_reachability` 只使用 `target_identity_id`。

完成后，`buddyswitch-codex web`、launcher 启动路径、central daemon CLI readiness 检查、central daemon service reachability、daemon client helper 必须只有一条 identity-first 路径。旧的 actor-address readiness 语义不得作为 live code、live tests、runtime guidance 或 fallback 留下。

## 核心要求

- 单一路径：ready probe 使用 actor identity id，不再发送或期待 actor address payload。
- 无双轨兼容：不增加 `target_actor_address` -> `target_identity_id` fallback，不保留 `actor_address_protocol` 成功标志，不让 core 同时接受新旧字段。
- 无残留：central daemon readiness 相关 live surfaces 不再出现旧 readiness 契约名称、旧错误消息、旧测试名。
- 保留 updated feature：`fea-im` 引入的 `target_identity_id` IM/reachability 契约是当前正确方向；`fea-tool` 引入的 browser cockpit/search_page 方向也不是本问题的修复对象。
- 验证闭环：先用 focused failing tests 锁定边界，再改 owning module，最后用 temp shared-root process smoke 和最小 web smoke 验证真实入口。

## docs/bitter 应用要点

- `2026-05-18-tool-skill-layering-principles.md`：runtime-visible tool/service semantics 属于 owning layer；修 `central_daemon.py` readiness probe 和测试，不靠 prompt 或调用方绕过。
- `2026-05-26-test-resource-lifecycle-principles.md`：启动 daemon 的测试必须拥有进程生命周期、注册、停止和残留检查。
- `2026-05-28-parallel-change-boundary-principles.md`：这次合并冲突是 shared contract ownership 问题；应缩小并明确 shared contract，而不是补宽兼容面。
- `2026-06-02-residue-cleanup-principles.md`：语义替换完成需要 behavior proof 和 scoped residue proof；历史 memo/spec 不是 cleanup target，live surface 才是。
- `2026-06-02-wrong-boundary-narrowness-principles.md`：不能在错误边界做窄修。core service 已是 identity-first，错误边界是 launcher readiness probe。
- `2026-06-25-built-in-product-interface-principles.md`：product core 拥有 identity/reachability 规则；CLI 是生命周期投影，不能自造旧 routing model。
- `2026-06-25-end-to-end-contract-slice-principles.md`：必须保留一条用户可见 contract sentence：`buddyswitch-codex web -> central daemon ensure -> identity reachability probe -> web process starts or returns actionable error`。

## 关键问题归类

| 类别 | 结论 | 处理方式 |
| --- | --- | --- |
| P0 merge contract blocker | `tools/launcher/central_daemon.py` still probes `actor.check_reachability` with `target_actor_address`, while `central_daemon_core.py` now accepts `target_identity_id`. | 修复。唯一源码阻塞点。 |
| P1 test gap | `tests/test_central_daemon_service.py` 仍有 actor-address readiness 预期，导致 focused central daemon tests 全绿但真实 start 失败。 | 修复。测试必须改为 identity readiness 并加 residue guard。 |
| P1 verification cascade | launcher/browser 大量失败来自 central daemon 未 ready。 | 修复 P0 后再复跑；先不把 browser 当独立问题改。 |
| P2 operational residue | 本机可能有 orphan central daemon process。 | 作为验收前后环境清理项处理；不是源码根因，不进入架构修复。 |
| Cleared updated-feature surfaces | browser cockpit/search_page、IM reply wrapper、identity-first routing 等是已更新特性。 | 不回退、不包兼容、不误判为 bug。 |

## 当前代码事实

- `tools/launcher/central_daemon_core.py` owns service semantics. `_reachability()` reads `params["target_identity_id"]` and returns `target_identity_id`; this is the updated feature and should remain the single service contract.
- `scripts/env/tool_runtime/daemon_client.py` exposes `check_reachability(target_identity_id=...)`; this is the correct client projection and should be reused by the readiness probe.
- `tools/launcher/central_daemon.py` owns process lifecycle and readiness. Its `ping_central_daemon()` is stale because it sends `{"target_actor_address": PROBE_ACTOR_ADDRESS}` and sets `actor_address_protocol`.
- `tools/launcher/daemon.sh` and `buddyswitch-codex web_main()` call central daemon ensure before web management starts, so this stale readiness probe blocks `./buddyswitch-codex web --port 8766`.
- `tests/test_central_daemon_service.py` currently has tests named `test_ping_rejects_daemon_without_actor_address_protocol` and `test_start_daemon_restarts_live_process_without_actor_address_protocol`; these tests preserve the old readiness contract and must be replaced, not retained as legacy coverage.

## 架构边界

### `tools/launcher/central_daemon_core.py`

Boundary: central daemon RPC semantics, actor identity registry, reachability status, signal delivery.

Expected state: keep identity-only `actor.check_reachability` semantics. Do not add `target_actor_address` acceptance here. If a caller sends old fields, the service may return identity validation failure; that is acceptable because old readiness contract is removed.

### `scripts/env/tool_runtime/daemon_client.py`

Boundary: client projection for central daemon RPC.

Expected state: keep `check_reachability(*, target_identity_id, socket_path=None)` as the only public helper for reachability. No actor-address helper should be added.

### `tools/launcher/central_daemon.py`

Boundary: process lifecycle, start/status/stop, readiness probing.

Expected state: `ping_central_daemon()` first verifies daemon ping, then verifies identity reachability through `daemon_client.check_reachability(target_identity_id="act-central-daemon-probe", socket_path=...)`. It returns readiness metadata that names the identity protocol, not actor-address protocol.

### `tools/launcher/daemon.sh` and `buddyswitch-codex`

Boundary: consumer entrypoints. They should not own reachability semantics.

Expected state: no source change unless verification proves they mis-handle the central daemon result. They continue to call `buddyswitch_central_daemon_ensure`.

### Tests

Boundary: protect the live contract and residue cleanup.

Expected state: focused tests fail before the source fix, pass after the source fix, and reject reintroduction of actor-address readiness surfaces.

## 修复步骤

### Step 1: Replace stale readiness tests with identity contract tests

File: `tests/test_central_daemon_service.py`

Replace `test_ping_rejects_daemon_without_actor_address_protocol` with a test that proves `ping_central_daemon()` uses identity reachability:

- Patch `cli.daemon_client.request_central_daemon` for `daemon.ping`.
- Patch or observe `cli.daemon_client.check_reachability`.
- Assert the reachability call receives `target_identity_id == "act-central-daemon-probe"` and the same `socket_path`.
- Return `{"reachability_status": "never_registered", "target_identity_id": "act-central-daemon-probe", "record": None}` from the fake checker.
- Assert returned ping payload contains `identity_reachability_protocol is True`.
- Assert no call sends `target_actor_address`.

Replace `test_start_daemon_restarts_live_process_without_actor_address_protocol` with the same lifecycle intent under the new protocol:

- Existing live pid remains terminated when its ping fails.
- Failure reason uses `central daemon does not support identity reachability protocol`.
- Newly spawned process becomes ready through identity reachability.
- Assertions stay about restart behavior, not old protocol naming.

Add a small residue guard in this same test file:

```python
def test_central_daemon_readiness_has_no_actor_address_contract(self) -> None:
    text = CENTRAL_CLI_PATH.read_text(encoding="utf-8")
    for forbidden in (
        "PROBE_ACTOR_ADDRESS",
        "target_actor_address",
        "actor_address_protocol",
        "actor-address protocol",
    ):
        self.assertNotIn(forbidden, text)
```

This guard is intentionally scoped to central daemon readiness live surface, not the whole repository.

### Step 2: Move `central_daemon.py` readiness probe to identity-only

File: `tools/launcher/central_daemon.py`

Replace:

```python
PROBE_ACTOR_ADDRESS = {"actor_id": "act-central-daemon-probe", "role_id": "dev"}
```

with:

```python
PROBE_IDENTITY_ID = "act-central-daemon-probe"
READY_REACHABILITY_STATUSES = {"online", "registered_offline", "never_registered"}
```

Replace `ping_central_daemon()` with identity reachability logic:

```python
def ping_central_daemon(*, socket_path: Path) -> dict[str, Any]:
    ping = daemon_client.request_central_daemon("daemon.ping", {}, socket_path=socket_path)
    reachability = daemon_client.check_reachability(
        target_identity_id=PROBE_IDENTITY_ID,
        socket_path=socket_path,
    )
    if (
        reachability.get("target_identity_id") != PROBE_IDENTITY_ID
        or reachability.get("reachability_status") not in READY_REACHABILITY_STATUSES
    ):
        raise RuntimeError("central daemon does not support identity reachability protocol")
    ping["identity_reachability_protocol"] = True
    return ping
```

Do not add any fallback branch for old fields. Do not modify `central_daemon_core.py` to accept `target_actor_address`.

### Step 3: Run focused central daemon verification

Commands:

```bash
python3 -m pytest tests/test_central_daemon_service.py -q
```

Expected result:

- The identity readiness tests pass.
- The service reachability tests still prove `online`, `registered_offline`, `never_registered`, and `invalid_identity_id`.
- No test name or assertion still teaches actor-address readiness.

### Step 4: Prove real process lifecycle with temp shared root

Use an isolated shared root and stop it in the same validation block:

```bash
tmp_root="$(mktemp -d "${TMPDIR:-/tmp}/buddyswitch-central-ready.XXXXXX")"
python3 tools/launcher/central_daemon.py start --shared-root "$tmp_root"
python3 tools/launcher/central_daemon.py status --shared-root "$tmp_root"
python3 tools/launcher/central_daemon.py request --shared-root "$tmp_root" --method actor.check_reachability --params '{"target_identity_id":"act-central-daemon-probe"}'
python3 tools/launcher/central_daemon.py stop --shared-root "$tmp_root"
```

Expected result:

- `start` exits 0 and returns JSON with `ok: true`, `socket_path`, and `ping.identity_reachability_protocol: true`.
- `status` reports healthy while the daemon is running.
- direct reachability request returns `target_identity_id: "act-central-daemon-probe"` and a valid reachability status, normally `never_registered`.
- `stop` exits 0 and removes pid/socket runtime files.

After this, check for temp-root process residue:

```bash
ps aux | rg "central_daemon.py serve --shared-root $tmp_root"
```

Expected result: no match after stop. If it matches, kill only that exact temp-root process and treat lifecycle cleanup as a failed verification to fix before broader tests.

### Step 5: Run scoped residue checks

Commands:

```bash
rg -n "PROBE_ACTOR_ADDRESS|target_actor_address|actor_address_protocol|actor-address protocol" tools/launcher/central_daemon.py tests/test_central_daemon_service.py scripts/env/tool_runtime/daemon_client.py
python3 -m pytest tests/test_repo_consistency.py::RepoConsistencyTests::test_live_browser_guidance_is_cockpit_first -q
```

Expected result:

- The `rg` command has no output.
- Browser guidance consistency remains green, proving the repair did not disturb cockpit/search_page direction.

Historical `docs/spec/**`, old memos, and this plan are not live runtime surfaces and are not cleanup targets for this scoped check.

### Step 6: Re-run the launcher/browser cascade only after P0 is green

Commands:

```bash
python3 -m pytest tests/test_buddyswitch_launcher.py -q
python3 -m pytest tests/test_browser_cockpit_proxy.py tests/test_browser_page_expired_handler.py tests/test_browser_lazy_release_integration.py -q
```

Expected result:

- Failures caused by `central daemon did not become ready` disappear.
- Any remaining browser failures must be reclassified from fresh evidence, not assumed to be part of this identity-readiness bug.

### Step 7: Minimal user-entry smoke

Run the same class of command that exposed the issue, using a short controlled session:

```bash
./buddyswitch-codex web --port 8766
```

Expected result:

- It no longer fails at `central daemon did not become ready`.
- If the web process stays foregrounded as designed, stop it manually after observing successful bind/start output.
- If another port conflict appears, rerun on an unused port and classify that separately.

Before this smoke, clear only confirmed local orphan daemon residue if still present and exactly tied to the old `.worktrees/fea-tool` central daemon command. This is environment hygiene, not a source fix.

## 禁止事项

- Do not restore `target_actor_address` handling in `central_daemon_core.py`.
- Do not keep both `actor_address_protocol` and `identity_reachability_protocol` success flags.
- Do not add a fallback that transforms actor address into identity id for readiness.
- Do not change browser cockpit/search_page contracts while fixing central daemon readiness.
- Do not edit projected runtime object storage under `buddyswitch/objects/**`.
- Do not treat local orphan daemon cleanup as proof that source is fixed.

## 验收清单

- `tests/test_central_daemon_service.py` has identity readiness behavior coverage.
- `tools/launcher/central_daemon.py` contains no actor-address readiness probe residue.
- temp shared-root `central_daemon.py start/status/request/stop` proves real process readiness and cleanup.
- scoped residue `rg` has no live-surface hits.
- launcher/browser cascade is rerun only after central daemon focused tests and temp process smoke pass.
- `./buddyswitch-codex web --port 8766` no longer fails at central daemon readiness.

## 计划文档自验收

This document is acceptable only if it contains:

- a task objective;
- core requirements;
- docs/bitter-derived rules;
- issue classification;
- current code facts;
- clean module boundaries;
- exact source/test files to modify;
- exact verification commands;
- explicit no-dual-track prohibitions.

Validation commands for this plan document:

```bash
rg -n "^## (任务目标|核心要求|docs/bitter 应用要点|关键问题归类|当前代码事实|架构边界|修复步骤|禁止事项|验收清单|计划文档自验收)" docs/memo/2026-07-07-central-daemon-identity-readiness-forward-repair-plan.md
rg -n "tools/launcher/central_daemon.py|tests/test_central_daemon_service.py|scripts/env/tool_runtime/daemon_client.py|python3 -m pytest|buddyswitch-codex web" docs/memo/2026-07-07-central-daemon-identity-readiness-forward-repair-plan.md
rg -n "T[B]D|T[O]DO|待[定]|placeholde[r]|以后[再]说" docs/memo/2026-07-07-central-daemon-identity-readiness-forward-repair-plan.md
```

Expected result:

- first command finds all required sections;
- second command finds concrete files and verification commands;
- third command has no output.
