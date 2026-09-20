# Penrix fork direction — Web Chat、本地执行与跨窗口连续性

> 状态：fork-local design context / Working direction
>
> 记录时间：2026-09-20
>
> 这不是上游 WebCodex 的新公共产品定义，也不覆盖现有 canonical contract。它保存 Penrix/webcodex 当前 fork 为什么存在、这几轮已经确认的事实、真正要解决的问题，以及后续实现不能轻易丢掉的判断。
>
> 如果本文对“现有 WebCodex 已经怎样工作”的描述与当前代码、AGENTS.md 或其指向的 canonical docs 冲突，以当前代码和权威文档为事实来源，本文应被修正。对 fork 的目标、验收条件和取舍，则以这里记录的当前明确判断为工作方向，直到新的实证推翻它。

---

## 1. 真正的母问题不是“有没有 MCP”

当前 fork 的第一目标不是做一个更强的 MCP Server，也不是把 WebCodex 已有能力重新实现一遍。

真正的问题有两段。

第一段：高质量云端模型 / ChatGPT Web 很擅长理解、判断和规划，但它缺少稳定的本地身体。我们真正需要的是让它可靠地进入 Windows、本地仓库、Git、Shell、程序与桌面，而不是让用户长期做人肉中转站。

第二段更贵：即使模型已经有本地工具，一次长任务仍可能在理解项目、排除错误方向、修改部分现实以后，因为 conversation / context 用尽或窗口消失而中断。新窗口通常还能看到代码，却丢掉了大量真正昂贵的工作认知：

- 为什么现在这样改；
- 哪些方向刚刚被证伪或明确否决；
- 用户刚刚纠正了模型什么；
- 当前 Working 是什么；
- 当前最显著的问题和执行前沿在哪里；
- 下一步为什么是这一刀而不是另一刀；
- 哪些 effect 可能已经发生，不能盲目重试。

所以本 fork 的母问题更准确地说是：

> 让高质量 Web 模型拥有可靠的本地执行能力，并让“正在进行的工作”不再等同于某一个浏览器窗口或某一次模型上下文。

---

## 2. 上游已经解决了很大一部分“身体”和“执行连续性”

这些不是 fork 新造的概念，应优先复用。

### 2.1 MCP 是入口之一，不是 runtime 本体

当前架构已经明确：MCP、GPT Actions / OpenAPI、REST、CLI、Console 最终进入同一个 canonical ToolRuntime，再由 Server / Runner 落到本地 Project。

因此，本 fork 不应该把“当前 ChatGPT Host 或套餐是否开放自定义 MCP”当成架构级前提。外部 Host 能力会变化。只要我们自己的 Web Provider 能安全地进入 WebCodex 已有 HTTP/runtime authority path，就没有理由再复制一套 Files / Git / Shell / Job / validation / authority runtime。

### 2.2 Server / Runner 已经是合适的本地执行边界

上游已经拥有 Project 注册与 allowed roots、文件读写、Git、Shell / process、validation、Job、LSP / navigation、Computer Use、Browser、Native Tool Plugins、local MCP gateway 等能力。

所以 fork 不应默认继续自造一套“本地执行器”。

### 2.3 不同持久对象解决的是不同问题

上游已经刻意把以下对象分开：

- Goal：高层、持久的最终意图、计划与进度。
- Workflow Session：一次具体编码/执行工作的证据、验证、handoff 与恢复上下文。
- Job：真正的长时间命令或验证执行。
- Durable Agent：跨浏览器窗口、Host connection、model turn 仍然存在的行动/通信身份。
- Agent Task / TaskAttempt：明确接受的异步工作与精确执行所有权。
- CodingAgentRun：通过 ACP 委派给 Codex 等本地 coding agent 的独立执行对象。

不能因为它们都和“连续性”有关，就合并成一个新的 fork 概念。

尤其要继续遵守：

- 模型进程不是 Agent；
- 浏览器窗口不是 Agent；
- Goal 不能从当前 Project、Window、credential 或 Session 猜出来；
- Workflow Session 不是 Conversation、Agent Task 或 Job；
- Job terminal 不自动等于 Goal 完成；
- Agent identity / Goal correlation 不自动获得 Project、文件系统或执行权限；
- 一个消失的 model turn 不证明上一轮 effect 没发生。

### 2.4 上游已经有跨 turn / 跨窗口恢复骨架

当前 Goal / Session 设计已经形成了清楚的恢复关系：

    最新 durable Goal / checkpoint
              +
    明确关联的 Workflow Session
              +
    session_handoff_summary
              +
    当前 Job / Project 真实状态
              ↓
    新 model turn 重新推理并继续

关键不是把旧窗口完整搬进新窗口，而是把继续工作真正需要的 durable state 从临时 model context 中剥离出来。

这应该成为 fork 的起点，而不是再设计一套平行“连续性引擎”。

---

## 3. Project Memory 已经存在，但它不是 ChatGPT Library，也不是聊天录像

这几轮讨论中需要明确纠正一个早先判断：WebCodex 已经有 Project Memory。

它是与 Workflow Session 分开的持久知识面，有独立权限，也支持 memory.bootstrap。但当前 contract 同时明确了几个决定性的边界：

1. memory_search 当前是 bounded deterministic literal matching，不是向量语义搜索。
2. Session event 不会自动创建或“总结成” Memory。
3. Memory body、summary、search result、bootstrap projection 不会自动复制进 Session handoff。
4. Project Memory 是显式 durable knowledge / guidance，不是原始 conversation archive。
5. 当前 durable-agent 文档仍把 Agent-scoped Memory 留在未来边界。

因此：

    Project Memory
    ≠ Workflow Session recovery
    ≠ Goal checkpoint
    ≠ Conversation transcript
    ≠ semantic retrieval index

这是 fork 后续不能再混掉的边界。

---

## 4. 连续性至少有两种不同的“真相”

只保留 WebCodex runtime 状态还不够；只保存聊天文本也不够。

### 4.1 项目现实 / 执行现实

例如：

- 当前文件内容；
- Git diff；
- 已完成的 validation；
- Job 当前状态；
- 哪个 effect 已知 completed、not_started 或 outcome_unknown；
- Goal 当前 revision / step；
- Workflow Session 当前证据。

这些事实应继续由 WebCodex canonical runtime / Store / Runner 拥有。

### 4.2 对话中形成的认知历史

例如：

- 用户明确否定了哪个方案；
- 为什么某条路技术上可行但不符合真实目标；
- 一个概念怎样从第一版被修正成当前 Working；
- 当前哪一个问题最显著；
- 哪些未完成推理还没有落到代码里；
- 为什么“下一步”是这一刀而不是另一刀。

这些事实可能还没有改变仓库现实，因此不能指望 Git diff、Job 或 Session 自动重建。

这就是 Conversation DVR / 原始对话证据仍然有独立价值的原因。

---

## 5. DVR 的地位：原始证据，不是另一个 Memory

当前 Working 决定是：

> 完整原始 Conversation DVR 如果实现，应作为 append-only、provenance-first 的原始证据源。

它不应该被摘要取代，也不应该让某个模型生成的 Memory 反过来覆盖它。

关系应更接近：

    完整 Conversation DVR
        ├─ 可以产生或更新显式 Project Memory
        ├─ 可以产生 handoff / recovery 辅助材料
        └─ 可以建立 retrieval index
                         ↓
                    找到原始证据

其中：

- DVR 保存“过去实际说过、改过、否定过什么”；
- Project Memory 保存“以后仍值得明确提醒模型的 durable knowledge”；
- Workflow Session 保存“这次执行发生了什么”；
- Goal 保存“当前高层意图与进度”；
- retrieval index 只负责“去哪里看”。

索引不能成为历史真相。

如果检索命中一段旧判断，而后面的 conversation 已经把它否掉，系统必须能回到原始时间关系和后续修正，而不是把最相似的 chunk 当成当前真相。

---

## 6. 因此“语义检索”不是第一步

很容易先想到：全部聊天 → embedding → vector DB → 新窗口语义搜索。

现在这条路线只能算候选 Working，不是默认答案。

原因不是向量搜索没用，而是：在事实来源、时间关系、修正关系、当前状态和恢复验收尚未定义清楚时，单纯提高相似度召回不会自动得到正确连续性。

应该先证明：

    旧 conversation 死亡
        ↓
    新 conversation
        ↓
    只靠 durable work state / explicit recovery
        ↓
    能不能真正继续同一个任务

这个实验完成以后，再看它具体缺了哪些“只存在于对话认知里”的信息。那些真实缺口才决定 DVR / retrieval 应该保存和检索什么。

---

## 7. ChatGPT Web Provider 应该很薄，而且可以被替换

本 fork 仍然需要一个上游 WebCodex 没解决的特殊入口：如何进入用户已经登录、正在使用的 ChatGPT Web 会话。

这一层不能和整个本地 runtime 绑死。更合理的边界是：

    ChatGPT Web / 其他 Web Host
                ↓
           Web Provider
          （薄、脆、可替换）
                ↓
          Penrix WebCodex
        ├─ canonical ToolRuntime
        ├─ Goal / Session / Job
        ├─ Durable Agent
        ├─ ACP CodingAgentRun
        └─ Runner / Windows

因此以前的 codex-chatgpt-web 更适合作为 ChatGPT Web Provider 行为与经验来源，而不是另一套继续平行生长的完整 runtime。

当前不应粗暴合仓。先提炼 Provider 边界，再决定代码迁移。

---

## 8. WebCodex Browser 不能替代 Web Provider

当前 Browser/CDP runtime 明确使用 WebCodex 自己创建的临时 profile，不附着用户正常 Chrome / Edge profile，也不继承用户已经登录的 ChatGPT session；Phase 1 也不提供真实 profile attachment、扩展、password manager 等。

因此：

    WebCodex Browser
    ≠ 用户当前已登录的 ChatGPT Web Tab

Browser 对普通网页自动化有价值，但不能被当成“已经不需要 ChatGPT Web Provider”的理由。

---

## 9. ACP 的正确位置：把工具噪声从高价值 Web 对话里移出去

上游已经有独立 CodingAgentRun，并真实 dogfood 过 Codex ACP。

本 fork 更看重的使用方式是：

    ChatGPT Web / 高质量模型
    负责理解用户、判断目标、决策、选择下一步、检查结果
                ↓ 委派
    本地 Codex / ACP agent
    负责大量代码搜索、修改、命令、测试、多轮工具交互
                ↓
    只返回结构化结果 / diff / evidence

这不能扩大 model context window。

但它能把大量本来不应该污染主 conversation 的工具轨迹移出去，从而延长高价值上下文的有效寿命。

---

## 10. 第一阶段真正的验收：杀掉旧窗口以后还能继续真实任务

在实现语义检索、复杂 DVR UI 或大规模 fork 改造之前，先做一个最小而残酷的实验。

### 10.1 准备真实多步任务

任务至少应产生：

- 一个明确 Goal；
- 一个关联的 Workflow Session；
- 至少一次真实文件修改；
- 至少一次验证或 Job；
- 一个明确被否掉的方案；
- 一个用户/模型形成的关键 Working；
- 一个 recovery-worthy checkpoint；
- 一个尚未完成的下一步。

### 10.2 强制杀掉原 conversation

不能让新窗口直接得到完整旧 transcript，也不能偷偷依赖旧窗口仍然活着。

### 10.3 新 conversation 恢复

新模型只允许通过 fork 当前设计的正式恢复面重新进入：

- exact Goal；
- checkpoint / plan；
- exact Session handoff；
- 当前 Project / Git / Job truth；
- 以后加入的显式 Memory / DVR retrieval（如果实验阶段已经存在）。

### 10.4 通过标准

新窗口应该能在很少的恢复动作后回答并继续：

1. 我们最终要完成什么？
2. 为什么当前方案是这样，而不是最明显的替代方案？
3. 已经真实改了什么？
4. 哪些方向已经被否掉，为什么？
5. 当前 Project / Job / validation 到什么状态？
6. 当前执行前沿在哪里？
7. 下一步具体是什么？
8. 然后真正继续修改并完成任务。

### 10.5 不算通过

- 只是生成一段看起来像样的摘要；
- 重新从头阅读整个仓库才逐渐猜回状态；
- 再次进入刚刚已否决的路线；
- 必须把完整旧 transcript 整段重新注入才能继续；
- 把消失的上一轮 effect 当成“肯定没发生”而盲目重试；
- 只能在 CLI 演示成功，但不能走向用户真正日常使用的 Web / Desktop 工作方式。

这个实验比“有没有一个 Memory 功能”更能证明连续性是否真的成立。

---

## 11. 当前事实关系

不要再造一个抽象总节点把一切叫“Memory”。

更准确的关系是：

- Durable Goal：最终意图与高层进度。
- Project truth：files / Git 等当前现实。
- Workflow Session：执行证据、验证、handoff、恢复。
- Job / CodingAgentRun：具体执行。
- Durable Agent / Conversation：谁在行动、谁在通信、跨窗口身份。
- Project Memory：显式 durable knowledge / guidance。
- Conversation DVR：完整原始对话与认知演变证据。
- Retrieval index：找到相关证据的位置，不拥有事实。

这些对象可以互相引用，但不要因为“恢复时都要用到”就取消各自边界。

---

## 12. fork 的实施顺序

### A. 先证明 Web Provider → canonical runtime

不要先重写 Runner。

先确认自己的 Web Provider 能否稳定、安全地走 WebCodex 已有 REST/runtime authority path，完成一个完整本地闭环：

    read
    → edit
    → run / validate
    → observe exact Job
    → show changes
    → finish / handoff

### B. 再证明跨 conversation 的 runtime continuity

先用已有 Goal / Session / Job / Durable Agent 能力跑第 10 节实验。

### C. 再用真实失败决定 DVR 缺口

记录新窗口恢复失败时究竟缺什么：用户裁决、已否决路线、Why、当前 Working、长期项目认知，还是其实只是 Session / Goal 没正确 checkpoint。

不要提前用一个“长期记忆系统”解释所有缺口。

### D. 最后才选择 retrieval 方案

语义向量、全文字面、时间邻近、conversation graph、混合搜索都只是候选手段。

应使用真实恢复 query 做对照测试，而不是因为“向量数据库通常这么做”就先固定架构。

---

## 13. fork / upstream 边界

为了未来继续跟上上游：

1. 优先复用上游 canonical domain。已经能由 Goal / Session / Agent / Job / Memory / ACP 表达的事实，不再造平行实体。
2. 特殊需求尽量放在 adapter / provider / plugin / fork-local docs，不因 ChatGPT Web 的脆弱细节污染 ToolRuntime 核心。
3. 核心改动必须有真实缺口。先用上游现有能力跑实验；只有当实验能证明某个事实无处表达时，才扩 core。
4. 不为了兼容旧项目而保留两套 runtime。旧项目中真正有价格的是 ChatGPT Web Provider 经验，不是它重复实现的通用本地能力。
5. 上游事实持续变化时先更新认知。本 fork 是 2026-09-20 从当时 main 分出的；上游仍高速演进。以后同步前应先检查是否已经原生解决我们准备自建的能力。

---

## 14. 当前 Working / 未知

下面这些还没有被实证，不应写成“已经解决”：

- ChatGPT Web Provider 到当前 REST/runtime 的最佳认证与 transport 形状；
- Web Provider 在 ChatGPT 页面变动后的稳定抽象边界；
- 哪些对话认知必须自动进入 durable state，哪些只应该留在 DVR；
- DVR 的最小原始数据模型；
- 怎样做到足够准确的长期语义检索，以及是否需要 embeddings；
- 新窗口恢复时最小必要上下文是多少；
- Desktop 最终怎样把这套能力变成普通用户可持续使用的工作流；
- ChatGPT Host 能力变化以后，哪些原生入口可以替代自建 Provider。

这些应该通过实验收紧，而不是为了“体系完整”提前补齐。

---

## 15. 当前一句话方向

> 不要重新造一个本地 Codex。把 WebCodex 当成模型与 Windows 之间已经成熟的执行 / 持久状态底座；fork 真正新增的价值，是把现有 ChatGPT Web 入口接进来，并证明工作认知能够跨 conversation 继续，而不是跟某个窗口一起死亡。

后续任何大改动，都应该先回答：

> 它是在推进这个问题，还是只是在 WebCodex 里增加一个本来就不缺的新功能？
