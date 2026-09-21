# Web 模型 × WebCodex：第一条连续性实验

> Working / 实验分支认知。这里记录的是当前已经被代码约束的接法，不是对 WebCodex 上游架构的改写提案。

## 当前真正的断点

最初容易把问题说成“让 ChatGPT Web 模型获得 WebCodex 的工具能力”。

继续检查后，这个说法已经不够准确。

`codex-chatgpt-web` 本身已经能把 ChatGPT Web 模型放进 Codex 的工具循环里；WebCodex 自己也已经有完整的 REST / ToolRuntime / Goal / Workflow Session / handoff。重复造一个 REST Provider 或重复造 DVR，都没有增加约束。

第一条真正缺失的关系是：

```text
当前 Codex thread
    ≠
长期任务本身
```

如果长期工作只存在于 Codex thread/context 里，那么 compaction、thread 重建、窗口死亡以后，模型仍然只能依赖压缩后的上下文继续。

所以第一条实验不替换 Runner，不替换 ToolRuntime，也不改 WebCodex core。它只验证：

> 一个 Web 模型 thread 能否显式锚定到 WebCodex 的 durable Goal + Workflow Session，并在旧 thread 死亡后由新 thread 重新读取这两个 durable 对象继续。

## 三个仓库的职责

### Penrix/codex-chatgpt-web

负责“模型这一侧”：

- ChatGPT Web 模型通道；
- 当前 thread identity；
- 浏览器 turn；
- compaction 发生的时点；
- 极薄的 WebCodex continuity client。

它不成为长期任务事实库。

### Penrix/webcodex

负责“工作这一侧”：

- Goal：长期意图、计划状态、checkpoint revision；
- Workflow Session：工作过程、工具证据、validation/handoff；
- Project / Runner / ToolRuntime：真正执行与权限事实。

它不保存 ChatGPT Web 的完整聊天录像。

### Penrix/chatgpt-continuity

负责“原始对话证据这一侧”：

- Web 对话 DVR；
- conversation graph；
- turn / exchange identity；
- canonical readback、冲突、缺口。

因此目前不应在 WebCodex 里再造第二套 DVR。

## 第一条 Vertical Slice

实验代码目前落在：

```text
Penrix/codex-chatgpt-web
branch: penrix/webcodex-continuity-binding
```

WebCodex 侧本轮不需要增加新的 runtime primitive；现有：

- `create_goal`
- `work_on_project`
- `associate_goal_workflow_session`
- `get_goal`
- `checkpoint_goal`
- `session_handoff_summary`

已经足够支撑第一条实验。

### 首条真实消息

```text
DEV thread id
  -> create_goal(stable idempotency key)
  -> work_on_project(exact project)
  -> associate exact goal + exact session
  -> local correlation: thread -> goal/session
```

本地 correlation 只保存 durable ID、revision、project 和时间，不保存 bearer token，也不复制用户首条 prompt。

另外，在 `create_goal` 成功以后、任何可能产生新 Workflow Session 的调用之前，Provider 会先落一条 **未完成绑定 attempt**。它只记录 Goal、project、revision、当前 phase，以及已经确认拿到时的 Session ID。这样即使进程在 `work_on_project` 调用中崩掉，或者请求已经执行但响应丢失，下一条用户消息也只会看到“这次绑定结果未确认”，不会再自动创建第二个 Session。

### Compaction

真实浏览器 compaction 完成以后：

```text
replacement history
  -> 取出真正的 compaction summary
  -> get_goal 刷新 authoritative revision
  -> checkpoint_goal(expected_revision=exact revision)
```

因此 checkpoint 使用的是 WebCodex 自己的 revision fence，而不是在 Provider 一侧自造版本号。

### Thread 死亡 / 重建

新 thread 不允许自动猜旧任务。

只有显式：

```text
/recover-from <old-thread-id>
```

并且当前 thread 必须为空，才会：

```text
old explicit correlation
  -> same goal_id
  -> same session_id
  -> get_goal
  -> session_handoff_summary
  -> inject deterministic recovery context
```

这意味着“恢复”是重新读取 durable truth 后重新推理，而不是把隐藏旧上下文假装复活。

## 明确排除的错误方向

当前实验已经主动排除了：

- 以 project 相同就自动认定是同一任务；
- 取最近一个 Session；
- 按时间邻近、窗口、prompt 相似度猜关联；
- 把 Goal/Session ID 当 bearer credential；
- token 直接放环境变量；
- correlation 文件复制原始 prompt；
- compaction 后只保存自由文本 summary，而没有 Goal revision fence；
- response 丢失后自动重放 effect；
- 新 thread 已经有自己的工作后再把旧任务硬塞进去；
- 为接 Web 模型重写 WebCodex Runner / ToolRuntime；
- 在 WebCodex 内再造 chatgpt-continuity 已经承担的 DVR。

## 当前验收标准

第一阶段不是“感觉能续上”，而是故意杀 thread：

1. 首条消息后只有一个 `wc_goal_*` 与一个 `wc_sess_*`；
2. 连续多轮不新增；
3. 真实 compaction 以后，同一 Goal revision 前进；
4. reset 清空旧 DEV context，并生成新 thread id；
5. 新空 thread 显式 recover 后，拿回原来的 exact Goal + exact Session；
6. 新模型 turn 能只凭当前用户输入 + Goal + handoff 继续；
7. correlation 文件无 token、无原 prompt；
8. effect 的 post-dispatch 断线产生 `outcome_unknown`，未完成 attempt 会被持久化；后续消息仍不会再次调用 `work_on_project`；
9. 非空 thread / project 不匹配的恢复直接失败。

只有这九条都成立，才值得把同一个薄 binding 接到生产 Responses path。

## 尚未解决

这条 slice **没有**声称解决：

- production Codex Responses 路径里的自动绑定；
- Luna rolling checkpoint 与 Goal checkpoint 的统一策略；
- 自动发现“这个新 native thread 应该恢复哪个旧 Goal”；
- WebCodex 与 chatgpt-continuity 的联合检索排序；
- context 进入新模型时的最优显著性配置；
- 超长任务中何时 checkpoint 最合适；
- Goal 完成状态怎样由模型显式裁决；
- 原始聊天 DVR、Goal checkpoint、Session handoff 三种证据冲突时的优先级。

这些都应在第一条“thread death != task death”实证通过以后继续，而不是现在一次性设计完。
