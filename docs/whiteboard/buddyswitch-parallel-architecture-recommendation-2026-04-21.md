# BuddySwitch 并行架构唯一推荐方案

## 结论
- 唯一裁决：在单 repo 内，收敛为六块硬边界模块：`contracts`、`runtime-kernel`、`state-store`、`launcher-runtime`、`console-readonly`、`projects/app`。
- 最大并行收益不来自继续横向拆更多模块，而来自先削薄共享控制面：冻结合同，抽空 `switch_runtime.py` 和 `env_store.py` 的中央职责，把写路径收敛到单一 store API，把读路径收敛到单一 projection/query API。
- 迁移总原则：外部入口先不变，内部逐层替换；launcher 最后动；任何阶段不得同时改 CLI 契约、对象 schema、launcher 拓扑 三者中的两项以上。
- 这不是“更漂亮的分层”提案，而是单 repo 下最大化并行开发的最短验证路径。

## 唯一推荐方案
- `contracts`
  - 唯一真相层。
  - 收敛 switch grammar、buddy-skill routing、skill runtime metadata、`selected_skill_packet`、canonical object schemas、workspace projection schema、runtime workspace boundary contract。
  - `manifest`、`env_manifest`、`runtime-AGENTS`、router 文档、合同测试都只能从这里导出或对这里校验。
- `runtime-kernel`
  - 唯一职责是 `parse -> resolve -> prepare_execution -> persist`。
  - 保留 `scripts/switch_runtime.py` 作为薄壳入口；壳内不得继续长出 buddy-specific 语义。
- `state-store`
  - 唯一可写状态入口。
  - 内部分为 `repositories` 与 `projections`：前者负责对象读写与一致性，后者负责 console/app 消费视图。
  - 共享 root 必须具备单写者约束，或对象级 version/CAS。
- `launcher-runtime`
  - 只负责运行环境准备、execution workspace 管理、稳定 runtime API 调用。
  - 不再承载路由、状态变更、业务判断。
- `console-readonly`
  - 只读 projection。
  - 不碰 repositories，不承担 cleanup、advance、handoff 写操作。
- `projects/app`
  - 只消费 workspace query/projection API。
  - 不直连 `scripts/env_*`，不感知 BuddySwitch 内部对象模型。
- 并行开发的实际分工面
  - 一条线做 `contracts + runtime-kernel`。
  - 一条线做 `state-store + projections`。
  - 一条线做 `projects/app`。
  - 一条线做 `console-readonly`。
  - `launcher-runtime` 最后单独收口。

## 明确放弃项
- 不先上 Nx、Turbo 或其他 monorepo 编排器；当前瓶颈不是构建编排。
- 不先改 launcher 拓扑；先稳住合同和数据面。
- 不做 multi-skill 自动选 skill。
- 不做 slot alias、双轨兼容、隐式 fallback、自动 downgrade。
- 不让 panel 直接 cleanup、advance、handoff。
- 不把 buddy-specific 规则继续堆进 orchestrator。
- 不引入 workflow DSL、permission engine、plugin system、event bus。
- 不做 snapshot、cache、fallback 形成第二事实来源。
- 不让 `projects/app` 或 console 直连 `env_store`、`env_manifest`、`scripts/env_*`。

## 迁移顺序
1. Phase 0：契约冻结，不搬家
   - 确定 `contracts` 首批冻结面与命名。
   - 让 `manifest`、`env_manifest`、`runtime-AGENTS`、router、合同测试指向同一合同源。
   - 在 CI 先加协议漂移即失败的检查，但不改外部入口。
2. Phase 1：先抽控制内核
   - 从 `scripts/switch_runtime.py` 抽出 `runtime-kernel` API。
   - 保留脚本为薄壳；CLI 行为不变。
3. Phase 2：再抽数据面
   - 从 `env_store.py` 抽 `state-store`。
   - 建立 `repositories + projections`。
   - 同时建立唯一 canonical projection builder 和 workspace query API。
4. Phase 3：拆表面层
   - 让 `projects/app` 与 `console-readonly` 改为只读 projection/query API。
   - 至此形成两个真正可并行演进的 app 面。
5. Phase 4：最后独立 launcher
   - 将 launcher 收口为 `launcher-runtime`，只负责环境与稳定 API 调用。
6. Phase 5：收口成单 repo 最大并行形态
   - 固化 CI 车道、目录边界、依赖禁令、合同导出流程。
- 阶段停止条件
  - 任一阶段若同时触及 CLI 契约、对象 schema、launcher 拓扑 三者中的两项以上，立即停下并重切阶段。

## 核心风险与 guardrails
- 风险：thin orchestrator 重新变厚。
  - Guardrail：`runtime-kernel` 只允许 `parse/resolve/prepare_execution/persist`；buddy-specific 规则不得进入。
- 风险：JSON object store 缺少并发协议，导致共享 root 写坏状态。
  - Guardrail：共享 root 强制单写者或对象级 version/CAS；无并发协议不得扩大并行写路径。
- 风险：`manifest`、`skill.toml`、`SKILL.md`、schema、runtime tests 继续协议漂移。
  - Guardrail：`contracts` 成为单源导出或单源校验；`test_repo_consistency.py` 只校验合同，不再承担多套真相胶水。
- 风险：`workspace_data.py`、context panel 或 query API 重新长成第二控制面。
  - Guardrail：projection 只读；canonical builder 只能有一个；panel 不得写状态。
- 风险：slot 词汇表变成隐式中央 API。
  - Guardrail：slot vocabulary 视为版本化公共协议；变更必须显式版本化。
- 风险：双真相回潮。
  - Guardrail：禁止 snapshot、cache、fallback 成为权威；permissions 要么真实执行，要么明确只是说明。
- 风险：测试墙继续锁死实现细节，阻塞迁移。
  - Guardrail：合同测试只锁 ABI 和边界，不锁内部文件布局和抽离路径。

## 下一步动作
- 1. 直接把本文件作为并行架构唯一基线，不再扩散新的架构备选文档。
- 2. 立即启动 Phase 0，只做契约冻结：
  - 冻结 switch grammar、`selected_skill_packet`、canonical object schemas、workspace projection schema、runtime workspace boundary。
  - 标记当前中央瓶颈文件：`scripts/switch_runtime.py`、`scripts/env_store.py`、`scripts/env_manifest.py`、`workspace_data.py`、`tests/test_repo_consistency.py`。
- 3. 下一张实施单只做一件事：
  - 从 `scripts/switch_runtime.py` 抽 `runtime-kernel`，保持 CLI 不变。
- 4. 在 Phase 1 完成前，拒绝以下并行需求：
  - 新增 orchestrator 语义。
  - launcher 新拓扑。
  - app 直连内部状态。
- 5. Phase 1 的验收标准：
  - CLI 契约不变。
  - orchestrator 只剩薄壳。
  - 新内核 API 可被脚本与后续 launcher 共同调用。
  - 文档合同测试仍通过，但开始基于统一合同源运行。
