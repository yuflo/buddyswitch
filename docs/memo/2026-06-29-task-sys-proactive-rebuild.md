# Task Sys Proactive Model Rebuild 备忘

## 审核结论

本次目标是重建 BuddySwitch 的 actor 驱动模型：所有会驱动 actor 的 inbound info 都必须先进入 `task sys`，登记为 task，再由 task sys 决定如何通过 side、parent、checkpoint 和 innerTUI 推进。

这是 rebuild，不是兼容迁移。阶段推进只是执行顺序，不是长期双轨。每完成一类入口或一类处理面，就删除对应旧路径，并用测试证明 raw inbound 不能再直达 actor。

核心判断：

- 架构边界必须收束在 `daemon-service`、`task sys`、`product domains`、`actor runtime` 四层。
- `daemon-service` 不承载业务语义，不拼 IM / Track / user input / checkpoint prompt。
- `task sys` 是 BuddySwitch 内建 product，负责 task 抽象、状态、UI、side/parent 协调和 checkpoint。
- actor 只响应 task-framed input，不直接响应 raw inbound info。
- task skill/tool 是 task sys 之上的管理接口，不是让 actor 自己发明 task 抽象的补丁。

## 总任务目标

将 BuddySwitch 从 inbound info 直接驱动 actor 的模型，重建为 task-first proactive model。

目标数据流：

```text
inbound info
  -> daemon-service generic ingress
  -> task_sys.ingest(envelope)
  -> task record + task frame
  -> side fast processing
  -> close | need_parent(params)
  -> task sys state transition
  -> runtime instruction
  -> daemon-service actuation
  -> parent task-framed input / checkpoint innerTUI
```

目标完成后，系统里不应存在这些路径：

- user input 直接 `submit_turn` 到 actor。
- IM / Track / comment handler 直接拼 actor prompt。
- handler 直接 `submit_parent_prompt`。
- handler 直接 `submit_side_triage_prompt`。
- turn complete 直接发送旧 `[TASK CHECKPOINT]` prompt。
- side thread 自己决定并执行 interrupt。
- taskbox / active-task gate 作为并行任务真相继续存在。

## 架构边界

### daemon-service

职责：

- 接收 generic inbound envelope。
- 做 actor target 定位、mailbox / local trigger / scheduled trigger 投递。
- 执行 task sys 输出的 runtime instruction。
- 提供物理 actuator：start side、submit parent、interrupt + submit、等待 parent 状态等。

不负责：

- 不判断 IM、Track、user input、checkpoint 的业务含义。
- 不生成业务 prompt。
- 不决定 task 生命周期。
- 不决定 side 结果。
- 不根据业务内容自行 interrupt。

daemon-service 如果需要改动，只能是泛化 transport 或物理 actuator 能力不足时的最小补齐，不能因为 IM / Track / task 业务而适配。

### task sys

职责：

- 作为所有 actor-driving inbound 的唯一语义入口。
- 将 inbound envelope 登记为 task。
- 保存 task source、context、状态、处理方、parent handoff 参数和 checkpoint 状态。
- 生成 side task frame。
- 接收 side result：`close` 或 `need_parent(params)`。
- 生成 parent task frame。
- 生成 checkpoint innerTUI。
- 输出 daemon-service 可执行的 runtime instruction。

不负责：

- 不直接操作 daemon internals。
- 不拥有 IM / Track / browser 等产品数据源。
- 不替 Codex 推荐或决定下一步任务。

### product domains

职责：

- IM、Track、browser 等产品维护自己的业务状态。
- 产出 source/ref/context，供 task sys 建 task 时引用。

不负责：

- 不拼 actor prompt。
- 不直接 start side 或 submit parent。
- 不绕过 task sys 唤醒 actor。

### actor runtime

职责：

- 读取 task sys framed input。
- 基于 task sys innerTUI/context 调用 task tool。
- 在 task sys 已经建立的抽象上做任务处理。

不负责：

- 不直接面对 raw inbound。
- 不靠 auth/gate 的扭曲提示来意识到要管理 task。
- 不维护另一套私有任务真相。

## 阶段 0：边界定稿与残留清单

### 子目标

冻结本次 rebuild 的边界和删除目标，避免后续继续扩散成兼容层、事件总线或泛化工作流系统。

### 内容

- 明确四层边界：daemon-service、task sys、product domains、actor runtime。
- 列出所有旧 raw inbound -> actor 路径。
- 列出所有旧 handler 直接拼 prompt、直接 submit、直接 side triage 的路径。
- 确认哪些 runtime maintenance 不驱动 actor，可以继续留在 daemon-service。
- 确认哪些 scheduled / browser / local trigger 一旦驱动 actor，必须进入 task sys。

### 验收

- 有一份明确的旧路径删除清单。
- 每个旧入口都有目标归属：task sys ingress、纯 daemon maintenance、或删除。
- 不出现“先双轨跑一段时间”的方案。

### 注意事项

- 阶段不是兼容边界，只是执行顺序。
- 不设计插件系统、规则引擎、事件总线或泛化 workflow engine。
- 不为了保留旧 handler 而加 adapter。

## 阶段 1：建立 task sys 最小底座

### 子目标

建立真正的 task substrate，让 task 成为 actor 驱动的底层抽象，而不是复用旧 taskbox 作为临时外壳。

### 内容

- 新建 `task_sys.ingest(envelope)` 作为 actor-driving inbound 唯一语义入口。
- 定义最小 task record：
  - task id
  - source type / source ref
  - actor target
  - inbound context
  - status
  - active processor
  - parent handoff params
  - checkpoint metadata
- 定义最小状态流：

```text
new
  -> side_processing
  -> closed | needs_parent
  -> parent_processing
  -> checkpoint
  -> closed | side_processing | needs_parent
```

- 定义 runtime instruction：
  - start side with task frame
  - submit parent with task frame
  - interrupt + submit parent with task frame
  - no actor action

### 验收

- 一条 inbound envelope 能生成 task record。
- task sys 能产出下一步 runtime instruction。
- task sys 不直接调用 daemon internals。
- 旧 taskbox 不作为新 task sys 的真相来源。

### 注意事项

- 先做最小可运行，不扩大为完整任务平台。
- task record 保存 source/ref，不复制产品域状态。
- runtime instruction 是 task sys 与 daemon-service 的边界 contract。

## 阶段 2：重建 inbound ingress

### 子目标

所有会驱动 actor 的 inbound info 都先登记为 task，删除 raw inbound 直达 actor 的入口。

### 内容

覆盖入口：

- CLI user input。
- Web user input。
- actor-to-actor / local trigger / signal 类入口。
- IM message created。
- Track comment added。
- turn complete checkpoint。
- scheduled trigger 中会驱动 actor 的部分。

目标改造：

- 入口只构造 generic inbound envelope。
- envelope 交给 `task_sys.ingest`。
- 入口不得拼 prompt。
- 入口不得直接 `submit_turn`。
- 入口不得直接 start side 或 submit parent。

### 验收

- user input 不再绕过 task sys。
- IM / Track inbound 不再直接唤醒 actor。
- turn complete 不再直接发送旧 checkpoint prompt。
- 测试证明所有 actor-driving inbound 都先生成 task。

### 注意事项

- daemon-service 只做 generic ingress，不为 IM / Track / user input 写业务分支。
- product domain 可以提供 source context，但不能拥有唤醒 actor 的执行权。
- 纯 runtime maintenance 不驱动 actor 时，不必强行建 task。

## 阶段 3：重建 side 快处理模型

### 子目标

side thread 成为 task sys 调度的快速处理者，而不是某个业务 handler 私自启动的 triage prompt。

### 内容

- task sys 生成 side task frame。
- daemon-service 只执行 start side / send side 的物理动作。
- side 处理 task frame 后，只能通过 task sys tool 返回两类结果：
  - `close`
  - `need_parent(params)`
- `need_parent(params)` 可包含：
  - parent frame context
  - 与当前 parent task 的关联说明
  - `interrupt: true | false`
  - ordering / priority metadata

### 验收

- side 不直接 submit parent。
- side 不直接 interrupt。
- side result 只有 `close` 和 `need_parent(params)`。
- 旧 side triage handler prompt 被删除或替换为 task sys frame。

### 注意事项

- `interrupt` 是 `need_parent(params)` 的参数，不是第三种 side outcome。
- side 表达判断，task sys 记录状态，daemon-service 执行物理动作。
- 不引入复杂优先级系统；需要排序时先用 task sys 内部简单字段表达。

## 阶段 4：重建 parent handoff 与 interrupt

### 子目标

parent thread 只接收 task sys framed input；interrupt 只能由 task sys 状态和 runtime instruction 驱动。

### 内容

- task sys 接收 `need_parent(params)`。
- task sys 将 task 状态更新为 `needs_parent` 或 `parent_processing`。
- task sys 生成 parent task frame。
- task sys 生成 runtime instruction：
  - submit parent
  - interrupt + submit parent
- daemon-service 执行 instruction。

### 验收

- 所有 parent prompt 都能追溯到 task id。
- 不存在业务 handler 直接调用 parent submit。
- 不存在业务 handler 自己决定 interrupt。
- daemon-service 不读取 IM / Track / user input 的业务字段来决策。

### 注意事项

- task sys 可以 gate / normalize side 给出的 `interrupt` 参数，但不能把 interrupt 决策下沉回 daemon-service。
- parent frame 必须包含足够 task context，让 actor 不需要回看 raw inbound 才能行动。

## 阶段 5：重建 task checkpoint 与连锁 innerTUI

### 子目标

turn complete 后由 task sys 执行 checkpoint，产生轻量 task UI，跑通 `UI -> Codex 调 tool -> UI update` 的最小闭环。

### 内容

- 删除旧 turn complete -> `[TASK CHECKPOINT]` prompt 路径。
- task sys checkpoint 确认：
  - 当前 task 是否完成。
  - 当前 task 是否需要扩展。
  - 当前 task 是否仍需 parent 继续。
  - 是否有待处理 task context 需要展示。
- task sys innerTUI 展示：
  - current task context
  - pending task context
  - legal operations
  - required params
  - constraints
- 先只试水一个 task sys tool，承担 checkpoint / task state update 的最小闭环。

### 验收

- turn complete 进入 task sys checkpoint。
- checkpoint UI 不推荐任务，不替 Codex 决策。
- Codex 能基于 UI context 调用 task sys tool。
- task sys tool 调用后能更新 task state，并返回下一帧 UI。

### 注意事项

- 连锁 innerTUI 是 task sys 的 UI，不是 daemon-service 的 UI。
- CTA 要轻，只给 context 和合法动作。
- 本阶段不做复杂队列 UI、不做推荐系统、不做 workflow engine。

## 阶段 6：重定位 actor-facing task skill/tool

### 子目标

actor-facing task skill/tool 建立在 task sys 之上，成为管理接口，而不是替代 task sys 的底层抽象。

### 内容

- task skill/tool 消费 task sys 当前 task、pending task、checkpoint frame。
- task tool 操作 task sys task state。
- active-task auth/gate 从“逼 actor 管 task”的提示机制，收束为 task-bound operation 的验证机制。
- 旧 taskbox 私有任务模型要被吸收或删除，不保留为并行 truth。

### 验收

- actor-facing task tool 不维护独立任务真相。
- actor 看到的 task context 来自 task sys。
- task skill 不复制 task sys schema 或私有实现路径。
- 旧 taskbox / active-task gate 中与新 task sys 冲突的逻辑被删除。

### 注意事项

- 先有 task sys，再有 task 管理能力。
- 不让 actor 越过 task 抽象直接管理 raw inbound。
- 不把旧 taskbox 包一层 facade 作为长期方案。

## 阶段 7：清残留、重写测试、验证收口

### 子目标

证明系统只剩 task-first proactive model，没有旧 actor 直达路径、没有双轨兼容、没有业务语义外溢到 daemon-service。

### 内容

清理残留：

- inbound handler 内业务 prompt rendering。
- handler 直接 `submit_parent_prompt`。
- handler 直接 `submit_side_triage_prompt`。
- user input 直接 `submit_turn`。
- turn complete 直接 checkpoint prompt。
- side 自行 interrupt。
- taskbox / active-task gate 并行任务真相。
- 旧测试中对 raw inbound 直达 actor 的期待。

新增或重写测试：

- inbound 必须先登记 task。
- user input / Web input / IM / Track / turn complete 都走 task sys。
- side result 只能是 `close` 或 `need_parent(params)`。
- interrupt 只能经 task sys runtime instruction 触发 daemon-service actuation。
- parent prompt 必须可追溯 task id。
- checkpoint 产生 task sys innerTUI frame。
- daemon-service 不包含 IM / Track / task checkpoint 业务决策。

### 验收

- 关键旧调用搜索无残留。
- 新行为测试通过。
- 相关集成路径通过。
- 被替换旧文件、旧 handler、旧测试期待已删除或改写。
- 没有为了历史行为保留双入口、双状态、双 prompt 生成路径。

### 注意事项

- 不用 compatibility adapter 掩盖旧路径。
- 不保留 legacy code “备用”。
- 删除本身是验收的一部分。

## 执行门禁

每个阶段开始前必须明确：

- 本阶段替换哪条旧路径。
- 本阶段新增哪条 task sys 主路径。
- 本阶段删除哪些旧逻辑。
- 本阶段用哪些测试证明新路径成立。

每个阶段结束时必须记录：

- 已完成的子目标。
- 已删除的旧路径。
- 已修改或新增的测试。
- 实际执行的验证命令和结果。
- 剩余风险是否影响进入下一阶段。

未证明删除旧路径，不进入下一阶段。

## 红线

- 不做 raw inbound -> actor 的兼容保留。
- 不做新旧 task system 双轨。
- 不让 daemon-service 适配业务语义。
- 不让 IM / Track / browser domain 直接唤醒 actor。
- 不让 side 直接 submit parent 或 interrupt。
- 不把 `interrupt` 做成 side 的第三种 outcome。
- 不把连锁 innerTUI 做成推荐系统。
- 不把 task skill/tool 作为 task sys 缺位时的替代品。
- 不引入 workflow engine、event bus、rule engine 或插件化调度系统。

## 一句话总结

BuddySwitch 的 actor 驱动入口必须重建为 task-first：所有 actor-driving inbound 先登记为 task，side 只返回 `close` 或 `need_parent(params)`，parent 只接收 task-framed input，checkpoint 和连锁 innerTUI 由 task sys 产出，daemon-service 只做通用传输和物理执行；旧直达 actor 路径必须删除，不保留双轨兼容。
