# Instance Stop Browser Schedule Cleanup Plan

Date: 2026-07-04

## Goal

目标只有一个：

`instance stop` 在释放 instance browser 资源时，必须同步清理该 instance 下所有 browser-owned pending schedules。

## Scope Lock

本计划只处理这一条链路：

```text
buddyswitch-codex instance stop
-> instance_set_inactive_locked
-> buddyswitch_browser_manager_stop_instance
-> browser_runtime_manager.stop(force cleanup)
-> clear browser runtime resources and browser-owned pending schedules
```

明确不做：

- 不改 `search.open_browser`。
- 不改 `chrome-devtools-cockpit` 的 search action。
- 不碰 Task Sys、side-frame、parent handoff。
- 不处理 external Chrome kill 后的 stale status。
- 不处理 cockpit watchdog 短暂残留。
- 不用 status projection 隐藏问题。
- 不做双轨兼容，不保留新旧两套 cleanup 语义。

## Principles Read

已按要求阅读 `docs/bitter`，本任务采用以下约束：

- 修 owning layer，不靠 prompt 或 status 展示掩盖状态错误。
- 资源生命周期完成标准是 process、socket、marker、runtime state 和 host residual 都回到基线。
- 语义替换必须清 live surface 残留，不能留下仍会教旧语义的路径。
- 小改动也必须落在正确边界；不要在 shell/status 层加特殊遮罩。
- 用户可见 contract 必须端到端验证，不能只靠组件测试。

## Current Finding

当前自动 TTL 到期路径可工作：

- `cdp_browser_lifecycle.refresh_page_idle()` 创建 `browser.page.expired` schedule，并写入 `source_context={"owner":"browser"}`。
- `browser_page_expired_handler` 在页面 idle 到期时清 page idle target。
- tracked page 为空后会创建 `browser.cockpit.release` schedule，同样属于 browser owner。
- release 后 Chrome、`browser_port`、`page_idle.json` 可以被清理。

当前 `instance stop` 路径不完整：

- `buddyswitch-codex instance stop` 调用 `instance_set_inactive_locked`。
- `instance_set_inactive_locked` 先停 daemon，再停 app-server/runtime-broker，最后调用 `buddyswitch_browser_manager_stop_instance`。
- `buddyswitch_browser_manager_stop_instance` 调用 `browser_runtime_manager stop`。
- `browser_runtime_manager._release_engine()` 会清 Chrome、upstream markers、`page_idle.json`、`page_idle.lock`、`browser_port`。
- 但 `_release_engine()` 没有取消 daemon state 中 `source_context.owner == "browser"` 且 `status == "pending"` 的 schedules。

所以 stop 后会出现不一致：

```text
browser runtime resources: 已释放
browser-owned pending schedules: 仍残留
```

这不是 status 展示问题。根因是 `instance stop` 的 browser cleanup transaction 缺少 schedule cleanup。

## Correct Boundary

修复应落在 browser runtime manager 和 daemon schedule store 的交界处。

不应落在：

- `instance_status_json`：这会遮盖状态，不清理 live state。
- `browser_cockpit.sh` shell stop wrapper：这会把 browser lifecycle 语义散落到 shell。
- `browser_page_expired_handler`：它只处理 TTL 到期事件，不拥有 stop cleanup。
- `chrome_devtools_cockpit_proxy.py`：它是 browser tool surface/upstream adapter，不拥有 instance stop 事务。

应落在：

- `tools/launcher/daemon_core.py`：提供 schedule store 的通用取消能力。
- `tools/launcher/browser_runtime_manager.py`：在 release/stop cleanup transaction 中调用该能力，选择 owner=`browser`。

## Rebuild Target

`browser_runtime_manager.stop()` 必须成为完整 browser cleanup transaction：

1. discover current browser resources；
2. stop owned upstream/Chrome；
3. verify owned browser resources are gone；
4. clear browser runtime files and `browser_port`；
5. cancel all browser-owned pending schedules；
6. return structured result that exposes canceled schedule ids/count。

关键规则：

- `browser_port`、`chrome.pid`、`page_idle.json` 和 browser-owned schedules 都属于同一次 browser cleanup。
- pending schedule 不能在 stop 后继续保持 `pending`。
- delivered/failed/canceled historical schedules 不应被重写。
- non-browser schedules 不应被改动。
- 如果 process cleanup verification failed，应保留状态用于诊断，不抢先清 runtime files 或 schedules。

## Implementation Plan

### Step 1: Add a failing daemon schedule-store test

File:

- Modify `tests/test_daemon_core.py` or `tests/test_daemon_service_contract.py`.

Test intent:

- 新增通用 schedule store 行为：按 `source_context.owner` 取消 pending schedules。
- 只取消 `status == "pending"`。
- 不改 non-browser owner。
- 不改 delivered/failed/canceled rows。

Expected API shape:

```python
state.cancel_pending_schedules_by_source_owner("browser", now="2026-07-04T00:00:10Z")
```

Expected assertions:

- browser pending rows become `status == "canceled"`。
- `canceled_at` and `updated_at` are set。
- non-browser pending rows remain pending。
- delivered browser rows remain delivered。
- returned payload includes canceled schedule ids.

Focused command:

```bash
pytest tests/test_daemon_service_contract.py -k schedule -q
```

### Step 2: Implement generic daemon schedule cancellation

File:

- Modify `tools/launcher/daemon_core.py`.

Add method on `DaemonState` with this exact public signature:

```python
def cancel_pending_schedules_by_source_owner(self, owner: str, *, now: str | None = None) -> list[dict[str, Any]]
```

Required behavior:

- validate `owner` is non-empty string；
- iterate `scheduled_trigger_ids` in stable order；
- inspect `scheduled_triggers[schedule_id].source_context.owner`；
- only mutate rows whose `status` is `pending` and owner matches；
- set `status="canceled"`；
- set `updated_at` and `canceled_at` to the same timestamp；
- save once after mutation；
- return canceled rows as dict copies。

This is a daemon schedule-store primitive, not a browser special case.

Focused command:

```bash
pytest tests/test_daemon_service_contract.py tests/test_daemon_trigger_router.py -q
```

### Step 3: Add a failing browser manager unit test

File:

- Modify `tests/test_browser_runtime_manager.py`.

Test case:

```text
browser release/stop succeeds
and daemon state has pending browser.page.expired + browser.cockpit.release schedules
then both browser-owned pending schedules are canceled
and non-browser pending schedule is unchanged
```

Required assertions:

- release/stop result has `ok == True`。
- result includes canceled browser schedule ids/count。
- daemon state no longer has browser-owned schedules with `status == "pending"`。
- non-browser pending schedule remains pending。
- browser runtime cleanup assertions still pass: no `page_idle.json`, no `browser_port`, Chrome stopped。

Focused command:

```bash
pytest tests/test_browser_runtime_manager.py -q
```

### Step 4: Integrate schedule cleanup into browser release transaction

File:

- Modify `tools/launcher/browser_runtime_manager.py`.

Required shape:

- Import `daemon_core` safely from `tools/launcher` context.
- Add helper with this exact private signature:

```python
def _cancel_browser_owned_pending_schedules(instance_root: Path, actor_id: str) -> list[dict[str, Any]]
```

Helper behavior:

- read instance payload for `thread_id`；
- load `daemon_core.DaemonState` for the instance；
- call `cancel_pending_schedules_by_source_owner("browser")`；
- return canceled rows；
- if daemon state file does not exist, return empty list；
- invalid state should fail the release instead of silently claiming cleanup succeeded。

Release transaction placement:

- call schedule cancellation only after process verification succeeds；
- include it in the same success branch as `_clear_release_state()`；
- combine `state_changed` with whether schedules were canceled；
- include `canceled_browser_schedule_ids` and `canceled_browser_schedule_count` in the result。

Important edge:

- `force=True` stop must cancel browser-owned pending schedules even when ownership is `inactive` and no Chrome resources are recorded.
- That means `_release_engine()` cannot return early for `ownership == "inactive"` before considering browser-owned schedules in explicit cleanup mode.

Focused command:

```bash
pytest tests/test_browser_runtime_manager.py -q
```

### Step 5: Add CLI stop regression coverage

File:

- Modify `tests/test_buddyswitch_launcher.py`.

Test intent:

`buddyswitch-codex instance stop "${ctx['actor_id']}" --json` must leave no browser-owned pending schedules in the fixture instance.

Setup:

- start a service instance using existing helper；
- seed daemon state with:
  - pending `browser.page.expired`, `source_context={"owner":"browser"}`；
  - pending `browser.cockpit.release`, `source_context={"owner":"browser"}`；
  - pending non-browser schedule, `source_context={"owner":"task"}`；
- do not seed Chrome for this CLI test; this verifies `force=True` stop cancels browser schedules even when runtime resources are already inactive；
- run `buddyswitch-codex instance stop "${ctx['actor_id']}" --json`。

Assertions:

- stop returns inactive JSON；
- browser-owned schedules are canceled；
- non-browser pending schedule is still pending；
- existing browser runtime cleanup assertions remain true。

Focused command:

```bash
pytest tests/test_buddyswitch_launcher.py -k "stop and browser" -q
```

### Step 6: Run focused and relevant verification

Required commands:

```bash
pytest tests/test_daemon_service_contract.py tests/test_daemon_trigger_router.py -q
pytest tests/test_browser_runtime_manager.py -q
pytest tests/test_buddyswitch_launcher.py -k "stop and browser" -q
```

Manual CLI smoke, after automated tests pass:

```bash
actor_id="$(
  ./buddyswitch-codex instance start --role market --json \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["actor_id"])'
)"
./buddyswitch-codex instance input "${actor_id}" \
  --text "请只使用 chrome-devtools-cockpit 打开一个 browser page，然后 list_pages/select_page/take_snapshot；不要调用 search.open_browser 或 search 工具。" \
  --json
./buddyswitch-codex instance status "${actor_id}" --json
./buddyswitch-codex instance stop "${actor_id}" --json
./buddyswitch-codex instance status "${actor_id}" --json
./buddyswitch-codex instance delete "${actor_id}" --yes --json
```

Manual acceptance checks:

- no actor-owned Chrome process；
- no `runtime/browser/page_idle.json`；
- `instance.json.browser_port == null`；
- no browser-owned schedule remains with `status == "pending"`；
- no test actor remains listed。

## Acceptance Criteria

The task is complete only when all are true:

- `instance stop` cancels all pending schedules whose `source_context.owner == "browser"`。
- `instance stop` does not cancel non-browser pending schedules。
- browser runtime cleanup still clears Chrome/upstream markers/page idle/browser port。
- failed browser process cleanup does not falsely clear schedule state as if cleanup succeeded。
- tests prove both manager-level behavior and real CLI stop behavior。
- no search, task dispatch, cockpit search action, or status projection changes are included.

## Plan Validation Checklist

- Single target: yes, only `instance stop` browser-owned pending schedule cleanup.
- Correct boundary: yes, daemon schedule store primitive plus browser manager transaction.
- No residue: pending browser schedules are canceled as live state, not hidden in status.
- No dual-track compatibility: yes, one release/stop transaction owns cleanup.
- No scope drift: search/task/external-kill/watchdog are explicitly excluded.
- Test-bound: unit and CLI stop regression tests are required before completion.
