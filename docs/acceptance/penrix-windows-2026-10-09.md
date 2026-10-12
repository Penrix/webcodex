# Penrix Windows acceptance — 2026-10-09

## Revision and environment

- Source baseline and binary: PR #2 head `25dccf12cdece192500f9a97f8318cc8c278b55c`, WebCodex 0.4.4. PR remains Draft/unmerged.
- Candidate artifact `11295883995`; ZIP SHA-256 `a658d325968ce71d7381c30992800425f9068c225709b8410d01e3e1a9c33251`. SOURCE.txt matches the head.
- Target: owner's Windows 10 build 19045, Python 3.14. Local working changes add test pacing and preserve failure evidence; they have no new hosted CI identity yet. Runtime binaries are unchanged.
- Exact baseline hosted driver, Windows candidate and repository CI succeeded (`37183471020`, `37183471031`, `37183470966`). These results do not validate subsequent local source changes.

## Verified behavior

**LIVE VERIFIED:** exact candidate `share --tunnel none --json --stop-on-stdin-eof` starts local Server/Runner, reports `local_ready`, and cleans up on stdin EOF. This lifecycle probe sends no ChatGPT message.

**CODE VERIFIED:** 71 offline Python tests passed after adding the shared test gate, literal JSON transport, canonical action history and the Git porcelain regression. Fake-clock and local fake-HTTP tests exercise actual Driver dispatch, completed-reply cooldown, fractional timestamp rounding, longer cooldown preservation, exclusive locking, and refusal after HTTP 429 or uncertain completion. Compilation and whitespace checks passed. Ordinary production inference has no newly added cooldown.

## First target run: stopped before Send

The first full disposable acceptance opened a canonical Project and Workflow Session. After the implemented 60-second initial cooldown, its first model call stopped with `model_version_unavailable` on installed relay 6.1.3. Dispatch reservation: `2026-10-09T11:55:41.754Z`.

Browser trace `2751fea37327-7fc92d22` ends at `06-turn-failed`, captured `2026-10-09T11:55:56.755Z`. Its error explicitly says the pending message was not sent. Earlier checkpoints show an empty composer and no user/assistant turns; there are no send-ready, send-accepted or response-visible checkpoints. Installed source constructs this error in model selection before submission. No rate limit, unusual-activity or CAPTCHA was observed. The repository remains clean; no model-proposed tool or local edit occurred.

Local diagnostics: `C:\Users\123\Documents\Codex\diagnostics\webcodex-20261009\live-acceptance.log` and `C:\Users\123\.codex-chatgpt-web\diagnostics\browser-turns\2751fea37327-7fc92d22`. The failed disposable workspace `C:\Users\123\AppData\Local\Temp\penrix-webcodex-live-if95rjrs` and its sibling `-webcodex-state` are retained. Credential contents must not be copied into reports or commits.

The shared operator stop was retained pending this reconciliation. A repaired run must not replay uncertain effects. This specific failure is positively pre-send; it is not evidence of an unknown accepted message.

## Dependency repair

Upstream [6.1.7 release](https://github.com/miuuyy/codex-chatgpt-web/releases/tag/v6.1.7) incorporates model selection fixes after the ChatGPT UI update, with further parallel-tab and localized-selector repairs. The downloaded Windows installer has verified SHA-256 `6a32711033b227ed23c67a8354904aff0e060962be74bd26b7c028e74c2ffbc9`. The acceptance/probe target is now exactly 6.1.7; the existing 5.6 Sol route remains explicitly supported upstream.

Program, core home, launcher profile and Codex config have local rollback copies under `webcodex-runtime\relay-6.1.7\backup`. The installation must preserve the existing login and must not replace the owner's newer Codex route. Original Codex config SHA-256: `5f9ac7bdffe65ec0149be8947343306d29770ed80b85b07efea9d0b75046257d`.

The installer completed with exit 0 and the installed package reports 6.1.7. Codex config hash remains identical. The launcher's automatic runtime upgrade refuses the newer Codex route before completing setup; saved core config remains at 6.1.3. At `2026-10-09T12:15:35.870Z` the launcher logged authenticated using the existing profile. Startup also logged Cloudflare challenges on backend requests, so agent-initiated tests remained stopped at that point. A later successful UI smoke and a fresh read-only authenticated session inspection allowed a reconciled new run, recorded below.

At `2026-10-09T12:20:23.043Z` the launcher recorded a UI smoke test completing at High, after send-accepted and turn-completed checkpoints. This was not dispatched by the WebCodex Driver or this agent's acceptance entry. It does not prove local tools, exact Session resume, or the owner's conversation integration.

The initial bundled standalone `serve` launch was rejected with `blocked by policy`. Investigation established a command-classification false positive, not a user rejection or model approval-review decision. Active Codex CLI is 0.160.1 with approval policy `Never`, full access, and no loaded command-rule files. Its [pinned Windows classifier](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/shell-command/src/command_safety/windows_dangerous_commands.rs) treats a PowerShell invocation containing both a URL and `Start-Process` as dangerous. The combined launch-plus-health-check script matched that condition even though the URL belonged to a separate HTTP health check. The [pinned execution policy](https://github.com/openai/codex/blob/rust-v0.160.1/codex-rs/core/src/exec_policy.rs) rejects that classification under `Never` and gives the generic message for `DangerousCommandMatch::Other`.

Executing local launch and HTTP health check as separate commands resolved the false positive through the same normal tool. No policy, approval setting or guard was modified. **LIVE VERIFIED:** the standalone service started as PID 18948; `/healthz` reports 6.1.7, browser-only, accepting turns, with zero active HTTP/browser turns. Codex config hash remains unchanged. This validates service startup, not a new model turn. The separate **Install into Codex** setting is unnecessary for this Driver and was not changed.

Current field reports also describe incomplete-response/DOM and viewport problems: [Windows #793](https://github.com/miuuyy/codex-chatgpt-web/issues/793), [6.1.6 #795](https://github.com/miuuyy/codex-chatgpt-web/issues/795), [6.1.7 #804](https://github.com/miuuyy/codex-chatgpt-web/issues/804). They support retaining exact completion evidence and stopping on uncertainty; they do not establish those bugs on this owner's run.

## Second target run: read succeeded, malformed edit proposal stopped

After explicit owner continuation and reconciliation of the pre-send failure, relay 6.1.7 completed two real browser-only turns. First dispatch `1791549326.952`, completed validation `1791549352.070`, next dispatch `1791549412.070`: the then-configured 60-second completed-reply cooldown was enforced. Browser traces `268dcccd732b-f3f7a5ef` and `7f9972d00bae-7de2d34f` show accepted and completed turns; the second completed at `2026-10-09T12:37:14.017Z`. No rate limit, challenge or ambiguous completion occurred in this run.

The first action performed canonical `read_files`. The second proposed `edit_project_files` but its returned Markdown presentation contained double backslashes before structural brackets and underscores. JSON parsing failed before dispatch. Retained Session `wc_sess_yHGUuO8a_MKKlXfp` has only manifests and read-file events, `repository_edit_observed=false`, no Job, no edit, and a clean Git diff. Workspace `C:\Users\123\AppData\Local\Temp\penrix-webcodex-live-5tnyo5cl` and its canonical state remain retained. Log: `diagnostics/webcodex-20261009/live-acceptance-617.log`.

Offline investigation reproduced an action-history defect: the Driver replayed the transport's escaped raw text even after parsing a correct action. It now replays the parsed action as canonical JSON. A regression first failed on invalid JSON in the second request history, then passed after the repair. This removes presentation escapes from history without guessing edits to literal file/path backslashes. It does not yet prove that every real malformed proposal is eliminated.

The owner's newer instruction sets future real tests to **at least 30 seconds after completed reply**, across the account. The actual acceptance/probe gate, fake-clock and HTTP-path tests, and operating documentation now implement 30 seconds. Unknown previous send time also waits 30 seconds. Existing longer deadlines remain intact; failures still stop and never automatically retry. Historical timestamps above retain the actual 60-second behavior of that earlier run.

## Third target run and literal JSON transport repair

With canonical action history and the owner's 30-second cadence, first dispatch was `1791549961.716`, completed validation `1791549984.243`, second dispatch `1791550014.243`. The observed completed-reply interval is exactly 30 seconds. Traces `bb2ebba92297-36c0e8b0` and `bb5df8ccd2da-820d0317` completed. The edit proposal still had double escapes and stopped before dispatch, proving that canonical history alone did not resolve the live transport format. Workspace `penrix-webcodex-live-qr_4wjny` and state are retained; no effect is inferred from a malformed proposal.

The relay's exact 6.1.7 prompt source forbids code fences for `json_schema` output, while its Markdown buffer converts HTML through Turndown. The Driver now requests text output with an explicit one-JSON-code-block contract and supplies the same action schema as inert format data. It admits only a single JSON object, with strict action/tool validation unchanged. Fenced content receives no escape repair; prose, multiple values/blocks and invalid JSON are rejected. Parsed action history stays canonical JSON.

An offline probe using the **installed** Turndown module reproduced double escaping of Markdown-escaped JSON prose, and verified exact literal file/path backslashes through a fenced code block. No ChatGPT message was sent for this probe. Probe: `diagnostics/webcodex-20261009/json-transport-offline.cjs`. All 69 integration tests, compile and whitespace checks passed. This transport change still requires a fresh real acceptance.

## Fourth target run: actual coding succeeded; local carrier misclassified Git status

The literal JSON transport completed nine real Web rounds. Canonical read, `edit_project_files`, exactly one `run_process`, exact Job observation, `review_changes`, `finish_coding_task` and the final model reply all succeeded. Session `wc_sess_YZDSYNk7kzu5fwpU` recorded Job `wc_job_N5vnn0ku_MEkXA67`, terminal success and exit 0 for `python slow_acceptance.py` (12,317 ms). Its retained validation excerpt reports one passing unittest. No rate limit, challenge or ambiguous completion occurred.

The local carrier then failed before its fresh-Driver resume: `run_checked()` stripped leading spaces from Git porcelain output, turning the expected ` M acceptance.py` into `M acceptance.py`. The fix preserves command stdout; version comparisons strip only their own version text. A real temporary Git repository regression reproduced the failure and passes after the fix. Local re-verification of the retained workspace also passes; only `acceptance.py` changed.

The gate's integer millisecond truncation could shorten the deadline by less than 1 ms; it now rounds upward and logs the same completion timestamp used for the deadline. A fractional-clock regression proves at least 30 seconds. The old run's rounded first completion/next dispatch timestamps (`1791550497.385` / `1791550527.384`) must not be described as strict 30-second proof.

Main run log: `diagnostics/webcodex-20261009/live-acceptance-30s-literal-json.log`. Retained workspace: `C:\Users\123\AppData\Local\Temp\penrix-webcodex-live-l9bg5dfc`; canonical state is its sibling `-webcodex-state`. The recovery investigation restarts Server/Runner on that exact state and resumes the same Session without repeating edits or the long validation execution. Do not run the initial acceptance again merely to replace this evidence.

## Retained recovery: passed after Server, Runner and Driver restart

The exact canonical Project and Session were accessible after restart. A fresh Driver resumed `wc_sess_YZDSYNk7kzu5fwpU` (`~s1`) and completed six Web rounds. It read current `acceptance.py`, discovered the read-only summary contract and recovered the prior Job's terminal success from `session_summary`. Its final answer cited exit 0 and the prior passing unittest. No new `edit_project_files`, `run_process` or `project_validate` events occurred. Independent local file/test verification passed and the before/after Git diff was identical. Share shutdown completed through stdin EOF; workspace and state remain retained for evidence.

Every next dispatch in this recovery run was at least 30 seconds after the logged prior completed reply (`30.001`, `30.002`, `30.001`, `30.002`, `30.001` seconds). Evidence: `diagnostics/webcodex-20261009/retained-resume.log` and `retained-resume-result.json`.

**LIVE VERIFIED for Stage A:** real browser reasoning, canonical read/edit/long Job/validation/review/finish and exact restarted-Session recovery. This is combined evidence from the initial successful coding loop and the subsequent retained recovery after repairing the carrier; it is not a claim that the original single carrier invocation exited successfully.

## Remaining target

The owner's existing conversation, corrections, cognition recovery and everyday entry remain pending product requirements. A successful isolated planner loop alone cannot satisfy them. The owner confirmed that Plus lacks the official MCP permission required for the direct route; the browser adapter is intentional, and a visible MCP creation form does not change that constraint. See [product context](../agent/penrix-product-context.md). No push, publication or release occurred; PR #2 remains Draft/unmerged.
