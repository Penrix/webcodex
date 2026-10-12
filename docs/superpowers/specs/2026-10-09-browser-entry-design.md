# WebCodex same-conversation browser entry

Owner approved implementation on 2026-10-09 after the in-chat design. Complete WebCodex first; Continuity is deferred. Existing uncommitted Stage A fixes and acceptance evidence remain part of this checkout.

## Outcome

An unpacked Chrome extension binds one existing ChatGPT conversation to one authorized local Git project. The owner starts work from a natural-language task, sees progress, pauses, supplies a correction and resumes the same canonical WebCodex Session. Tool results return to that same native conversation as ordinary messages. This is a browser adapter, not official Plus MCP.

## Ownership

Reuse `driver.Driver`, its canonical manifests, fixed selectors, Job admission and closeout. A localhost Python entry owns a single transient browser request/reply rendezvous; it owns no execution queue, Job ledger, recorder or cognition store. WebCodex `share` owns Server/Runner and persistent canonical state. Persist only exact Project/Session/conversation binding pointers, never tool histories or inferred completion.

The extension carries transport messages and renders a small Chinese panel. Credentials stay in the extension background context, never in ChatGPT DOM. Restrict background messages to the bound top-level ChatGPT tab. Bind the loopback service to 127.0.0.1:17842, validate Host and the fixed extension origin, and expose pairing only to that origin. User explicitly clicks Connect before a conversation can drive the fixed project. Preserve login, Codex routing and existing extensions.

## Browser protocol

The owner can enter a task in the panel or use the latest human message. The Driver supplies canonical bootstrap and subsequent results. Send the full contract and only new controller history since the last browser round; the existing native conversation retains discussion. Replies contain a single JSON envelope with the exact transient request ID and existing Driver action. Wait for the matching new assistant response to finish; never interpret unrelated examples, old replies or a streaming prefix as a tool call.

Claim a request before activating Send. No submission is retried after claim, network failure, reload or uncertain browser state. Stop on CAPTCHA, unusual activity or rate limits. Pause prevents later tool dispatch, wakes a waiting model request and keeps already-running canonical Jobs intact. Resume starts a fresh Driver on the exact saved Session after the old worker has stopped; it reads current handoff rather than replaying the old action.

Real acceptance mode uses the existing account-wide RealTestGate around the actual browser request through completed reply validation: >=30 seconds after completion, preserve longer deadlines, no concurrency bypass. No ChatGPT sends are needed for offline checks.

## Delivery and acceptance

Python stdlib, Chrome MV3 and plain JavaScript; no new runtime dependencies or Continuity changes. Provide a Windows start command with an explicit project and reviewed candidate directory, retain canonical state on shutdown, and package the extension for one normal unpacked installation. Verify request identity, authorization, duplicate claim/reply, pause/resume, stale tab and malformed response with offline tests, then exercise the real Server/Runner with a simulated browser transport. Real Chrome installation and the same-chat read/edit/test/correction/recovery flow are separate acceptance gates. Do not claim daily usability until those pass.
