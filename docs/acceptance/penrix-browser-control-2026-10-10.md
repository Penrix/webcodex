# Chrome control prerequisite repair — 2026-10-10

Owner reports extension Reload complete and authorizes continuing WebCodex acceptance. Treat that as owner-supplied deployment evidence, not proof that a page or particular extension package is currently active. Do not ask for a repeat Reload to diagnose the separate Codex control transport.

## Before the owning Codex restart

Official CUA inventory discovers both registered Chrome control surfaces, but both tab inventories return `nodeRepl.fetch request failed`. No page was read, no WebCodex panel admission occurred, and no real ChatGPT test message was sent. Native automation is disabled in this CUA entry. No alternate browser-control client, profile rewrite or privileged-page bypass was used.

The current owning launch process runs `@oai/cua-repl/bin/cua-repl.mjs` under the newly bundled `cua_node/cfb32733c877621e`, Node 24.21.0. Its actual `src/launch.js` does not contain the proxy defaults installed in an older runtime. Windows still points at the existing Hiddify HTTP proxy `http://127.0.0.1:12334`, with live loopback listeners. No proxy/VPN setting was changed.

Controlled unauthenticated HEAD tests with this exact Node binary: direct access to `https://ab.chatgpt.com` fails with `UND_ERR_CONNECT_TIMEOUT`; enabling the existing system proxy returns HTTP 403. The 403 is transport reachability, not authenticated Chrome control or ChatGPT usability. This supports restoring the previously proven proxy-inheritance correction; target-browser recovery remains unverified until the owning tool process restarts and actual supported browser operations succeed.

[Node's documented proxy mechanism](https://nodejs.org/api/cli.html#node_use_env_proxy1) reads HTTP_PROXY, HTTPS_PROXY and NO_PROXY during startup when NODE_USE_ENV_PROXY=1. Installed Node behavior was tested directly rather than inferred solely from current documentation.

## Applied narrow correction

Only the current installed CUA launcher's spawned-child environment changed: enable NODE_USE_ENV_PROXY; default HTTP_PROXY/HTTPS_PROXY to the already configured 12334; default NO_PROXY to loopback. Explicit existing proxy/NO_PROXY values are preserved. Browser/computer surface selection, trusted-service configuration, stdio, certificates, auth, approval policy and native Codex model routing are untouched. No config.toml write or 17841 insertion occurred.

- Original SHA256: `3e52a41f4da41d35be8cc3723fe97251711087a998c1ed7f2cfdf7e20b50fc2b`.
- Patched SHA256: `cab80056a6cd2c711acdabfeacb2317077e54b8258326947d5847ad52669cb05`.
- Exact original backup: `diagnostics/webcodex-20261010/launch-cfb32733c877621e.original.js`, outside the repository.
- Guarded repair and test scripts plus machine result: the same diagnostics directory. Exact byte reversal reproduces the original; syntax check passes.
- An offline VM executes the actual launch function with intercepted process creation: the original fails the proxy-inheritance assertion; the patch passes default routing, explicit-routing preservation, surfaces, trusted services and stdio checks. This does not start a second MCP server or bypass the supported browser API.

**CODE VERIFIED, LIVE UNVERIFIED.** The running launcher has already imported its module; resetting only the JavaScript kernel does not recreate its child-process environment. No supported owning-MCP restart tool is exposed. Complete Codex exit/reopen is the remaining activation step. This work did not kill Codex or interrupt unrelated chats. An app/runtime update can replace the package again; do not carry this hash or version claim forward without verification.

After restart: acquire the same supported Chrome surface, verify tab inventory and actual page read/click, confirm WebCodex candidate installation and Continuity's controller exclusion on the refreshed page, then run the bounded same-chat read/edit/test and exact Session recovery acceptance. Verify the actual `-RealTest` path before any send; wait at least 30 seconds after prior reply completion across the account. No extra sends merely to test the gate, no automatic retry after limits/challenge/ambiguity.

Concurrent Continuity runtime-002 work now exists in its own checkout. Preserve it and read its current package state when verifying co-use; this WebCodex work unit does not claim ownership or live validation of that migration.

## After the owner restart — 10:27 UTC

**LIVE VERIFIED for supported Chrome inventory, page reads, trusted clicks and page refresh.** The supported CUA surface now lists the owner's Chrome tabs without transport errors. The existing authorized test conversation `6ac796a5-76e0-83e8-b61d-3c6aa9005414` was read and its WebCodex Connect button clicked. The panel confirmed the exact disposable Project and real-test mode. Refresh also succeeded. This verifies the narrow proxy inheritance repair against actual authenticated browser operations, not only the unauthenticated HEAD probe. No new Codex restart is needed for this control repair.

This does not establish the complete WebCodex coding loop. The first controller attempt was stopped before Send by an observed ProseMirror paragraph serialization mismatch. The observed old extension cache and required activation step are recorded in `penrix-browser-entry-2026-10-10.md`. No real ChatGPT test message was submitted in this attempt.
