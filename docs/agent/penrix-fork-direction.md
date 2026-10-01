# Penrix fork direction — current boundary after upstream 0.4.4

> Status: fork-local Working direction
>
> Current review date: 2026-10-01
>
> Upstream source baseline reviewed here: `yyjeqhc/webcodex@d11cdd226abd1efdb0351d4b58d502acb8f41f6e` (0.4.4 release-preparation head).
>
> Historical origin: the 2026-09-20 fork direction remains preserved on branch
> `penrix/archive-pre-0.4.4-2026-10-01` and in commit
> `f62dd0c0113aa039204152ad559b6300e79604a7`. This document supersedes that
> historical Working where newer upstream Reality has already answered the old gap.

This document records why `Penrix/webcodex` still exists after re-evaluating the
fork against current upstream. It is deliberately narrow. Upstream WebCodex is the
authoritative owner of its canonical runtime domains; this fork should add only
Penrix-specific behavior that current upstream does not already own.

## 1. Current mother problem

The product goal is still:

> Let a high-quality ChatGPT Web conversation use the user's real Windows
> development environment, while making ongoing work durable enough that losing one
> model turn or browser conversation does not mean losing the work itself.

There are two distinct continuity problems:

1. **work/runtime continuity** — files, Git state, Sessions, Goals, Jobs, validation,
   execution receipts, handoff and recovery;
2. **conversation cognition continuity** — user corrections, rejected directions,
   Why, evolving Working judgments, current salience and reasoning that may never
   have been written into repository/runtime state.

Current upstream has advanced substantially on the first problem. The fork must not
rebuild it.

## 2. What upstream now owns

As of the reviewed 0.4.4 source baseline, upstream already provides or is actively
defining the canonical domains we need for durable coding work:

- Workflow Session identity, handoff, explicit discovery and recovery;
- durable Session refs and selector contracts;
- saved decisions/recent progress in bounded handoff context;
- Goal correlation, checkpoint/progress and Goal context on Session recovery;
- durable Jobs, exact continuation/reconciliation, liveness heartbeats and
  meaningful-change waits;
- bounded interactive Job stdin through `run_process(interactive=true)` and
  `job_write_input`;
- Durable Agent / Conversation / Wake / AgentTask foundations;
- external-participant continuity for local Codex, including bounded external
  observations, handoff composition, selected-Session recovery and Windows adapter
  support;
- model-API delegation from saved Session context through the existing ACP run
  lifecycle;
- Windows Desktop / Server / Runner as an actively maintained target.

The user-facing upstream continuity guide is
[`docs/SESSION_CONTINUITY.md`](../SESSION_CONTINUITY.md). Relevant internal
contracts remain the authoritative source for exact semantics:

- [Workflow Session model](session-model.md)
- [Durable Agent runtime](../architecture/durable-agent-runtime.md)
- [Job reliability and Runner concurrency](job-reliability-and-concurrency.md)

Fork code must compose with these domains instead of creating parallel Session,
Goal, Job, Agent, task, retry or recovery truth.

## 3. What changed from the 2026-09-20 Working

The original fork direction correctly identified WebCodex as the local execution
and durable-state substrate, but several items that were then open are no longer
fork gaps.

In particular, the fork should **not** independently build:

- a second Session recovery system;
- a second Goal/checkpoint system;
- a second long-running Job lifecycle;
- a special Codex handoff store;
- a fork-owned generic model gateway merely because model delegation is useful;
- Windows continuity plumbing already present upstream.

Upstream issue
[`#784`](https://github.com/yyjeqhc/webcodex/issues/784) now explicitly studies
cross-ChatGPT-account/model context loss and references `codex-chatgpt-web` as a
useful model-backend precedent. Upstream PR
[`#800`](https://github.com/yyjeqhc/webcodex/pull/800) already added explicit
Session discovery/recovery plus saved-context model delegation.

Therefore the fork boundary has become thinner.

## 4. Fork-owned gap A: ChatGPT Web Provider

The main missing execution entry remains a provider for the user's already logged-in
ChatGPT Web experience.

Desired boundary:

```text
ChatGPT Web
    |
    v
Penrix Web Provider
    |
    v
WebCodex canonical runtime
    |
    v
Server / Runner
    |
    v
Windows
```

The provider must be thin, replaceable and Host-specific. ChatGPT Web DOM/session
behavior must not leak into core ToolRuntime, Goal, Session, Job or Runner
semantics.

### 4.1 Reuse prior working evidence, not the old runtime

`codex-chatgpt-web` / `dsh-chatgpt-web` already contain valuable evidence about:

- reusing an authenticated ChatGPT Web session;
- submitting one prompt reliably;
- detecting whether Send actually happened;
- binding one returned reply to the correct request/turn;
- waiting for completion without mistaking intermediate DOM state for success;
- browser recovery and bounded timeout/retry behavior;
- preserving effect uncertainty instead of blindly sending the same prompt twice.

Those projects are Provider behavior/code evidence. They are **not** the new
canonical Files/Git/Shell/Job runtime.

The first implementation should extract only the smallest Provider seam needed to
enter current WebCodex.

## 5. Fork-owned gap B: Conversation DVR

Upstream durable work state does not equal a full ChatGPT conversation archive.

The fork may still need an append-only, provenance-first Conversation DVR for facts
such as:

- an explicit user correction that never changed a file;
- a rejected technical/product direction and the reason it was rejected;
- an evolving Working judgment;
- current salience or an unfinished reasoning frontier;
- the history of how a current rule replaced an older rule.

The DVR is raw evidence, not a replacement for current runtime truth.

```text
current files / Git / Job / validation -> canonical WebCodex runtime
explicit durable work context           -> Session / Goal / Memory as appropriate
raw conversation history                -> DVR
retrieval index                         -> locator only
```

A retrieval result must not silently outrank later corrections or current runtime
facts.

## 6. Fork-owned gap C: conversation-to-durable-state bridge

The valuable missing layer is not "store every sentence as Memory".

We need experiments that determine which conversation facts must become explicit
durable state so a new conversation can continue correctly.

Candidates include:

- user-authoritative corrections;
- rejected routes;
- decision/Why notes;
- current Working;
- recovery-worthy checkpoint context.

Do not pre-commit to embeddings, vector DBs or a generic memory framework. First
measure what exact information is missing after current upstream Session/Goal
recovery.

## 7. First acceptance sequence

### Stage A — Web Provider to canonical runtime

Prove one real Windows loop:

```text
ChatGPT Web
-> Provider
-> WebCodex
-> read
-> edit
-> run / validate
-> observe the exact Job
-> return the result to the same ChatGPT Web request
```

No DSH dependency is required for this acceptance. No local Codex quota is required
for the canonical path. Local Codex/ACP may remain an optional worker.

### Stage B — cross-conversation runtime recovery

Run a real multi-step task that creates durable Session/Goal/Job evidence, then kill
the original ChatGPT conversation.

A new conversation should be able to explicitly discover and resume the exact work,
recover current Project/Git/Job truth and continue after a small user action such as
"continue".

The first acceptance does **not** require fully unattended automatic creation of a
fresh ChatGPT model turn. Upstream has had real Host-auto-resume failures in
dogfood; manual re-entry and correct durable recovery are a separate, earlier
product milestone.

### Stage C — measure the cognition gap

Only after Stage B, record what could not be reconstructed from current upstream
state.

Those observed failures define the minimum DVR projection/retrieval work.

## 8. Windows reality

Windows is now a first-class upstream target, but current field evidence still
matters.

At review time:

- official v0.4.3 Windows artifacts have an open Defender report
  [#780](https://github.com/yyjeqhc/webcodex/issues/780), including a verified
  byte-identical Runner quarantine report;
- another reported Windows environment shows `0xC0000022 / STATUS_ACCESS_DENIED`
  when launching bundled runtime executables;
- upstream has prepared 0.4.4 source and asked for re-test on the fresh Windows
  build.

Consequences for this fork:

- use current upstream 0.4.4 source as the engineering baseline;
- do not claim Windows live acceptance merely from source/CI;
- do not solve the field reports by disabling Defender or adding broad exclusions;
- re-check the actual published/current Windows artifact before live acceptance.

## 9. Upstream/fork ownership rule

Before any material fork-core implementation, ask:

1. Does current upstream already own this concern?
2. Has upstream implemented it since the last fork review?
3. Can the Penrix need be expressed as Provider/adapter/plugin composition instead?
4. Is there a demonstrated gap that cannot be represented by existing canonical
   domains?

If upstream owns it, follow upstream.

If the need is ChatGPT-Web-specific, keep it outside canonical core where practical.

If a true core gap is demonstrated and is generally useful, prefer an upstreamable
change rather than permanent fork divergence.

## 10. Sync policy

The fork should stay close to upstream and keep fork-local surface small.

Current fork-local durable assets are intentionally limited to:

- this direction document and its repository pointers;
- `PENRIX-CODING.md` as the local coding/reality overlay;
- future ChatGPT Web Provider / DVR adapter code that cannot live upstream unchanged.

Historical fork reasoning is preserved by Git history/archival branch rather than by
keeping stale architecture active in current docs.

## 11. Current unknowns

Still OPEN and requiring implementation evidence:

- the thinnest stable Provider boundary against current ChatGPT Web;
- which exact code from prior Web bridges should be reused versus rewritten;
- authentication/session-state ownership for the Provider;
- how Provider request identity maps to WebCodex Window/Session without inventing
  authority;
- the minimum conversation facts missing after upstream 0.4.4 Session/Goal recovery;
- whether DVR retrieval needs lexical, semantic, temporal/graph or hybrid indexing;
- the correct Desktop/user workflow after the Provider exists;
- whether upstream #784 will absorb part or all of the generic model-provider layer.

## 12. Current one-line direction

> Follow upstream for runtime continuity. Keep the Penrix fork thin: connect the
> already-logged-in ChatGPT Web experience to canonical WebCodex, then add only the
> raw conversation evidence/recovery bridge that real cross-conversation tests prove
> upstream cannot reconstruct.
