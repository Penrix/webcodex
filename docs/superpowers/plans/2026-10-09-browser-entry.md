# WebCodex browser entry implementation plan

> **For agentic workers:** Use superpowers:executing-plans inline; the owner authorized doing the work in this chat. Tasks use checkboxes.

**Goal:** Connect an existing ChatGPT conversation to an authorized Windows project with tool result return, pause and exact Session recovery.

**Architecture:** Keep the tested Driver and canonical WebCodex runtime. Add one loopback browser transport and a thin Chrome extension; no second execution or memory system.

**Tech Stack:** Python stdlib, Chrome MV3, JavaScript, existing WebCodex 0.4.4 candidate.

**Spec:** `docs/superpowers/specs/2026-10-09-browser-entry-design.md`

## Global Constraints

- Continuity deferred; preserve existing login/config, Stage A fixes and retained evidence.
- Owner's later runtime-002 context prompted only the narrow controller/human provenance repair in Continuity. Its model/OAuth/embedding migration remains deferred. New two-file candidate needs Reload and affected-page refresh before co-use; source/test evidence is recorded in both repositories.
- Local service 127.0.0.1:17842; fixed project, exact extension origin, credential isolation.
- No tool/reply/send retries on ambiguity; claim before Send; canonical Job truth only.
- Real tests use account-wide >=30s completed-reply gate before actual browser dispatch.
- Separate offline, real runtime and real ChatGPT acceptance claims.

## Review Focus

- Streaming or unrelated assistant text cannot become a tool request.
- Reload or duplicate polling cannot cause a second Send or effect.
- A different tab/conversation cannot consume the connected project's request.
- Pause during a reply or effect cannot release the stale proposal on resume.
- Browser service-worker eviction cannot lose authorization/binding silently.

### Task 1: Loopback transport and canonical worker

Files: `integrations/penrix_chatgpt_web/browser_entry.py`, `tests/test_browser_entry.py`.

- [x] Write tests for exact request/reply, claim uniqueness, pause cancellation, auth/origin admission and read-only binding recovery; show red.
- [x] Implement `BrowserEntry`, `BoundModel.next(history, prompt)`, HTTP API and explicit `share` lifecycle using existing Driver.
- [x] Green tests and real Server/Runner transport fixture; preserve exact canonical Session on restart.

### Task 2: Browser extension

Files: `browser_extension/manifest.json`, `background.js`, `protocol.js`, `content.js`, `tests/browser_protocol.test.cjs`.

- [x] Pin envelope parsing, finality and duplicate claim invariants in Node tests; show red.
- [x] Implement scoped background RPC and Chinese panel with Connect/Start/Pause/Resume and visible result state.
- [x] Bind only current chat; completion must match a new assistant response and request ID. No ChatGPT sends in offline verification; one simulated native composer Send is covered by the local browser fixture.

### Task 3: Package and acceptance

Files: integration README, CI lanes, Windows launch script and acceptance record.

- [x] Run complete Python integration suite, Node tests, syntax/whitespace checks and installed-runtime fixture.
- [x] Package extension and launcher, verify hashes and preserve rollback/login/config.
- [x] Install through normal Chrome unpacked-extension flow; owner Reload and actual page build-marker verification establish activation.
- [x] Verify same-chat read/edit/test, correction and exact recovery under the real-test gate; no claim about cross-chat cognition or untested daily-use paths.

2026-10-10 continuation: 78 Python and nine Node tests passed; local browser fixture and real Windows launcher/full restart passed. Fresh independent review completed and late blocking-page Send race fixed with discriminating RED/GREEN evidence. Chrome control transport is currently unavailable, so unpacked installation and real same-chat acceptance remain open. Minor deferred: navigation can leave the backend waiting up to the reply deadline; pause before switching. See `docs/acceptance/penrix-browser-entry-2026-10-10.md` for exact scope, current package and evidence.

Post-restart continuation: real Chrome control and pairing restored. The actual paragraph composer regression failed before repair, then all ten Node tests passed; owner Reload plus the fresh page's build marker prove activation. Real same-chat read/edit/test/closeout/final passed: one `run_process`, original Job terminal exit 0, one unittest passed. Exact shutdown/restart and subsequent correction acceptance is in progress. The earlier unavailable-control statement above is historical.

Final continuation: exact shutdown/restart/reconnect/correction passed on the same real Session, 14 completed model replies in total, minimum completion cooldown 30.001s, one process/test dispatch. See the final acceptance section for canonical validation warnings, partial DOM evidence, untested human picker/shutdown-dialog flow, cross-chat restrictions and offline Continuity state. This completes the existing-chat entry plan, not the entire product roadmap.
