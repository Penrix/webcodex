# Penrix ChatGPT Web driver

> Status: **Stage A and same-chat execution/restart LIVE VERIFIED; explicit chat transfer CODE VERIFIED, LIVE UNVERIFIED; cognition continuity pending**
>
> Fork-local experiment. This is not an upstream WebCodex product surface and does not change canonical ToolRuntime semantics.

### Co-use with ChatGPT Continuity

Browser-entry prompts begin with the reserved `[WebCodex controller request:<32 lowercase hex>]` line. They are automated controller evidence, not human originals. Continuity needs the 2026-10-10 admission repair before co-use: skip memory preparation/original receipts for this prefix while retaining the raw provider recording. Its existing mirror then excludes the uncaptured controller and following tool result. Ordinary native human messages still use Memory. Panel-entered tasks remain controller evidence; this adapter does not separately import them as human Memory.

The local Continuity candidate has this repair and 256 passing offline tests; its two installed source files were updated with backup, the owner reported Reload. Real controller Memory exclusion and Recorder co-use remain is **CODE VERIFIED, LIVE UNVERIFIED**. This does not implement Luna/OAuth/embedding migration, memory quality acceptance or cognition rollover. Do not use the older installed MAIN script as evidence that this boundary is active.

This integration tests the shortest path from the already-proven `codex-chatgpt-web` browser transport into current WebCodex without making Codex model quota, DSH, or ChatGPT Full MCP a hard dependency.

```text
owner task
   |
   v
Penrix driver
   |                      (reasoning only)
   +--> codex-chatgpt-web /v1/responses --> ChatGPT Web browser-only
   |                                      |
   |<----------- strict JSON action ------+
   |
   +--> WebCodex /api/tools/call --> canonical ToolRuntime --> Runner --> Project
   |                                      |
   |<-------------- exact result ----------+
   |
   +--> next ChatGPT Web reasoning round ... --> final
```

The driver does **not** pretend browser-only ChatGPT has local tools. Each Web turn is a meta-task: choose one inert action proposal for a separate authorized driver. The local effect happens only after this process validates the proposal and sends it to WebCodex.

## Why this exists

Current WebCodex already owns Project authority, Workflow Sessions, Jobs, edits, validation, Git evidence, recovery and closeout. Current `codex-chatgpt-web` already owns the fragile ChatGPT Web browser submission/reply boundary. Re-implementing either side would duplicate the expensive parts.

The remaining gap for a Plus-style environment without a dependable Full MCP path is the small orchestration seam between them. Upstream WebCodex issue [#784](https://github.com/yyjeqhc/webcodex/issues/784) is investigating the broader model-gateway/context-continuity problem; this fork experiment stays deliberately removable.

## Current contract

The Web model must return exactly one strict JSON object per round:

```json
{
  "kind": "discover | call | final",
  "tool": "tool_name or null",
  "params": {},
  "text": "final text or null"
}
```

- `discover` asks WebCodex for the current exact `tool_manifest` contract. A tool cannot be called until its contract has been discovered or preloaded.
- `call` sends one admitted tool to the canonical `/api/tools/call` endpoint. The driver binds Project and Workflow Session fields mechanically when the current schema exposes them.
- `final` is accepted only when no required local work remains. Once a call that may change the Project workspace has crossed the driver boundary, the read-only `finish_coding_task` evidence snapshot must succeed **after the latest such change** before finalization. Session/attention-only mutations do not create this source-closeout requirement. The snapshot is evidence; it does not itself close the Workflow Session.

The default allowlist is coding-oriented, not administrative. `run_shell` is intentionally **not** enabled by default; `wait_for_job_terminal` is also excluded from the ordinary coding surface because it belongs to an explicitly established durable continuation workflow, while ordinary blocking uses `wait_for_job_readiness` and recovery/detail uses `observe_jobs`. An operator can add an exact extra tool with `--allow-tool` when the task really needs it and the WebCodex credential independently authorizes it.

## Safety / effect boundaries

The driver intentionally has no automatic retry loop.

- A ChatGPT Web transport disconnect stops with `outcome_unknown`; it does not send the same prompt again.
- Relay errors `chatgpt_submission_ambiguous` and `chatgpt_submitted_turn_failed` are also classified as `outcome_unknown`, because current `codex-chatgpt-web` says Send may have occurred / the task already started. They are never treated as a clean pre-send failure.
- A WebCodex transport disconnect also stops instead of replaying a possibly accepted effect.
- A non-idempotent/unknown canonical `Mutate` call with the same normalized arguments cannot be dispatched twice in one driver run. Canonical `Execute` calls remain distinct logical invocations (for example, rerunning the same validation command after new work); they are never automatic transport retries. WebCodex tools whose current manifest explicitly says `desired_state`, `keyed`, or `fenced_replay` may use their canonical replay/reconciliation contract.
- The model cannot retarget another Project or Workflow Session. The driver pins the selectors established by `work_on_project` and rejects conflicting proposals before calling WebCodex.
- Project-less Job observation/wait calls accept only opaque Job IDs / observation refs already observed in this fixed Project/Session's bootstrap, handoff, current-Project `list_jobs`, or current-Project tool results. Unknown Job identities are rejected before the request crosses to WebCodex.
- WebCodex HTTP 5xx after dispatch and canonical `output.execution_state="outcome_unknown"` both stop the current driver run. Canonical uncertainty may retain returned Job identity for later explicit recovery, but it never authorizes another effect in the same run.
- WebCodex remains the authority for authentication, scopes, schema validation, Runner capability, filesystem boundaries, Job identity and effect truth. The driver never treats its own transcript as execution proof.
- Redirects and ambient HTTP proxies are disabled for the two local/service calls, credentials cannot be embedded in configured URLs, and plain HTTP is accepted only on loopback.

## Requirements

- Python 3.10+
- current WebCodex Server + Runner, with a credential scoped for the tools you intend to use
- current `codex-chatgpt-web` relay reachable through its Responses endpoint (default `http://127.0.0.1:17841/v1`) and configured for the browser-only path used by this experiment; no native Codex model-catalog credential is part of this path
- an authenticated ChatGPT Web browser owned by that relay

The launcher's **Install into Codex** step is not a requirement for this Driver. It registers Web models and routing for Codex itself; this integration calls the relay's Responses endpoint directly. Keep the owner's existing Codex route. The browser-owning launcher and Responses service must run during browser inference, but WebCodex's own Server/Runner do not depend on Codex model registration.

The current Windows acceptance/probe target is exactly relay **6.1.7**, browser-only, with `chatgpt-web/gpt-5.6-sol`. Its supported standalone `serve` entry starts the Responses service without invoking Codex setup. An installed launcher version alone does not prove that the service is running; check `/healthz` and the actual version. Do not replace Codex routing to work around stale integration records.

On Codex CLI 0.160.1 for Windows, run the local `Start-Process` launch and URL health check as separate tool commands. Combining them can trigger its built-in URL-launch heuristic and produce `blocked by policy` even with full access. Split the two operations; do not disable approvals or protections to resolve this classification problem.

The driver reads the WebCodex bearer credential only from `WEBCODEX_TOKEN`; do not put it in command-line arguments or repository files.

## Example

PowerShell environment values are shown only as placeholders:

```powershell
$env:WEBCODEX_URL = "http://127.0.0.1:<webcodex-port>"
$env:WEBCODEX_TOKEN = "<project/runtime credential>"
$env:WEBCODEX_PROJECT = "<exact project id or ref>"
$env:CODEX_CHATGPT_WEB_URL = "http://127.0.0.1:17841/v1"

python integrations/penrix_chatgpt_web/driver.py --task "Inspect the current bug, make the smallest justified fix, validate it, and close out the WebCodex Session."
```

To resume an exact durable Workflow Session after the browser/model process is gone:

```powershell
python integrations/penrix_chatgpt_web/driver.py --session "~s1" --task "Continue from the saved handoff and finish the current task."
```

The driver re-enters through `work_on_project`, reads `session_handoff_summary`, and gives that current durable state to a fresh Web reasoning context. When the compact handoff is not enough to reconcile an exact prior Job/effect fact, the planner may discover the read-only canonical `session_summary` and inspect its bounded durable ledger tail before proposing overlapping work. That summary is evidence, not a raw-argument archive: omitted/redacted arguments are never inferred. The previous ChatGPT browser conversation does not need to survive.

Each relay round also carries the minimum current `codex-chatgpt-web` browser identity contract: one stable driver `thread_id`, one fresh `turn_id`, matching current-user turn provenance, and `prompt_cache_key`. The driver does not invent Codex filesystem/sandbox authority; browser-only mode does not need that environment surface.

## REST context boundary

This experiment intentionally uses WebCodex's canonical `/api/tools/call` REST path. That path does not provide the MCP invocation-envelope `_wc.context` sidecar used for projected `project.instructions` / `webcodex.workflow` material.

Consequences for this first slice:

- the full `work_on_project` bootstrap result is still handed to the Web model;
- when bootstrap reports instruction sources without their bodies, the Web model must use canonical read tools such as `read_files` before an instruction-dependent mutation;
- the driver does not pretend that REST returned MCP context sidecars;
- switching the orchestration seam to MCP remains a later option only if live evidence shows this missing projection materially hurts the workflow.

## Validation performed so far

Deterministic stdlib fake-server tests cover:

- text-format Responses requests with a schema-guided literal JSON code block, while the driver strictly parses and validates the returned action;
- current relay thread/turn identity and current-user turn provenance;
- positive Responses completion evidence (`status=completed` + `end_turn=true`) before any action is accepted;
- fixed Project + exact Workflow Session injection;
- Project retarget rejection before an effect;
- contract discovery before non-preloaded tools;
- current ordinary `review_changes` discovery is preloaded alongside the edit/validation/closeout path;
- source-changing work cannot finalize before `finish_coding_task`; omitted `summary_only` is pinned to the current upstream normal-closeout default (`true`) while an explicit caller choice is preserved;
- non-idempotent canonical mutation with identical normalized arguments is sent only once, while repeated canonical `Execute` calls remain distinct logical invocations;
- every default admitted tool name exists in the exact checkout's canonical `ToolCall::tool_name()` registry, catching rename drift such as `workspace_hygiene_check`;
- exact Session resume reads the saved handoff, and can recover an authoritative prior Job identity on demand through `session_summary` before observing that Job;
- relay disconnect is not automatically retried;
- current relay post-Send uncertainty codes stop as `outcome_unknown` for both HTTP-error and HTTP-200 failed-envelope forms, without a second Web request;
- HTTP 200 with an incomplete/non-terminal Responses envelope cannot drive a WebCodex effect;
- a WebCodex mutation whose response transport drops stops immediately with `outcome_unknown` and does not ask the model for another action.
- a later workspace mutation invalidates an older `finish_coding_task` snapshot;
- Session-only mutation does not force a false source closeout;
- an opaque Job from outside current-task evidence is rejected while a Job returned by the fixed Project can be observed;
- WebCodex HTTP 500 and canonical `execution_state=outcome_unknown` stop without a follow-on effect, while the canonical uncertain Job identity is retained for explicit recovery;

Run locally on Windows:

```text
python -m unittest discover -s integrations/penrix_chatgpt_web/tests -v
```

The fork also carries `.github/workflows/penrix-chatgpt-web-driver.yml`, a Windows-only five-minute contract lane that compiles the driver/test sources and runs exactly this suite when the integration changes.

These tests alone prove driver logic. Separate owner-machine acceptance on 2026-10-09 verified actual browser reasoning, Windows edits, long Job success, review/closeout and exact Session recovery after Server/Runner/Driver restart. See the [target acceptance record](../../docs/acceptance/penrix-windows-2026-10-09.md). The everyday conversation entry and cognition continuity remain unverified.

## Windows live carrier

Real ChatGPT test sends use the acceptance-only `real_test_driver.py`, not the ordinary production Driver entry. It shares the existing Continuity operator file `~/.codex/chatgpt-continuity-real-test-gate.json` and its exclusive-create `.lock`. Unknown last-send time waits at least 30 seconds; each validated completed reply is followed by at least 30 seconds before another test request. Longer recorded cooldowns are preserved. The lock covers the request and exact response validation, including fresh-process Session resume. A limit, challenge, transport failure, incomplete response, malformed action or process interruption stops testing; the shared stop is never automatically cleared. Other account test senders must use this same operator gate; ordinary/manual sends are not intercepted by it. Do not reset a stop without reconciling the actual browser outcome.

The carrier now retains both the disposable workspace **and** its canonical WebCodex state on failure. A fresh Session/Job recovery investigation must use that retained state; deleting it while retaining only source files would destroy the evidence. Ordinary `driver.py` has no test cooldown.

Upstream 0.4.4 source remains the reviewed and pinned baseline for this Provider acceptance. Upstream has since published v0.4.6 (2026-10-03), including additional Windows/runtime fixes, but this PR deliberately does not mix that upgrade into the current Stage A evidence. The exact fork-built 0.4.4 Windows runtime remains the acceptance target for this branch; evaluating/rebasing onto v0.4.6 is a separate follow-up after the Provider loop is proven.

`.github/workflows/penrix-windows-live-candidate.yml` builds the exact PR source on a real `windows-latest` runner, then runs:

```text
python integrations/penrix_chatgpt_web/live_acceptance.py --share-probe-only --webcodex-bin-dir target/dogfood
```

That probe creates a disposable Git repository, starts the real `webcodex share --tunnel none --json --stop-on-stdin-eof` path, requires `local_ready`, closes stdin, and requires clean Server/Runner cleanup. Only after that does the workflow upload the exact three Windows runtime binaries together with the driver and live carrier.

For the target-machine acceptance, extract that candidate on Windows, start the current `codex-chatgpt-web` relay with an authenticated ChatGPT Web session, then run from the candidate root:

```powershell
python integrations\penrix_chatgpt_web\live_acceptance.py --webcodex-bin-dir .
```

The carrier:

- refuses WebCodex versions other than 0.4.4;
- proves the configured `chatgpt-web/gpt-5.6-sol` route by completing real browser-only Responses turns under the literal text transport / strict driver boundary; it does not call `/v1/models`, because that catalog endpoint is a native-Codex passthrough requiring Codex Bearer auth;
- creates a disposable temporary Git project instead of touching a real repository;
- starts local WebCodex Server + Runner + Project through upstream `share`;
- never reads WebCodex secret files or prints the temporary credential;
- relies on upstream's normal clipboard handoff and reads the staged temporary Bearer once through the Windows clipboard API; the credential is validated by shape and is never printed or persisted;
- resolves the exact canonical Project through `list_projects` instead of trusting a display name;
- makes ChatGPT Web repair one intentionally failing one-line Python fixture through the driver;
- requires one disposable `run_process` fixture that lasts more than the canonical 10-second sync-first grace, then requires the driver log to prove the same execution was observed through `observe_jobs` before completion;
- requires successful Runner-side unittest evidence, change review, and `finish_coding_task` evidence;
- independently rechecks the resulting file/test locally;
- starts a fresh driver process with the returned `~s...` ref and requires exact Session handoff recovery without another mutation;
- stops `share` through its documented stdin-EOF contract and deletes the disposable repository only after a clean pass.

A failure stops at the first blocker and retains the temporary repository for diagnosis. It does not retry effects, repair login state, disable Defender, broaden Project authority, or silently switch to v0.4.3.

## First live acceptance

Use the Windows live carrier above. Its target-machine flow exercises the same acceptance sequence in one disposable project: real Server/Runner bootstrap, real ChatGPT Web browser-only reasoning, read/edit/process validation, `finish_coding_task` evidence, local result recheck, and fresh-process exact Session resume.

Stage A passed on 2026-10-09 through the successful initial coding loop and subsequent retained recovery after repairing the carrier's Git-status parsing. The original carrier invocation failed locally before recovery; it was not rerun to repeat successful effects. This acceptance does not establish integration with the owner's existing conversation or cognition.

## Same-conversation Chrome entry (candidate)

This entry uses the ChatGPT page already open in Chrome and the local canonical WebCodex runtime. It does not need Codex Web GPT, official Plus MCP, or **Install into Codex**. Continuity remains a separate follow-up. Real same-chat read/edit/test/result return and service-restart correction passed on a disposable project. Explicit chat transfer has canonical Windows runtime and simulated-browser proof; its real Chrome activation and acceptance remain pending.

The candidate root contains `Start-WebCodex.cmd`, `Start-WebCodex.ps1`, the three reviewed 0.4.4 executables and `integrations/penrix_chatgpt_web/browser_extension`. Windows requires Git and Python 3.12 or newer on PATH.

1. In Chrome's normal **Extensions → Developer mode → Load unpacked** flow, select the candidate's `integrations/penrix_chatgpt_web/browser_extension` directory. This is a one-time local extension installation. No login migration or Codex configuration change is needed.
2. Double-click `Start-WebCodex.cmd` and select the local Git project you authorize. Startup reports success only after the local entry announces readiness. Logs live under `~/.codex/webcodex-browser-logs`.
3. Open or refresh an existing `https://chatgpt.com/c/<id>` conversation. Click **WebCodex → 连接项目**. Enter the task in the panel, or leave it empty to use your last native chat message; click **开始 / 恢复**.
4. Use **暂停** before changing direction. Supply a correction in the panel and click **开始 / 恢复** after the current reply finishes. A new native user message during work also pauses the loop. Resume reads the same saved canonical Session; it does not replay an old proposal.
5. To continue in another existing conversation, pause the old execution and wait for its reply/worker to finish. In the destination chat click **转移到本聊天**. This retains the exact Session, revokes the old tab binding and stays paused. Supply the next instruction and click **开始 / 恢复** to read the canonical handoff before continuing. Transfer refuses active work or pending delivery; it never starts or sends by itself.
6. **关闭本地服务** stops the browser entry and its Server/Runner after the worker has stopped. Canonical state and the exact Project/Session/conversation pointer remain under `~/.codex/webcodex-browser-state`. A project already bound to one conversation cannot silently move to another.

For an explicit project, the PowerShell launcher supports `-ProjectDir "C:\path\to\repo"`. Agent-initiated real acceptance must also pass `-RealTest`; this wraps the actual request through completed reply validation in the existing account-wide 30-second gate. Never use normal mode to bypass acceptance cadence.

The extension's background owns the local credential and admits only its own top-level ChatGPT sender and bound tab. The loopback service admits only the stable extension Origin and exact Host, then checks its bearer. Message IDs must be unique, replies complete and newly observed, and the envelope must match the claimed request. Reload, timeout, ambiguous delivery or a blocking page stops execution without resending. Page-shape mismatches stop before claiming a request.

The native DOM hooks were inspected on the owner's page and exercised in real Chrome on 2026-10-10. Fixed-Origin pairing, unique matching completed replies, a fenced file edit, one long-running test Job and result return passed on the disposable project. The observed ProseMirror editor uses one paragraph per logical line; the send check reconstructs those exact lines rather than comparing paragraph-spacing `innerText`. Empty lines and indentation remain significant. See [current acceptance evidence](../../docs/acceptance/penrix-browser-entry-2026-10-10.md) for exact recovery, correction and unverified boundaries. No other ChatGPT extension is a declared dependency.

Offline browser checks:

```text
node --test integrations/penrix_chatgpt_web/tests/browser_protocol.test.cjs integrations/penrix_chatgpt_web/tests/browser_extension.test.cjs
```

The Node DOM/API simulations prove local admission decisions only. The real Server/Runner transport fixture, which sends no ChatGPT messages, is `tests/browser_runtime_acceptance.py <candidate-root>`.

### Literal action transport

Relay 6.1.7 serializes browser HTML as Markdown. The Driver requests text output containing exactly one fenced JSON object, with the action schema supplied as format data. The code block protects source/path backslashes from prose Markdown escaping. Fenced JSON is parsed literally, without escape repair, and all existing action, Project, Session, Job and tool admission checks remain authoritative. Additional prose or multiple JSON values fail before dispatch. Older observed raw JSON responses retain the narrowly proven single-escape compatibility parser; double-escaped malformed proposals remain rejected. Assistant history replays canonical parsed JSON, never the transport's presentation escapes.
