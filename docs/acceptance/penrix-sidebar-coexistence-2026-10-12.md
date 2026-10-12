# Sidebar coexistence correction — 2026-10-12

Build marker: `20261012-collapsed-dock`. This is a UI-only correction to the
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

Remaining: activate the changed unpacked extension with Chrome Reload, then
repeat coexistence on the actual ChatGPT page, including native input/sidebar
layout. A fixture cannot establish the layout of ChatGPT's fixed descendants.
Do not call the installed correction LIVE VERIFIED before that observation.
