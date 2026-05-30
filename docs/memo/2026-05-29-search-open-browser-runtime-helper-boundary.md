# Search Open Browser Runtime Helper Boundary Repair Memo

Date: 2026-05-29
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill`
Branch: `fea-skill`
Status: repair task confirmed, implementation not started in this memo

## 背景

上一轮 browser focus repair 已经把 BuddySwitch-owned 直接 `/json/new` 开页路径改成了 CDP `Target.createTarget` 且 `background: true`。

目标方向是对的：避免 BuddySwitch 自动打开浏览器页面时抢前台焦点。

但真实 product runtime session 暴露了一个新问题：`search.open-browser` 在 market buddy 内失败，报缺少：

```text
tools/launcher/cdp_background_page.py
```

同时，`chrome-devtools-cockpit` 仍然能连上浏览器并检查已有页面。这说明问题不是浏览器整体不可用，而是 `search.open-browser` 自动搜索/打开新页入口坏了。

## 准确问题

`search.open-browser` 是 runtime env tool，运行位置是 product instance 的 runtime workspace，例如：

```text
/Users/chen/.codex-buddyswitch/instances/<instance-id>/workspace
```

这个 workspace 是 sparse 投影，只包含 runtime 需要的受控文件，例如：

```text
scripts/env/
scripts/runtime_kernel/
scripts/turn_runtime.py
scripts/env_store.py
scripts/env_legacy_store.py
scripts/env_manifest.py
scripts/env_profiles.py
scripts/browser_evidence.py
buddyswitch/manifest.toml
buddyswitch/env-profiles/
framework/contracts/
```

`tools` 明确属于 execution workspace forbidden entries，不会被投影进 product runtime workspace。

当前实现里，`scripts/env/tools/search/_impl.py` 的 `_open_browser_page` 依赖：

```text
env_profiles.ROOT / "tools" / "launcher" / "cdp_background_page.py"
```

在源码 worktree 中，这个文件存在。但在真实 runtime workspace 中，`env_profiles.ROOT` 指向 instance workspace，而该 workspace 没有 `tools/launcher/`，所以 `search.open-browser` 找不到 helper 并失败。

## 为什么 `chrome-devtools-cockpit` 还能用

`chrome-devtools-cockpit` 的 MCP 配置指向源码 worktree 的绝对路径，例如：

```text
/Users/chen/Dev/buddyswitch/.worktrees/fea-skill/tools/launcher/chrome_devtools_cockpit_proxy.py
```

它不依赖 runtime workspace 中是否存在 `tools/launcher/`。

所以现象不矛盾：

- `chrome-devtools-cockpit` 可以检查当前浏览器页面；
- `search.open-browser` 不能自动打开新的搜索页；
- 根因是两个入口的文件解析边界不同。

## 设计判断

`search.open-browser` 本质上是 runtime env tool，不应该依赖 launcher-only 的 `tools/launcher/**`。

`tools/launcher/**` 属于启动器和主源码 worktree 能力，不属于 buddy runtime sparse workspace 能力。把 runtime env tool 的运行时依赖放进 `tools/launcher`，会导致源码测试通过但 product instance 失败。

更合理的边界是：

- `scripts/env/**` 放 runtime env tool 及其运行时依赖；
- `tools/launcher/**` 放 launcher orchestration、实例启动、MCP 注册、浏览器生命周期管理；
- launcher 可以调用 `scripts/env/**` 中的共享小工具；
- runtime env tool 不应反向依赖 `tools/launcher/**`。

## 修复方案

推荐修复：把 CDP background page helper 迁到 runtime sparse 已包含的 `scripts/env/` 下。

目标路径：

```text
scripts/env/cdp_background_page.py
```

然后统一调整调用方：

1. `scripts/env/tools/search/_impl.py`
   - 从 `env_profiles.ROOT / "tools" / "launcher" / "cdp_background_page.py`
   - 改为 `env_profiles.ROOT / "scripts" / "env" / "cdp_background_page.py"`
   - 保持 `search.open-browser` 对外返回契约不变。

2. `tools/launcher/browser_cockpit.sh`
   - 默认 helper 路径也改为：

```text
${BUDDYSWITCH_REPO_ROOT}/scripts/env/cdp_background_page.py
```

   - launcher ready-page repair 仍走 `Target.createTarget(background: true)`。

3. `tools/launcher/cdp_background_page.py`
   - 推荐删除，避免两个 helper 路径长期并存。
   - 如有短期兼容需要，也只能做极薄 wrapper，但当前 SHARP 判断不建议保留 dual path。

## 不推荐的方案

### 不推荐把 `tools/launcher/` 加进 runtime sparse workspace

原因：

- 扩大 runtime workspace 暴露面；
- 违反现有 workspace sparse 边界；
- 会把 launcher-only 文件带进 buddy runtime；
- 为一个小 helper 引入过大投影范围。

### 不推荐让 `search.open-browser` 继续依赖源码 worktree 绝对路径

原因：

- product runtime tool 应该能在自己的 sparse workspace 内解释依赖；
- 依赖外部源码路径会让实例可移植性、测试隔离和权限边界变差；
- 和 env runtime 基本位于 `scripts` 体系内的设计不一致。

### 不推荐删除 `search.open-browser` 作为本次修复

`search.open-browser` 确实和浏览器 MCP 有能力重叠，但当前 `chrome-devtools-cockpit` 暴露工具不等价于完整浏览器导航代理。

本次任务是修复已存在入口，不是重新设计 market browser discovery 模型。是否删除 `search.open-browser` 应另起设计讨论。

## 测试计划

测试要补上上一轮遗漏的 runtime sparse 边界。

### 1. Search runtime source-shape test

修改 `tests/test_search_env_tool.py` 中现有 source-shape 断言。

目标断言：

- `scripts/env/tools/search/_impl.py` 不包含 `/json/new`；
- `scripts/env/tools/search/_impl.py` 不引用 `tools/launcher`；
- `scripts/env/tools/search/_impl.py` 引用 `scripts/env/cdp_background_page.py`；
- `scripts/env/cdp_background_page.py` 存在。

这个测试应先红：当前实现仍引用 `tools/launcher/cdp_background_page.py`。

### 2. Search behavior tests

保留并跑现有 fake CDP websocket tests：

- `search.open-browser` 不调用 `/json/new`；
- 通过 websocket 发送 `Target.createTarget`；
- `params.url` 等于搜索目标 URL；
- `params.background is True`；
- browser open 失败时仍返回 `E_SEARCH_BROWSER_OPEN_FAILED`，并保留 `target_url` 和 `browser_endpoint`。

这些测试验证行为，不只验证字符串。

### 3. Launcher source-shape tests

更新 `tests/test_browser_cockpit_launcher.py`。

目标断言：

- `tools/launcher/browser_cockpit.sh` 默认 helper 指向 `scripts/env/cdp_background_page.py`；
- 不再引用 `tools/launcher/cdp_background_page.py`；
- 不包含 `/json/new?about:blank`；
- `chrome-devtools-cockpit` proxy 注册仍保留。

### 4. Broader launcher tests

更新 `tests/test_buddyswitch_launcher.py` 中与 ready-page repair 相关的断言。

目标行为保持不变：

- endpoint-only browser 修复失败时，Codex 不启动；
- intro-only browser repair 时，先创建 background target，再继续 MCP/Codex setup；
- 不调用 `/json/new?about:blank`；
- fake background helper 记录的是 `Target.createTarget` 且 `background: true`。

### 5. Runtime sparse boundary test

在 workspace 相关测试中补一个边界断言。

目标断言：

- execution sparse paths 包含 `scripts/env/`；
- execution forbidden entries 包含 `tools`；
- `search.open-browser` 依赖的 helper 位于 `scripts/env/` 下；
- helper 不位于 forbidden 的 `tools/` 下。

这能防止以后再次把 runtime env tool 依赖放回 launcher-only 路径。

## 推荐验证顺序

先跑 focused red：

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
```

实现后跑 focused green：

```bash
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_source_has_no_direct_json_new_page_open -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_creates_background_cdp_target -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_encodes_queries_for_supported_engines -v
python3 -m unittest tests.test_search_env_tool.SearchEnvToolTests.test_search_open_browser_reports_cdp_open_failure_with_target_url -v
```

然后跑相关 suites：

```bash
python3 -m unittest tests.test_search_env_tool -v
python3 -m unittest tests.test_browser_cockpit_launcher -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_repairs_intro_only_browser_before_codex_launch -v
python3 -m unittest tests.test_buddyswitch_launcher.BuddySwitchLauncherTests.test_start_with_required_buddy_rejects_endpoint_only_browser_before_codex -v
```

最后做 runtime product smoke check：

```bash
./buddyswitch-codex instance start --buddy market --json
python3 scripts/env/client.py search open-browser --payload '{"query":"creator analytics pain","engine":"google"}'
```

第二条命令应在新 market instance workspace 内执行，或者通过 instance input 触发，以确认真实 sparse workspace 不再缺 helper。

## 资源约束

继续遵守 `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md`。

测试原则：

- focused tests 优先；
- 不在 unit tests 中启动真实 Chrome、真实 Codex、daemon、app-server；
- fake CDP server、fake helper、fake subprocess 必须由测试完整拥有生命周期；
- broad launcher suite 前后做残留进程检查。

建议残留检查：

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

## 验收标准

修复完成必须同时满足：

1. `search.open-browser` 在真实 product runtime sparse workspace 中不再报缺 `tools/launcher/cdp_background_page.py`。
2. `search.open-browser` 仍用 `Target.createTarget(background: true)` 打开搜索页。
3. `search.open-browser` 不回退到 `/json/new`。
4. launcher ready-page repair 不回退到 `/json/new?about:blank`。
5. runtime env tool 不依赖 `tools/launcher/**`。
6. `chrome-devtools-cockpit` proxy 保持现有注册和焦点保护。
7. focused tests 和相关 launcher tests 通过。
8. 工作区资源没有留下 fake Chrome、fake upstream、broker、app-server 测试残留。

## 当前结论

本次修复任务不是重新设计 browser discovery，也不是删除 `search.open-browser`。

当前最小正确修复是：把 CDP background target helper 移到 `scripts/env/`，让 search runtime 和 launcher 都调用 runtime 可见的同一个 helper，并用测试锁住 `search.open-browser` 不再依赖 forbidden `tools/launcher` 路径。
