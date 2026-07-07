# Browser Failed Open Residue Cleanup Plan

Date: 2026-07-07
Status: planning only; no implementation in this memo.

## 任务目标

消除 `chrome-devtools-cockpit.new_page` 和 `chrome-devtools-cockpit.search_page` 在打开失败、导航超时、或返回结果不可交付时产生的未托管浏览器页面残留。

核心不变量：

```text
在 failed/undeliverable open-page 工具结果返回给 actor 之前，本次调用创建的每一个 Chrome page target 必须已经被关闭，或者已经进入精确的 BuddySwitch 清理路径。
```

不能再出现这种状态：

```text
Chrome 里存在真实 page target
actor 没有拿到可用页面
page_idle 没有 TTL 记录
cleanup schedule 没有精确记录
release 又因为 real_user_page_present 拒绝释放浏览器
```

这次改造目标不是优化页面加载等待策略，也不是重新设计 browser session。目标只聚焦一个产品语义：

```text
失败打开不能留下脱离 BuddySwitch 管理的真实页面。
```

## docs/bitter 应用要点

- `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`：浏览器相关测试必须证明资源回到基线，不能只证明返回值断言通过。
- `docs/bitter/2026-06-25-end-to-end-contract-slice-principles.md`：验收必须覆盖 actor 调用失败、目标清理、release 不再被该残留永久阻塞的完整链路。
- `docs/bitter/2026-07-07-guarded-residue-boundary-principles.md`：不能加一层 guard 后继续接受错误状态；要定义新的准确边界。
- `docs/bitter/2026-06-02-residue-cleanup-principles.md`：需要 behavior proof 和 live-surface residue scan，两者都要有。
- `docs/bitter/2026-05-18-tool-skill-layering-principles.md`：修工具契约和反馈，不靠 prompt、AGENTS 或 actor 自觉规避。
- `docs/bitter/2026-06-02-wrong-boundary-narrowness-principles.md`：generic daemon 只保留调度能力；浏览器失败打开语义属于 browser owning code。
- `docs/bitter/2026-06-25-built-in-product-interface-principles.md`：browser lifecycle 是产品内建能力，tool response 只是投影，不能让 runtime 真相散落在外部提示里。
- `docs/bitter/2026-05-28-parallel-change-boundary-principles.md`：本计划只处理 failed-open residue，不混入 timeout 策略、页面复用、release 策略重构等旁支。

## 已确认问题

这次 `act-market-a59020d3460d` 的问题归类是：

```text
new_page navigation timeout / registration failure path
```

不是 profile/session restore、旧会话残留，也不是 raw CDP only 的 cockpit 不可见页面。

已确认事实：

1. upstream `chrome-devtools-mcp` 的 `new_page` 会先创建 tab，再执行 `page.goto(...)`。
2. `Navigation timeout of 10000 ms exceeded` 只表示 upstream tool 没有在 10s 内完成它定义的导航等待并返回正常结果，不表示 Chrome 没有创建页面。
3. 本次失败调用创建的 etnet/Yahoo Finance 页面在后续 upstream MCP/cockpit 页面列表里可见，不只是 raw CDP 可见。
4. BuddySwitch daemon schedule 中没有这些失败创建页的 page id。
5. `page_idle` 为空后触发 browser release，但 release handler 又通过 raw CDP `/json/list` 看到真实页面，于是跳过 release：`real_user_page_present`。
6. 结果是 failed-open 页面既不受 TTL 管理，也阻止浏览器最终释放。

当前 live path 的准确缺口：

```text
open attempted
-> Chrome target created
-> upstream result isError 或 BuddySwitch 无法解析 selected page id
-> proxy 不登记、不关闭、不调度清理
-> TTL 看不到该页
-> release 看到真实页后保守跳过
```

## 当前代码事实

### `tools/launcher/chrome_devtools_cockpit_proxy.py`

当前职责：cockpit 工具代理、`search_page`/`new_page` 改写、actor-visible response patch、TTL idle state registration。

关键事实：

- `search_page` 和 `new_page` 会转发到 upstream MCP `new_page`，并设置 `background=true`。
- `_tool_response_succeeded()` 只把 `result.isError is not True` 当成功。
- `patch_tool_response_page_use_metadata()` 在 upstream 返回 `isError: true` 时直接返回原始错误 response。
- 成功路径只在解析到 `[selected]` page id 后登记 normal page idle。
- 成功文本里如果没有 selected page id，目前只追加 warning，不关闭真实 target，也不调度清理。
- 当前代码没有围绕单次 open attempt 做 pre/post target diff。

这是最主要的 owning module。失败打开的 cleanup decision 必须在这里发生，不能推给 actor，也不能等 release 碰运气。

### `scripts/env/cdp_background_page.py`

当前职责：低层 browser websocket CDP helper，已有 `Target.createTarget` 能力用于非激活 readiness，不是 normal actor page lifecycle。

计划中它只应新增或承载最小 `Target.closeTarget` primitive。这个 primitive 的边界必须清楚：

```text
只服务 failed-open residue cleanup，不成为普通页面打开、复用、选择、TTL 的入口。
```

### `scripts/env/cdp_browser_lifecycle.py`

当前职责：browser lifecycle 常量、page idle state、schedule helper、CDP page target listing。

计划中它可以承载 failed-open cleanup 的 schedule 常量和 helper，但不能把 CDP target id 写进 normal `page_idle.pages`，也不能把 failed-open target 伪装成 current/selected page。

### `tools/launcher/browser_page_expired_handler.py`

当前职责：处理 browser-owned lifecycle schedule。

现状中 normal `browser.page.expired` 只关闭记录在 `page_idle` 里的 MCP page id，并通过 upstream MCP `close_page` 执行。

计划中可以让它处理一个新的 cleanup-only trigger，但必须保持边界：

```text
normal TTL expiry: MCP page id -> upstream MCP close_page
failed-open cleanup: CDP target id -> low-level CDP close target
```

这不是双轨兼容，因为两条路径处理的是不同状态形态：一个是已交付、已登记页面；一个是未交付、未登记残留。

### `tools/launcher/browser_release_handler.py`

当前职责：最终浏览器释放。

它现在通过 raw CDP `/json/list` 判断是否还有真实页面，并在 `real_user_page_present` 时跳过 release。这一保守行为本身不是根因；根因是 failed-open residue 在进入 release 之前没有被关闭或登记。

计划中 release 仍是最后释放边界，不作为 failed-open 的第一修复点。

## 产品契约

### 成功打开

当 upstream `new_page` 返回成功，并且 BuddySwitch 能解析出 `[selected]` page id：

- 继续使用现有正常路径；
- selected/current truth 是 upstream MCP page id；
- 继续登记 normal `browser.page.expired` TTL；
- 不把 CDP target id 引入 normal page identity；
- 不使用 pre/post CDP diff 干预成功打开。

### 失败打开

当 upstream `new_page` 或由 `search_page` 改写来的 upstream `new_page` 返回 `isError: true`：

- actor 不应获得可继续使用的页面；
- BuddySwitch 必须判断本次调用是否创建了新的 Chrome page target；
- 对新 target 立即执行 cleanup decision；
- 能关闭则在返回 actor 之前关闭；
- 不能关闭则登记精确 cleanup schedule；
- actor feedback 必须保留 upstream error，并追加 BuddySwitch 的清理结果。

### 不可交付成功

当 upstream 返回 nominal success，但 BuddySwitch 无法解析 selected page id：

- 该结果对 BuddySwitch lifecycle 来说不可交付；
- 不登记 fake current page；
- 不把页面留给 actor 继续使用；
- 如果本次调用新增了 target，按 failed-open residue 处理；
- response 里明确说明 page id 不可读、页面未登记、清理已完成或已进入清理队列。

## 架构目标

### 单一路径

正常页面只有一条 owning path：

```text
upstream MCP new_page success
-> parse selected MCP page id
-> register normal page idle TTL
-> expire through upstream MCP close_page
```

失败残留只有一条 owning path：

```text
failed or undeliverable open result
-> pre/post CDP target diff
-> close exact new CDP target
-> close failed then schedule exact cleanup
```

两者不共享 identity，也不互相兜底成对方的模型。

### 无双轨兼容

本计划明确禁止：

- 恢复本地 CDP actor page opening；
- 恢复 open/reuse/page-count gate；
- 成功打开同时维护 MCP page id 和 CDP target id 两套 current truth；
- 把 failed-open target 写入 normal `page_idle.pages`；
- 用 release handler 作为 failed-open 的主要清理机制；
- 通过 prompt 或 actor 侧约定要求失败后手动 close。

### 无残留

改造完成后，任何 failed/undeliverable `new_page/search_page` 必须落入三种终态之一：

1. 没有创建新 target；
2. 创建了新 target，并在 response 返回前被关闭；
3. 创建了新 target，立即关闭失败，但有精确 cleanup schedule 接管。

第三种不是允许残留，而是受管清理状态。它必须短 TTL、精确 target、可重试、可验证、可升级到最终 sweep/release。

## 设计路径

### Step A: 捕获单次调用前置视图

只对 `new_page` 和 `search_page` 执行：

```text
pre_open_page_targets = CDP /json/list filtered to type=page
```

这个读取只服务失败清理，不服务：

- page-count 限流；
- 页面复用；
- 本地打开；
- 成功页面登记；
- actor-visible page selection。

旧测试中如果断言 "`new_page` 前不能读取 `/json/list`"，需要更新为更准确的边界：

```text
允许 cleanup-only pre-open snapshot；
禁止 page-count gate、local open、reuse、block。
```

### Step B: 判断响应是否可交付

可交付条件：

```text
result.isError is not True
AND response text contains parseable selected MCP page id
```

不可交付条件：

```text
result.isError is True
OR selected MCP page id cannot be parsed
```

不可交付不等于页面未创建。不可交付只表示 actor 不能获得一个 BuddySwitch 已登记、可 TTL 管理的页面。

### Step C: 对不可交付结果做 post diff

不可交付后读取：

```text
post_open_page_targets = CDP /json/list filtered to type=page
new_failed_targets = post ids - pre ids
```

`new_failed_targets` 默认归属本次失败调用。这里的归因是合理的，因为 diff 只围绕单次 tool call 的短时间窗口，并且只在该 tool call 不可交付时使用。

### Step D: 立即关闭新 target

对每个 `new_failed_target`：

```text
Target.closeTarget(targetId=<new target id>)
```

关闭成功后，在 actor response 中追加类似反馈：

```text
Browser cleanup: the failed open created 1 unmanaged page target; BuddySwitch closed it before returning this error.
```

反馈要求：

- 不吞掉 upstream error；
- 明确说页面打开失败或超时；
- 明确说系统检测到新 tab 已创建；
- 明确说未管理 tab 已关闭；
- 提示可稍后重试，或在后续单独优化 timeout 策略后使用更合适的 timeout。

### Step E: 关闭失败时登记精确 cleanup

如果 immediate close 失败，不能忽略，也不能只依赖 release。

最直接、最可靠的降级路径是：

```text
登记 exact target cleanup schedule
```

推荐 trigger：

```text
type: browser.failed_open_page.cleanup
schedule_key: browser.failed_open_page.cleanup:<target_id>
payload:
  target_id: <cdp target id>
  url: <target url if known>
  attempts: <integer>
  first_seen_at: <timestamp>
  reason: failed_open_page
```

actor feedback 追加类似内容：

```text
Browser cleanup warning: the failed open created an unmanaged page target, immediate close failed, and BuddySwitch scheduled short cleanup for it.
```

为什么不是直接 browser release：

- exact target cleanup 范围最小，只处理本次失败创建页；
- release 是进程级动作，会受其它真实页面影响；
- release 当前设计上会因为 `real_user_page_present` 保守跳过，不能作为首选修复；
- exact cleanup 成功后，release 自然不再被这个 target 阻塞。

release/sweep 只作为 attempts exhausted 后的最终升级路径。

### Step F: cleanup-only handler

handler 行为：

1. 读取当前 CDP page targets。
2. 如果 `target_id` 已不存在，标记 handled。
3. 如果 `target_id` 存在，调用 low-level CDP close primitive。
4. close 成功则标记 handled。
5. close 失败且 attempts 未耗尽，短延迟 reschedule 同一个 target。
6. attempts 耗尽后，记录清晰日志，并触发 browser-owned sweep/release check。

handler 不能：

- 把 target 登记为 normal page；
- 设置 current/selected page；
- 调 upstream MCP `close_page` 关闭 CDP target；
- 静默吞掉最后失败。

## 模块边界

| 模块 | 应做 | 不应做 |
| --- | --- | --- |
| `chrome_devtools_cockpit_proxy.py` | open tool contract、pre/post diff、响应可交付判断、cleanup decision、actor feedback | 本地打开 actor 页面、页面复用、page-count gate、维护 CDP current truth |
| `cdp_background_page.py` | 提供最小 `Target.closeTarget` primitive | 成为 normal page lifecycle API |
| `cdp_browser_lifecycle.py` | 常量、target listing、cleanup-only schedule helper | 把 failed target 写进 normal `page_idle.pages` |
| `browser_page_expired_handler.py` | 处理 cleanup-only trigger；保留 normal TTL close_page 行为 | 用 CDP close 关闭普通 tracked page |
| `browser_release_handler.py` | 最终释放浏览器；处理最后 sweep/release | 作为 failed-open 的首选 cleanup |
| tests | 锁定行为、端到端契约、live-surface residue scan | 只测 mock 返回值、不证明残留消失 |

## 测试计划

### Proxy focused tests

文件：`tests/test_browser_cockpit_proxy.py`

新增或替换测试：

1. `test_failed_new_page_closes_new_cdp_page_target_and_reports_cleanup`
   - pre `/json/list` 只有既有页面；
   - upstream `new_page` 返回 `isError: true`；
   - post `/json/list` 多一个 target；
   - 断言只 close 新 target；
   - 断言 response 保留 upstream error，并包含 cleanup feedback。

2. `test_failed_search_page_closes_new_cdp_page_target_and_reports_cleanup`
   - 通过 `search_page` 触发；
   - 保留 search URL rewrite 到 upstream MCP `new_page` 的断言；
   - 断言 cleanup 绑定的是新 target。

3. `test_new_page_without_selected_page_id_closes_new_target_and_reports_not_deliverable`
   - upstream 返回 success-like text，但没有 `[selected]`；
   - post `/json/list` 出现新 target；
   - 断言 close 或 precise cleanup schedule；
   - 断言 response 说明 page id 不可读、页面未登记。

4. `test_failed_new_page_close_failure_schedules_precise_cleanup`
   - CDP close primitive 抛错或返回失败；
   - 断言存在 `browser.failed_open_page.cleanup:<target_id>` schedule；
   - 断言 response 说明已进入清理队列。

5. 更新旧边界测试：
   - 保留 "`new_page` 不 block、不复用、不本地打开"；
   - 删除或替换 "`new_page` 绝不能读取 `/json/list`"；
   - 新断言为 "最多允许 cleanup-only snapshot，且 response 不出现 page-count hint/local gate"。

### CDP helper tests

覆盖 low-level close primitive：

- `Target.closeTarget` 使用精确 target id；
- CDP error 转成清晰异常；
- websocket 关闭、malformed response 不挂死；
- 不引入 `Target.createTarget` actor page use 回路。

### Cleanup handler tests

覆盖 cleanup-only trigger：

- target 已不存在时成功 handled；
- target 存在且 close 成功时成功 handled；
- close 失败且 attempts 未耗尽时 reschedule 同一个 target；
- attempts 耗尽时触发 browser-owned sweep/release check，并有清晰日志。

### End-to-end contract slice

必须有一条端到端验收测试：

```text
actor failed new_page
-> Chrome creates target
-> proxy returns failure with cleanup feedback
-> target no longer present OR exact cleanup schedule exists
-> browser release is not permanently blocked by that failed target
```

这是产品验收主线。只靠 proxy unit test 不够。

### Residue checks

增加 scoped live-surface scan，目标是证明没有双轨残留：

- normal page idle path 不存 CDP target id 作为 current/selected truth；
- `browser_page_expired_handler.py` 不用 `Target.closeTarget` 关闭 ordinary tracked page；
- `chrome_devtools_cockpit_proxy.py` 不恢复 local CDP open/reuse/page-count gate；
- failed-open cleanup 术语只出现在 owning code、tests、tool feedback；
- 历史 `docs/memo` 不作为 residue cleanup target。

## 验证命令

Focused tests：

```bash
python -m unittest tests.test_browser_cockpit_proxy
python -m unittest tests.test_cdp_browser_session
python -m unittest tests.test_browser_page_expired_handler
```

Release/lifecycle tests：

```bash
python -m unittest tests.test_browser_runtime_manager tests.test_browser_lazy_release_integration
```

Repo consistency：

```bash
python -m unittest tests.test_repo_consistency
```

Manual residue scan：

```bash
rg -n "Target\\.closeTarget|close_target|failed_open_page|pre_open_page_targets|page-count|open_or_reuse_page|current_target_id|page_id_to_target_id" \
  tools/launcher scripts/env tests/test_browser_cockpit_proxy.py tests/test_browser_page_expired_handler.py tests/test_repo_consistency.py
```

期望：

- `Target.closeTarget` 只出现在 low-level CDP helper、cleanup owner、以及相关测试；
- normal page idle 和 release path 不用 CDP close 处理普通 tracked page；
- live proxy code 不出现旧 browser-session/local open/reuse/page-count gate。

Resource residual check：

```bash
ps -axo pid,ppid,pgid,command | rg "chrome_devtools_cockpit_proxy|chrome-devtools-mcp|fake-chrome|buddyswitch.*browser" || true
```

期望：

- focused/integration test run 后没有本轮测试拥有的进程残留；
- 若存在测试前已有的 long-lived product service，必须明确标注并排除。

## 实施顺序

1. 先写 proxy focused failing tests：failed `new_page`、failed `search_page`、selected id missing、close failure fallback。
2. 运行 focused tests，确认失败点是 cleanup 缺失，而不是 mock 或 fixture 写错。
3. 在 `cdp_background_page.py` 增加最小 `Target.closeTarget` primitive。
4. 在 proxy 中增加 cleanup-only pre-open snapshot、不可交付判断、post diff、immediate close。
5. 增加 exact cleanup schedule helper 和 cleanup-only handler path。
6. 替换旧的 "no CDP read before new_page" 测试口径，保留更强的 "no local open/reuse/block" 口径。
7. 跑 focused proxy/helper/handler tests 到绿。
8. 增加端到端 contract slice。
9. 增加 scoped residue scan 或 repo consistency test。
10. 跑完整验证命令和资源残留检查。

## 验收标准

- failed `new_page` 不能在 response 返回后留下 unmanaged target。
- failed `search_page` 同样不能留下 unmanaged target。
- selected page id 不可解析时，不能留下未登记页面。
- actor feedback 同时包含 upstream failure 和 BuddySwitch cleanup outcome。
- immediate close 失败时必须创建 exact target cleanup schedule。
- normal successful open 仍只使用 upstream MCP page id 作为 current/selected/TTL truth。
- normal TTL expiry 仍通过 upstream MCP `close_page` 关闭 tracked MCP page。
- release 不再是 failed-open residue 的首选修复路径。
- live-surface scan 证明没有恢复 local CDP open/reuse/page-count 双轨。
- 启动服务的测试结束后没有本轮测试拥有的进程残留。

## 关键审查问题

实施前后都必须逐项回答：

1. 每个 undeliverable `new_page/search_page` response 返回 actor 前，是否已经有 cleanup decision？
2. cleanup target set 是否只包含本次调用后新增的 page targets？
3. close failure 是否进入受管 cleanup state，而不是被日志吞掉？
4. CDP target id 是否只用于 failed-open cleanup，不参与 normal page identity？
5. `browser_release_handler.py` 是否仍是最终释放边界，而不是清理拐杖？
6. tests 是否覆盖 proxy、cleanup handler、release-visible outcome 的完整链路？
7. residue scan 是否能防止旧 local CDP open/reuse/page-count path 回来？

## 计划自检

本计划覆盖的确认失败类是：

```text
upstream new_page does not return a deliverable selected page
-> Chrome target exists
-> no TTL ledger entry
-> release can be blocked
```

本计划是前进式改造，不是兼容叠层：

- normal open 只有 upstream MCP success + selected MCP page id 一条路径；
- failed-open residue 只有 exact CDP target cleanup 一条路径；
- close failure 是 cleanup-owned short TTL state，不是 unmanaged residue；
- 不让 actor 继续使用 failed-open page；
- 不恢复 local CDP page opening；
- 不靠 prompt 规避；
- 不把 release handler 当第一修复点。
