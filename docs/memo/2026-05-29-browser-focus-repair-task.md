# Browser Focus Repair Task Memo

Date: 2026-05-29
Worktree: `/Users/chen/Dev/buddyswitch/.worktrees/fea-skill`
Current branch: `fea-skill`

## 任务目标

本次修复的核心目标是：

让 BuddySwitch 自己控制的 headed browser 浏览路径默认不抢用户当前前台焦点，同时继续保留真实浏览器能力，不退回 headless。

这里的 headed browser 是必要能力，因为很多深度浏览、登录态、社交网站、动态界面和复杂交互场景无法稳定依赖 headless。目标不是取消浏览器，而是把 BuddySwitch 管理的浏览器入口收口到非激活、少打扰的路径上。

## 关键边界

本任务只承诺 BuddySwitch-owned 路径：

- launcher 初始化浏览器和 MCP 的路径；
- BuddySwitch search tool 打开浏览器页面的路径；
- `chrome-devtools-cockpit` 暴露给 Codex 的 MCP 路径；
- 相关测试和文档。

## 硬性范围锁

本次修复必须写死在以下范围内：

- `tools/launcher/**`
- `scripts/env/tools/search/**`
- 与上述行为直接相关的 `tests/**`
- `docs/spec/**` 和 `docs/memo/**`

除非用户重新明确授权扩大范围，否则禁止修改以下层：

- skill 层；
- daemon 层；
- runtime actor profile；
- auth / permission 核心层；
- runtime broker / app-server 主协议；
- buddy profile / role contract。

如果实现过程中发现必须触碰上述禁止范围，当前任务应停止并回报原因，不允许自行外溢。

本任务不承诺覆盖任意外部逃逸路径，例如：

- Codex 或用户手动通过 shell 调 `curl http://127.0.0.1:9222/json/new?...`；
- 其它未由 BuddySwitch 包装的 browser MCP；
- 用户手动操作浏览器窗口；
- 系统窗口管理器或 Chrome 自身不可控的少数平台行为。

如果以后需要覆盖这些逃逸路径，应该另起一阶段评估更底层的 CDP proxy、port guard 或权限收口，而不是把当前任务扩成平台级权限系统。

## 已完成的第一阶段

已提交：

```text
5689f9d Avoid browser focus stealing in cockpit
```

第一阶段完成的是 `chrome-devtools-cockpit` MCP 入口收口：

- `chrome-devtools-cockpit` 仍保持 Codex 可见的同名 MCP server；
- launcher 不再直接注册 raw `chrome-devtools-mcp`；
- launcher 改为注册 BuddySwitch-owned proxy：
  - `tools/launcher/chrome_devtools_cockpit_proxy.py`
  - upstream 固定为 `chrome-devtools-mcp@1.1.1`
  - browser URL 仍通过 `--browser-url` 传给 upstream；
- proxy 透明转发大多数 MCP JSON-RPC；
- proxy 拦截焦点敏感行为：
  - `new_page` 强制 `background: true`；
  - `select_page` 强制 `bringToFront: false`；
  - `new_page` 携带 `isolatedContext` 时直接返回 MCP tool error，不转发；
  - `Page.bringToFront` / `Target.activateTarget` 这类能力被阻断或门控；
  - `tools/list` 返回里补充 BuddySwitch 非激活行为说明；
- 测试覆盖了 proxy 行为、launcher 注册、stale raw MCP config repair、相关 broader launcher 断言。

这一阶段的重点是：Codex 通过 `chrome-devtools-cockpit` 使用浏览器时，不能再直接绕到 raw upstream MCP。

## 日志复盘后的真实漏点

后续运行日志证明，“仍然抢焦点”的主路径不是第一阶段刚包住的 `chrome-devtools-cockpit.new_page`。

日志里大量出现的是：

```text
python3 scripts/env/client.py search open-browser --payload ...
```

对应源码路径：

```text
scripts/env/tools/search/_impl.py
```

其中 `_open_browser_page` 当前直接调用 Chrome DevTools HTTP endpoint：

```text
/json/new?...
```

这条路径绕过了 `chrome-devtools-cockpit` proxy，所以即使第一阶段已经生效，`search.open_browser` 打开搜索页仍可能抢焦点。

另一个小漏点在 launcher ready-page 创建：

```text
tools/launcher/browser_cockpit.sh
```

当前仍有：

```text
/json/new?about:blank
```

这同样是直接 CDP HTTP 开页路径，不经过 MCP proxy。

## 重要结论

这不是 commit 是否生效的问题。

commit 只影响版本记录和远端同步，不会自动改变运行中的 Codex/MCP 进程。真正的生效条件是：

- 实例 `codex-home/config.toml` 里的 `chrome-devtools-cockpit` 是否已经指向 proxy；
- 当前 Codex/BuddySwitch 会话是否已经重新加载 MCP 配置；
- 实际触发浏览器打开的入口是否走了已经包住的路径。

本地排查时已经看到目标实例的 app-server 使用了实例 `CODEX_HOME`，且 `chrome-devtools-cockpit` 配置已经指向 proxy。日志中的体感问题主要来自 `search.open_browser` 这条未覆盖路径。

## 下一阶段修复范围

下一阶段应该直接修真实漏点，不做过渡方案。

### 1. 修 `search.open_browser`

当前问题：

```text
search.open_browser -> /json/new?...
```

目标行为：

- 不再使用会激活窗口的裸 `/json/new?...`；
- 改为非激活创建页面的 CDP 路径；
- 优先评估通过 browser websocket 调 `Target.createTarget` 并传 `background: true`；
- 保持 search tool 的输出契约稳定：仍返回 target URL、opened 状态、后续 cockpit 使用提示；
- 后续提示要避免依赖“新 tab 自动成为 selected page”。

### 2. 修 launcher ready-page

当前问题：

```text
tools/launcher/browser_cockpit.sh -> /json/new?about:blank
```

目标行为：

- 避免在已有页面可用时创建新的激活页；
- 如果必须创建 ready page，也走非激活 CDP 路径；
- 不影响 browser ensure 的实例级生命周期和 MCP bootstrap。

### 3. 保持 MCP proxy 作为主保护层

第一阶段 proxy 不应回退。

下一阶段是在 `search.open_browser` 和 launcher 直接 CDP 路径上补齐非激活行为，而不是删除 proxy 或重新暴露 raw `chrome-devtools-mcp`。

### 4. 加源码形状和行为测试

测试要锁住 BuddySwitch-owned 浏览器入口，避免以后重新出现裸焦点路径：

- `scripts/env/tools/search/_impl.py` 不应再直接使用 `/json/new?...` 打开页面；
- `tools/launcher/browser_cockpit.sh` 不应再直接使用 `/json/new?about:blank` 创建 ready page；
- `chrome-devtools-cockpit` 注册必须继续指向 proxy；
- `new_page` / `select_page` 焦点参数继续被 proxy 强制改写；
- `Page.bringToFront` / `Target.activateTarget` 不能成为无门控路径。

## 测试与资源约束

必须遵守 `docs/bitter/2026-05-26-test-resource-lifecycle-principles.md` 的教训。

测试原则：

- 先跑 focused tests，再跑 broader tests；
- 不在 focused tests 中启动真实 Chrome、真实 Codex、daemon、app-server 或长生命周期服务；
- 如果测试需要 subprocess，测试必须拥有完整生命周期；
- 使用 fake CDP endpoint、fake websocket server 或 fake command 捕获行为；
- 每轮 service-like 测试后做 residual process check；
- broad suite 只能在 focused tests 通过且残留检查干净后运行。

建议的残留检查模式：

```bash
pgrep -fl 'chrome_devtools_cockpit_proxy|fake_upstream.py|fake-chrome|buddyswitch.*app-server|runtime_broker' || true
```

如果发现残留，不要继续扩大测试面，先定位生命周期问题。

## 推荐执行路径

1. 阅读当前代码：
   - `scripts/env/tools/search/_impl.py`
   - `scripts/env/tools/search/tool.py`
   - `tools/launcher/browser_cockpit.sh`
   - `tools/launcher/chrome_devtools_cockpit_proxy.py`
   - `tests/test_browser_cockpit_proxy.py`
   - `tests/test_browser_cockpit_launcher.py`
   - `tests/test_buddyswitch_launcher.py`

2. 先写 search browser 非激活开页测试：
   - 用 fake CDP server 验证没有调用 `/json/new?...`；
   - 验证调用的是非激活 CDP 创建 target；
   - 验证 search tool 返回契约不破坏；
   - 验证失败时错误信息仍可操作。

3. 实现最小直接改动：
   - 给 search tool 增加非激活创建 page 的内部 helper；
   - 避免引入通用 browser engine 或大型抽象；
   - 只服务当前 `search.open_browser` 需要。

4. 修 launcher ready-page：
   - 优先复用同类非激活 CDP helper 或 shell 侧最小实现；
   - 不扩大到 daemon/runtime/auth/skill 层。

5. 跑 focused verification：
   - search tool focused tests；
   - browser cockpit launcher focused tests；
   - proxy tests。

6. 残留检查干净后，跑 broader relevant tests：
   - `tests.test_browser_cockpit_proxy`
   - `tests.test_browser_cockpit_launcher`
   - 相关 `tests.test_buddyswitch_launcher` cases；
   - 必要时再跑更广的 launcher suite。

7. 做最终 review：
   - 确认 BuddySwitch-owned 常规浏览主链路不再有裸 `/json/new`；
   - 确认没有引入长生命周期测试泄漏；
   - 确认修复范围没有外溢到 skill、daemon、runtime actor profile、auth 等层。

## 完成判定

本任务不能以“proxy 已提交”作为最终完成。

最终完成需要同时满足：

- `chrome-devtools-cockpit` 继续通过 BuddySwitch proxy 暴露；
- `search.open_browser` 不再通过裸 `/json/new?...` 抢焦点；
- launcher ready-page 不再通过裸 `/json/new?about:blank` 抢焦点；
- tests 覆盖上述行为和防回归形状；
- focused tests 和 relevant broader tests 通过；
- residual process check 干净；
- 最终 review 通过，确认没有外溢到不相关模块。

## 当前风险

- Chrome/CDP 的非激活创建能力需要用实际协议行为验证，不能只靠字符串替换；
- 如果未来引入新的 browser tool 或直接暴露 raw MCP，仍可能绕过本次保护；
- 如果 Codex 使用键盘快捷键控制浏览器 chrome UI，例如 `Meta+L` / `Control+L`，行为本身不稳定，应该优先使用 page-level navigation 或非激活 target 创建；
- 不能为了“绝对不抢焦点”临时引入大而泛的权限系统；当前应先把 BuddySwitch-owned 主路径收口。
