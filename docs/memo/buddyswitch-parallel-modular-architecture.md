# BuddySwitch 并行开发模块化架构

## 结论

目标只有一个：提高核心模块的并行开发效率。

本方案采用“薄封装”，不是“大抽象”：

```text
SKILL -> Tool Contract -> Service -> Domain Ops -> Object Repo -> JSON / Files
```

它解决三件事：

1. Tool layer 可以独立开发和扩展，尽量不影响 SKILL 或上层调用。
2. Buddy 专属 / 共享 SKILL 可以独立维护，尽量不影响 runtime。
3. `artifact`、`track`、`task`、`message`、`comment`、`buddybox` 可以按边界并行开发，彼此影响可控。

不引入 workflow engine、plugin system、event bus、通用对象框架。

## 整体视图

这张图看整体解耦度：三块可以并行开发，但运行时仍然走一条主链路。

```mermaid
flowchart TB
  subgraph SkillLayer["SKILL 指导层"]
    BuddySkill["buddy 专属 SKILL"]
    SharedSkill["共享 SKILL"]
  end

  Host["host / codex-cli"]

  subgraph ToolLayer["Tool 契约层"]
    Contract["tool contract\nschema + catalog + semantics"]
    Dispatch["dispatch\n执行入口"]
  end

  subgraph RuntimeLayer["Runtime 对象层"]
    Service["service\n请求/响应边界"]
    Domain["domain ops\n业务规则"]
    Repo["object repo\n单对象读写"]
    Store["JSON / files\n持久化"]
  end

  BuddySkill -. 发现能力 .-> Contract
  SharedSkill -. 发现能力 .-> Contract
  Host -. 发现能力 .-> Contract

  Contract --> Dispatch
  Host --> Dispatch
  Dispatch --> Service
  Service --> Domain
  Domain --> Repo
  Repo --> Store
```

读图方式：

- `SKILL` 负责“什么时候用、怎么判断、业务流程”。
- `Tool Contract` 负责 action、payload schema、catalog、semantics、dispatch 对齐。
- `Service` 负责把 tool 请求转成 domain 调用，再包装 runtime response。
- `Domain Ops` 负责业务规则和必要的跨对象协调。
- `Object Repo` 只负责单对象 schema、路径、读写、校验。

## 分层边界

| Layer | Owns | Does not own |
| --- | --- | --- |
| `SKILL` | 使用判断、业务流程、角色经验 | payload schema、dispatch 注册表、对象存储结构 |
| `Tool Contract` | action 名称、payload、catalog、semantics、权限声明 | 对象内部存储、跨对象业务规则 |
| `Service` | 输入适配、错误反馈、response shape | JSON 直接写入、跨对象状态决策 |
| `Domain Ops` | 业务规则、权限判断、跨对象协调 | 通用 workflow、plugin、event engine |
| `Object Repo` | 单对象 schema、normalize、load/save/list | sibling object mutation |

最重要的约束：

```text
跨对象规则只能在 Domain Ops；
Repo 不能互相调用；
SKILL 不能复制 runtime contract。
```

## 外部实践依据

这个方向符合主流 agent/tool 架构：

- MCP tools 通过 `tools/list` 暴露工具，并用 `inputSchema` / `outputSchema` 描述参数和输出；host 可以发现并调用工具。见 [MCP Tools](https://modelcontextprotocol.io/specification/draft/server/tools)。
- OpenAI Apps SDK 的 MCP server 负责定义 tools、auth、返回数据和 UI 关联，工具契约在 server 侧而不是 prompt 里。见 [OpenAI Apps SDK MCP Server](https://developers.openai.com/apps-sdk/build/mcp-server)。
- Claude Skills / Agent Skills 主要是按需加载的 instructions、workflows、resources，不应成为工具注册表。见 [Claude Skills overview](https://claude.com/docs/skills/overview)。

所以简化 SKILL 不会削弱工具能力。前提是 tool catalog、operation semantics、runtime response 足够完整，host / Codex CLI 可以直接发现并调用相关 tool，不必完全依赖 SKILL。

## 对象解耦

| Object | Owns | Allowed coupling | Must not do |
| --- | --- | --- | --- |
| `message` | direct send、inbox、reply 规则 | manifest buddy ids | mutate track / task / artifact / comment |
| `comment` | comment shape、thread、resolve/reopen | 通过 domain 检查 target readable | mutate target object state |
| `buddybox` | active-buddy private files | source_refs 可引用 logical_name 作为 provenance | become product-readable state |
| `artifact` | draft/revision/body/readability | 发布后被 track refs 读取 | 直接改 track shared refs |
| `track` | shared collaboration page、material/proof refs | publication domain 协调 artifact 状态 | own artifact body/schema |
| `task` | active-buddy work item state | 可引用 track_id 作为工作上下文 | 承担 artifact 发布或 track shared state |

`track` 和 `artifact` 不是完全隔离：发布本身就是跨对象业务。这里要做的是“受控耦合”，只允许一个发布入口。

## Track / Artifact 发布路径

`track-artifact-pm-runtime-repair` 合并后，唯一共享发布路径应是：

```text
artifact.create_revision -> track.add_material / track.add_proof -> track.open -> artifact.get
```

含义：

- `artifact.create_revision` 创建 active-buddy 草稿 / revision。
- `track.add_material` 和 `track.add_proof` 是共享发布入口。
- 发布时由 domain ops 同步 artifact 状态和 track 引用。
- `track.open` 读共享引用，`artifact.get` 读完整正文。
- `published_to_track` 不再作为 artifact 侧的直接发布输入。

## 并行开发方式

| Work | Should touch | Should not touch |
| --- | --- | --- |
| 新增 tool action | tool contract、对应 service、对应 domain/repo | 无关 SKILL、无关 tool |
| 修改 buddy SKILL | 对应 SKILL 文件 | Python runtime |
| 修改 shared SKILL | shared SKILL 文件 | dispatch、object repo |
| 修改 message | message service/domain/repo/test | track、artifact、comment |
| 修改 comment | comment service/domain/repo/test | target object mutation |
| 修改 buddybox | buddybox service/file repo/test | product object repos |
| 修改 track/artifact 发布 | publication domain、track/artifact repo、相关 service | message、comment、buddybox、task |

## 第一阶段落地

按最短验证路径推进，不一次性大拆：

1. 加边界测试：tool contract 投影一致、SKILL 不复制 schema、repo 不互相 import。
2. 先抽 `message`：它最独立，适合验证新结构。
3. 再抽 `comment`：验证 target readability 只能通过 domain ops。
4. 固化 `buddybox` 私有文件边界：它不进入 product object 状态。
5. `track/artifact` 等 runtime repair 合并后再抽：保留唯一发布路径。
6. 最后处理 `task`：它不承担 artifact 发布或 track shared state。

## 完成标准

第一阶段只证明三件事：

1. 新增一个 `message` action，不需要改共享 SKILL。
2. 修改一个 buddy-specific SKILL，不需要改 Python runtime。
3. `message` / `comment` / `buddybox` 的测试可以独立运行，不被 `track` / `artifact` / `task` 牵连。

必须保留的验证：

- tool contract、catalog、dispatch、semantics 对齐。
- object repo 没有 sibling repo import。
- `track/artifact` 发布只有一个 domain 入口。
- 现有 runtime contract tests 继续通过。
