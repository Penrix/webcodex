# Sidebar coexistence correction — 2026-10-12

Build marker: `20261012-collapsed-dock-r2`. This is a UI-only correction to the
browser entry on `penrix/chatgpt-web-driver`; Server/Runner, authority, history
storage, delivery and cooldown paths are unchanged.

## Failure observed in actual Chrome

The installed `20261011-user-workspace` build occupied the same bottom-right
rectangle as Prompt Shelf. On the owner's real ChatGPT page, viewport roughly
1862 × 850, WebCodex's collapsed button was at x1753..1846, y789..826,
z-index 2147483645. Prompt Shelf's launcher was at x1768..1838, y793..826,
z-index 40. Attempting to click the latter opened WebCodex instead.
The source also inserted the entire sidebar open on every document load.
The previous synthetic sidebar checks did not include the owner's other
extension and were insufficient to establish coexistence.

## Correction

- Collapse before insertion, avoiding an expanded-panel flash on load.
- A narrow vertical launcher on the left replaces the overlapping right button.
- Explicit opening docks the task panel on the left. Above 1100 CSS pixels,
  a scoped stylesheet reserves space by reducing the observed direct-body
  ChatGPT `#root` width. Collapse restores its normal layout automatically.
- At 1100 pixels and below, opening uses a drawer; it does not shrink ChatGPT
  into an unusably narrow column. Prompt Shelf retains its existing z-index 40
  above the drawer's 30, and its right launcher remains accessible.
- Resize handle and keyboard direction follow the left dock. Existing large
  task input, history, and unsent draft retention on collapse remain.
- No other extension's DOM, styles, settings or storage are modified.

## Evidence

**LIVE VERIFIED — failure only:** original installed build, owner's real Chrome,
2026-10-12: geometric overlap and misdirected click reproduced. Prompt Shelf's
actual shadow stylesheet and ChatGPT root structure were inspected read-only.

**CODE VERIFIED, LIVE UNVERIFIED — correction:** 23 Node tests pass, including a
new initially failing default-collapsed/draft/no-send regression. Independent
diff review found no actionable regression. Exact production content script was
rendered in Chrome on a local fixture with Prompt Shelf's observed placement,
size and layer. At 2048 × 991, both panels opened, WebCodex occupied x8..528 and
ChatGPT root began at x544. Keyboard resize moved the root consistently; collapse
restored x0; draft survived. At 390 × 640, drawer stayed in bounds, root stayed
unshrunk, and the prompt launcher remained the hit-test target and clickable.
Relevant fixture console warnings/errors: none. Temporary viewport restored.
Zero ChatGPT messages sent.

## Real-page follow-up and viewport-width child correction

The owner reloaded the first dock build. Actual ChatGPT then revealed an inline
viewport-width direct child of `#root`, identified by its existing inline
`--app-shell-navigation-rail-width` property. Shrinking only `#root` left that
child overflowing horizontally. Native input ancestors were inspected and
belong to the app layout, rather than being independently viewport-fixed.

The r2 build constrains that observed child with `max-width:100%`, only while
the desktop dock is open. The regression fixture now includes its actual
viewport-width characteristic. This rule does not rewrite inline styles and
does not affect closed or narrow layouts. Node tests remain 23/23.

## Final actual Chrome acceptance — LIVE VERIFIED for UI scope

After the owner's second Reload, source commit
`11d82034f3007ae1ba0a3c00bb5bbc2a556e88a8`, marker
`20261012-collapsed-dock-r2`, was observed on a freshly reloaded duplicate of
the owner's actual ChatGPT conversation. The original tab and its draft were
not reloaded or edited. Observation date: 2026-10-12, Windows/Chrome.

- Fresh load: collapsed, ChatGPT root x0, no horizontal document overflow.
- At actual CSS viewport 1862 × 850: explicit opening produced WebCodex
  x8..528, ChatGPT root and its app-shell child x544..1862. Native composer
  remained inside the available chat area; no horizontal overflow.
- The actual Prompt Shelf launcher opened its actual panel at x1483..1838,
  separate from WebCodex. Both plugins remained available.
- Keyboard resizing 520 → 540 pixels moved the ChatGPT root x544 → x564,
  without overflow. Returning to 520 restored x544.
- Collapse restored root x0. Reopening retained the unsent test draft.
- A temporary 390 × 640 viewport request resulted in an actual CSS viewport
  355 × 582 on this browser. The drawer stayed within bounds; the root stayed
  at x0; no horizontal overflow. Prompt Shelf's launcher remained the native
  hit-test target and opened its panel while WebCodex was open.
- At actual CSS viewport 1309 × 818, both actual panels were captured together
  in `diagnostics/webcodex-20261012/dock-live-coexistence.png` (local workspace,
  outside the repository). They did not overlap each other.
- Temporary viewport override was reset. Test draft cleared, WebCodex collapsed,
  root x0 restored. Relevant captured warning/error log entries: none.

Only layout/open/close/resize/draft controls were exercised. Zero ChatGPT
messages were sent; no Connect, Start, Pause, Transfer or Shutdown was invoked.
Server/Runner were not restarted. Existing runtime ZIP snapshots remain intact;
the reviewed UI source was overlaid with backups into the five existing runtime
candidates. The PR remains Draft/unmerged.

This acceptance establishes the reported UI adaptation/coexistence fix. It does
not accept task execution on project-specific ChatGPT routes, real history
persistence, a new ChatGPT-to-home task, cross-chat execution, daily long-running
use, or Continuity/OpenViking integration. The inspected project conversation
displayed the existing offline-history error; no claim of history success is
made from this UI-only check.
