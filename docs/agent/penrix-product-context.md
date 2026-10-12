# Penrix WebCodex — product context and engineering takeover

Owner handover: 2026-10-09. The [complete original handover](../archive/2026-10-09-penrix-owner-handover.md) is preserved verbatim. This page is a navigation and current engineering projection; it does not replace the original reasoning.

## The outcome

The ChatGPT Web conversation the owner actually uses should be able to work on an authorized Windows project: inspect current source, edit, run validation, observe results, accept the owner's corrections and continue. The owner should not carry prompts or logs between ChatGPT and Codex for ordinary work. Local Codex is the current engineer and an optional future worker, not a required inference expense on every tool round.

An independent browser planner carrying only a new task is a transport experiment. Even a successful read/edit/test loop is not proof that the owner's current conversation, cognition or everyday workflow is connected.

## Why the direction changed

Task contracts improved coding procedure but could not restore discussion that was never handed over. Earlier DSH/browser bridges also accumulated unrelated execution, state and memory responsibilities. WebCodex was selected because it already owns real Project, Workflow Session, ToolRuntime, Runner and Job domains. Reuse those rather than building another agent runtime.

The earlier fork direction's DVR proposal is now superseded as an ownership decision: ChatGPT Continuity's Recorder preserves raw conversation evidence and OpenViking is the cognition-continuity body. WebCodex must not build a parallel recorder, memory database or Hot State. Preserve the older proposal as formation history; it is no longer a new implementation assignment.

The detailed cognition source is [ChatGPT Continuity's cognition-continuity document](https://github.com/Penrix/chatgpt-continuity/blob/main/docs/architecture/0003-cognition-continuity.md). It preserves perspectives, corrections, tensions, rejected routes and WHY. A latest summary does not erase older cognition or become execution truth. Use small timely context and selective recall rather than replaying all history.

## Responsibility boundaries

| Owner | Responsibility |
| --- | --- |
| ChatGPT Web | Understand the owner and current conversation; choose next actions using real evidence |
| Thin browser/provider adapter | Bind the intended conversation and authorized project; carry proposals and results |
| WebCodex | Tools, permissions, files/Git, Workflow Sessions, Jobs, Runner and execution evidence |
| ChatGPT Continuity / OpenViking / Recorder | Cognition trajectory, active context, selective recall and raw history |
| Coding agent | Technical research, implementation, debugging and verification without outsourcing ordinary choices to the owner |

## Reality recovered on 2026-10-09

- PR [#2](https://github.com/Penrix/webcodex/pull/2) is Draft/unmerged at `25dccf12cdece192500f9a97f8318cc8c278b55c`, against `penrix/sync-upstream-0.4.4`.
- All three exact-head CI runs succeeded: driver `37183471020`, Windows candidate `37183471031`, repository CI `37183470966`. The PR description still embeds earlier heads; use actual PR metadata.
- Candidate artifact `11295883995` has ZIP SHA-256 `a658d325968ce71d7381c30992800425f9068c225709b8410d01e3e1a9c33251`; download hash and `SOURCE.txt` were checked.
- On the owner's Windows machine the exact 0.4.4 candidate starts real local Server/Runner and reports `local_ready`; stdin EOF cleans up successfully. This probe sends nothing to ChatGPT and proves only that lifecycle.
- Recovered Codex Web GPT runtime was 6.1.3, browser-only, automatic, retained conversation, with existing launcher login. The launcher is now upgraded to 6.1.7 with rollback copies and unchanged Codex config. Its automatic runtime setup is blocked by the old integration journal versus the owner's newer route; saved core config remains at 6.1.3. The old local `codex-chatgpt-web` source checkout is 5.0.8-p2 and is not the installed producer.
- The first real acceptance stopped before Send with `model_version_unavailable`; no message or edit occurred. Upstream relay 6.1.7 contains fixes for the changed ChatGPT model UI. The acceptance/probe now require that exact version; upgrade and target evidence are tracked in the acceptance record.
- Launcher startup can conflict with the owner's newer Codex route. Keep the guard and the user's config. The bundled standalone `serve` path is a distinct Responses-only entry; do not solve the conflict by overwriting Codex routing.
- The owner's 2026-10-09 clarification makes **Install into Codex** conditional on WebCodex needing it. This Driver does not need it, so leave that setting alone. Local service startup now succeeds: split the local `Start-Process` invocation and URL health check into separate commands to avoid Codex 0.160.1's Windows command-classification false positive. No approval/guard settings were changed. Following a later successful UI smoke and fresh authenticated session inspection, a reconciled acceptance completed two Web turns and canonical file reading. A malformed edit proposal stopped before any mutation; the action-history repair is offline verified. The owner now requires a 30-second completed-reply test cooldown. See the acceptance record for exact evidence.
- The literal JSON transport subsequently completed the actual read/edit/long Job/test/review/finish loop. The local carrier's Git porcelain whitespace bug was repaired with a real Git regression. Retained recovery then restarted Server, Runner and Driver and recovered the exact same Project/Session and prior successful Job without repeating edits or execution. Stage A is now LIVE VERIFIED through combined initial-loop and retained-recovery evidence; the original carrier invocation itself failed before recovery. All 71 offline integration tests pass. Test cadence now rounds millisecond deadlines upward to guarantee at least 30 seconds after completion.
- Upstream latest release remains 0.4.6, including Windows onboarding/local-workflow fixes. The Stage A evidence remains scoped to the reviewed 0.4.4 binaries; an upgrade requires a separate runtime comparison.

## Immediate engineering sequence

1. Preserve the original handover and make the product/cognition boundaries discoverable.
2. Repair the real acceptance entry's missing send cadence using the existing account-wide Continuity operator file. Ordinary production Driver inference stays unchanged.
3. Stage A read/edit/long Job/validation/review/finish and retained restarted-Session recovery are verified. Preserve their evidence; do not repeat successful effects merely to obtain a single fresh carrier pass.
4. Choose the everyday entry against actual account capabilities and current supported connection paths. Bind the owner's chosen conversation or explicitly transfer sufficient cognition; do not present an isolated planner as the final entry.
5. Add context-continuity composition only for demonstrated missing cognition and use Continuity's existing owners.

## Connection research boundary

The owner confirmed that the Plus account lacks the required official MCP permission; this is why WebCodex uses a browser adapter. The read-only UI investigation saw a custom MCP creation form and a Tunnel option, but seeing those controls did not establish usable permission. No server was created, no credential entered and no model test sent during that investigation. Do not pursue official MCP or Tunnel setup for this account. Continue the thin browser adapter, retaining WebCodex as the execution owner and Continuity as the cognition owner; do not add a second executor or paid dependencies.

## Acceptance and evidence

The target remains the handover's scenarios A–F: complete task, correction in the same work, interrupted-execution recovery, new-window continuation with necessary cognition, simple daily startup, and truthful evidence. Code tests, hosted Windows build, target-machine runtime, cognition effectiveness and daily usability are separate claims.

Fresh local evidence and blockers belong in [the target acceptance record](../acceptance/penrix-windows-2026-10-09.md). Keep PR #2 Draft/unmerged while the target full loop is unverified.
