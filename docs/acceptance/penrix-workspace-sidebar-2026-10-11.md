# User workspace, sidebar and task records — 2026-10-11

Owner authorized the entire `C:\Users\123` user directory, after requesting broader operation than one Git project. This unit also completes the pending larger input/sidebar and local task/final-result records. Parent adapter revision: `8f457bad074e51cd619a0611f903d2517b1bd27c`; runtime binaries remain the reviewed 0.4.4 build `25dccf12cdece192500f9a97f8318cc8c278b55c`.

## Current implementation

- Default launcher targets the current user directory. `-WorkspaceDir` selects a narrower ordinary folder; `-ProjectDir` preserves the prior Git-project share path. No Git initialization of personal folders.
- A direct non-Git `share` probe failed with `workspace_unavailable`: the selected directory is not a supported Git project. The new workspace path therefore uses the existing canonical `server init`, `runner init` and `project register` contracts and the original Server/Runner binaries. It does not remove canonical file fences or permissions.
- Dedicated workspace Server listens on IPv4 loopback. Runner `allowed_roots` is exactly the selected workspace and `allow_cwd_anywhere=false`; authority is checked before startup. Driver still pins one canonical Project and exact Session. Workspace path is visible in the panel and supplied as controller context.
- Private runtime state lives outside the workspace in `%PROGRAMDATA%/Penrix-WebCodex/<root-hash>`; its protected inheritable DACL grants only current user and SYSTEM. Credentials remain in private state/service worker, never page messages or package. Server/Runner own EOF shutdown. Git-project state and bindings are retained separately.
- File tools enforce workspace paths. `run_process` retains canonical process semantics and runs with current-user OS authority; there is no new OS sandbox. Nested Git repositories can be handled through a process with that child directory as `cwd`.
- Full-height sidebar defaults to 520px, resizes with drag or keyboard, collapses without losing its draft, and has scrollable task/results. Secondary transfer/exit actions are collapsed. Short windows can scroll the whole panel; a clipped-controls defect found during 1000×520 rendering was fixed.
- Local records retain latest 30 task/final-result pairs globally within 4 MiB; per-result text cap 32,000 characters is visibly marked. Partition is Project + conversation, update identity is `run_id`. Offline lookup requires no server. Atomic previous-run snapshot preserves a just-completed final when next Start precedes polling; per-run snapshot ordering prevents late state regression. SPA navigation reloads the destination records and rejects delayed old-route responses. Storage failure does not replay execution. This is not a duplicate full-chat Recorder or Memory runtime.
- Connect no longer requires a mounted native composer. Start/send wait within the existing bounded deadline for exactly one input; multiple inputs stop before Start/claim. On the owner's reported page the transient failure had disappeared; only one current visible composer was observed. The original zero-versus-multiple cause was not captured, so a specific original root cause is NOT VERIFIED.

## Evidence

**LIVE VERIFIED — Windows canonical workspace runtime, synthetic actions, zero ChatGPT sends.**

`python -X utf8 integrations/penrix_chatgpt_web/tests/workspace_runtime_acceptance.py <r4-runtime>` used the actual authorized root `C:\Users\123`, dedicated `C:/ProgramData/Penrix-WebCodex/acceptance-home` state, and new disposable `webcodex-proof-*` folders in Documents and Downloads. It read both sibling folders, performed a revision-fenced text edit, ran Python with Downloads child cwd and verified `SIBLING_CWD_OK`, rejected `C:/Windows/win.ini`, completed canonical `finish_coding_task`, stopped/restarted the real Server/Runner and recovered the exact Session. Project `agent:browser-workspace:123`; final passing Session `wc_sess_SSao_jH6KO9e1Yfp`. No existing personal documents were inspected or modified. Local log: `diagnostics/webcodex-20261011/workspace-runtime.log` in the owner workspace outside the repository. Earlier diagnostic proof folders are retained as test artifacts.

**LIVE VERIFIED — Chrome renders exact production content.js against local synthetic page.**

Local fixture `http://127.0.0.1:18789/c/fixture` exercised multi-paragraph draft, collapse/reopen preservation, keyboard width 520→540px, task/result scrolling, secondary controls, and responsive 996×910, 390×640, 1000×520 windows. Short expanded controls became accessible through panel scrolling; viewport was reset after testing. This fixture has mocked extension RPC and does not prove real extension storage persistence or native ChatGPT DOM integration. Screenshots: owner workspace `diagnostics/webcodex-20261011/sidebar-desktop.png` and `sidebar-narrow.png`.

**CODE VERIFIED, LIVE UNVERIFIED — new Chrome extension activation/persistence and complete browser-to-home task.**

85 Python tests and 22 Node tests pass. These cover prior admission/replay/Session/Job semantics and new history storage, worker restart, retention/failure, unique composer wait, previous-run retention, stale snapshot suppression, offline lookup and SPA route handling. Independent review found history/routing defects; their fixes have focused regressions, including a delayed response crossing navigation and a pending composer wait crossing an explicit transfer. Existing same-chat real ChatGPT read/edit/test/restart/correction evidence remains in [2026-10-10 acceptance](penrix-browser-entry-2026-10-10.md). It is not upgraded to live proof of this new home-workspace/record build. New build marker: `20261011-user-workspace`.

Activation requires one owner Chrome extension Reload and a refresh of the intended existing ChatGPT conversation; browser control cannot operate the restricted extension-management page. Then connect the running workspace, inspect its displayed scope and use ordinary tasks. No new real ChatGPT acceptance sends were made in this unit. Real agent tests still require the actual `--real-test` shared account gate, at least 30 seconds after a completed reply, preserving longer waits and stopping on challenges/limits.

**NOT VERIFIED / BLOCKED:** real Chrome storage eviction/reopen retention after activation, a complete real ChatGPT-to-user-home task on this new build, arbitrary document-format conversions without installed-library checks, daily long-running usage, cross-chat cognition/Recorder/OpenViking co-use. Continuity remains deferred; this unit does not complete the cognition-memory system. Draft PR #2 remains unmerged.

## Deployment and handoff

Adapter commit: `01414ff2df46d10b684fa506e1cdfd14e381de3f`. Local candidate `C:\Users\123\Documents\Codex\webcodex-runtime\browser-entry-20261011`; ZIP sibling `browser-entry-20261011.zip`, 38,293,430 bytes, SHA256 `849c6f9d8c5a833cc3a46e6a903d3e6913d0e1ee032cbaab9ea83c2dd897b10d`. All 34 listed files and ZIP integrity verified. Binaries remain the same reviewed build. Embedded acceptance records precede this deployment-only addition.

Existing unpacked candidate directories `browser-entry-20261010`, `-r2`, `-r3`, `-r4` received guarded source overlays, with originals backed up to owner workspace `diagnostics/webcodex-20261011/workspace-deployment-backup`. Historical ZIP hashes were unchanged. Source/metadata/hashes were read back after overlay; no Codex configuration or personal project files changed.

The exact new top-level PowerShell launcher was invoked with `-WorkspaceDir C:\Users\123` and returned readiness. Authenticated loopback `/status` readback confirmed `state=idle`, `workspace_root=C:\Users\123`, `project=agent:browser-workspace:123`, no Session/run yet, ordinary mode. Server is left running for owner use; no task was started. Only the local synthetic browser fixture was stopped after QA.

Remaining activation: owner Reload of the already-installed Chrome extension, refresh the intended existing ChatGPT page, then **连接工作区**. No reinstall or Codex Web GPT needed. GitHub reports empty workflow/status lists for adapter commit; this is not CI success. PR #2 remains Draft/unmerged.
