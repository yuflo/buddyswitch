# Runtime Identity 边界收敛心得

Date: 2026-05-29

这次和 daemon/message 团队对焦后，我们对 `actor_profile` 这条线的定位更清楚了。

一开始容易把问题说成“系统只能有一套 buddy identity”。这句话是对的，但如果不继续拆开，就容易把所有和 buddy 相关的运行时事实都塞进 identity：谁在线、daemon endpoint 是什么、heartbeat 是否正常、消息投递是否成功、多实例时选哪一个。这会让 `actor_profile` 从身份归一化模块膨胀成一个 runtime 总控模块。

这次最重要的收敛是把 identity/address 和 runtime facts 分开。

`actor_profile` 应该回答的是：

```text
这个 runtime actor 是哪个 buddy 的哪个 instance？
```

也就是稳定提供：

```text
RuntimeActorAddress(buddy_id, instance_id)
```

central daemon 回答谁在线、怎么路由；daemon delivery 回答通知怎么投递；message 模块回答消息数据怎么创建和读取。这样既保住了“只有一套 buddy 身份语言”，又没有把 presence、routing、delivery、message data 错误塞进 identity。

对我们团队来说，未来定位应该从“actor_profile 小模块”升级为更明确的 Runtime Actor Identity 责任线，但不要过早改成泛化的 `identity` 平台。`identity` 这个名字太大，容易吸进 auth、配置、presence、routing。更稳妥的路径是先继续用 `actor_profile` 做实 `RuntimeActorAddress`，等 env.tool、daemon、message 都稳定消费后，再评估是否改名为 `runtime_identity`。

这次还有一个值得保留的判断：模块边界不是按数据看起来相关来划，而是按“谁拥有这个事实”来划。`buddy_id + instance_id` 是 identity 事实，归 `actor_profile`；online status 是 presence 事实，归 central daemon；notification status 是 delivery 结果，归 daemon/message 协作边界；message object 是 durable data，归 message。

我们的后续工作重点也更明确：

- 提供 `RuntimeActorAddress`；
- 提供稳定 `to_payload()` / `from_payload()`；
- 统一 buddy_id 和 instance_id 校验；
- 让 daemon/message 消费 actor_profile 输出，而不是各自解释 JSON；
- 坚决不把 endpoint、heartbeat、online status、routing choice 放进 actor_profile。

这次对焦的价值不是多加了一个结构体，而是把系统里“身份语言唯一”和“模块职责不过宽”同时守住了。后续实现时要继续保持这个判断：identity 可以被多个模块消费，但不能因此变成多个模块运行时事实的容器。
