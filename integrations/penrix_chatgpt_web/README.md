# Penrix ChatGPT Web driver

> Status: **CODE VERIFIED, LIVE UNVERIFIED**
>
> Fork-local experiment. This is not an upstream WebCodex product surface and does not change canonical ToolRuntime semantics.

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

The default allowlist is coding-oriented, not administrative. `run_shell` is intentionally **not** enabled by default; an operator can add an exact extra tool with `--allow-tool` when the task really needs it and the WebCodex credential independently authorizes it.

## Safety / effect boundaries

The driver intentionally has no automatic retry loop.

- A ChatGPT Web transport disconnect stops with `outcome_unknown`; it does not send the same prompt again.
- Relay errors `chatgpt_submission_ambiguous` and `chatgpt_submitted_turn_failed` are also classified as `outcome_unknown`, because current `codex-chatgpt-web` says Send may have occurred / the task already started. They are never treated as a clean pre-send failure.
- A WebCodex transport disconnect also stops instead of replaying a possibly accepted effect.
- A non-idempotent/unknown mutating tool call with the same normalized arguments cannot be dispatched twice in one driver run. WebCodex tools whose current manifest explicitly says `desired_state`, `keyed`, or `fenced_replay` may use their canonical replay/reconciliation contract.
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

The driver re-enters through `work_on_project`, reads `session_handoff_summary`, and gives that current durable state to a fresh Web reasoning context. It does not require the previous ChatGPT browser conversation to survive.

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

- strict JSON-schema Responses request construction;
- current relay thread/turn identity and current-user turn provenance;
- positive Responses completion evidence (`status=completed` + `end_turn=true`) before any action is accepted;
- fixed Project + exact Workflow Session injection;
- Project retarget rejection before an effect;
- contract discovery before non-preloaded tools;
- current ordinary `review_changes` discovery is preloaded alongside the edit/validation/closeout path;
- source-changing work cannot finalize before `finish_coding_task`; omitted `summary_only` is pinned to the current upstream normal-closeout default (`true`) while an explicit caller choice is preserved;
- non-idempotent mutation with identical normalized arguments is sent only once;
- exact Session resume reads the saved handoff;
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

These tests prove driver logic only. They do **not** prove the current Windows WebCodex build, the local `codex-chatgpt-web` launcher/login, a real ChatGPT Web strict-output turn, or a real edit/Job round-trip. Those remain **LIVE UNVERIFIED** until exercised on the target Windows machine.

## Windows live carrier

Upstream 0.4.4 source is the reviewed baseline, but the latest published WebCodex release is still v0.4.3. The fork therefore does not use the published v0.4.3 Windows installer as acceptance evidence for this path.

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
- proves the configured `chatgpt-web/gpt-5.6-sol` route by completing real browser-only Responses turns; it does not call `/v1/models`, because that catalog endpoint is a native-Codex passthrough requiring Codex Bearer auth;
- creates a disposable temporary Git project instead of touching a real repository;
- starts local WebCodex Server + Runner + Project through upstream `share`;
- never reads WebCodex secret files or prints the temporary credential;
- relies on upstream's normal clipboard handoff, then asks the owner to paste that temporary Bearer once into hidden console input;
- resolves the exact canonical Project through `list_projects` instead of trusting a display name;
- makes ChatGPT Web repair one intentionally failing one-line Python fixture through the driver;
- requires Runner-side `python -m unittest -v`, change review, and `finish_coding_task` evidence;
- independently rechecks the resulting file/test locally;
- starts a fresh driver process with the returned `~s...` ref and requires exact Session handoff recovery without another mutation;
- stops `share` through its documented stdin-EOF contract and deletes the disposable repository only after a clean pass.

A failure stops at the first blocker and retains the temporary repository for diagnosis. It does not retry effects, repair login state, disable Defender, broaden Project authority, or silently switch to v0.4.3.

## First live acceptance

Use the Windows live carrier above. Its target-machine flow exercises the same acceptance sequence in one disposable project: real Server/Runner bootstrap, real ChatGPT Web browser-only reasoning, read/edit/process validation, `finish_coding_task` evidence, local result recheck, and fresh-process exact Session resume.

Only after that should this path be promoted beyond **CODE VERIFIED, LIVE UNVERIFIED**.
