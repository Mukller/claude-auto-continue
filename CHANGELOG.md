# Changelog — claude-auto-continue

All notable changes will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/)

## [Unreleased]

## [3.7.0]
### Changed
- **Rounded cards** — all content cards (trigger, plan, Claude Desktop, templates, history)
  now use a Canvas-based `RoundedCard` widget with smooth 12 px corner curves and a
  1 px border accent on hover/active state, replacing square `tk.Frame` borders.
- **Collapsible log** — the log panel is collapsed by default when empty; clicking the
  `▸ Log` header expands it. A small blue count badge (`● N`) appears on the header
  when new messages arrive while collapsed. Clearing the log auto-collapses the panel.

## [3.6.0]
### Added
- **System tray** (`pystray`, optional) — closing the window minimizes to tray instead of
  quitting. A toggle checkbox in the top bar switches the behavior. Double-click the tray
  icon or use "Show" from the context menu to restore; "Exit" quits cleanly.
- **Windows toast notifications** (`plyer`, optional) — a desktop notification fires after
  every successful trigger cycle. A toggle checkbox is shown when `plyer` is installed.
  Both packages degrade gracefully when not installed.

## [3.5.0]
### Added
- **Settings persistence** — time, intervals, checkboxes, plan times, and trigger history are
  saved to `settings.json` in the app directory and restored on next launch.
- **Per-chat checkboxes** — replaced the "first N chats" spinner with individual checkboxes
  for each detected chat; clicking a row label also toggles the checkbox. First 3 chats
  are auto-selected on initial scan.
- **Windows autostart toggle** — button in the top bar writes/removes the app entry in
  `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
- **Session statistics** — cycle counter with success percentage shown below the badge row;
  updates after every run cycle.
- **Trigger history** — last 10 trigger events (timestamp + OK/fail) displayed in a card
  at the bottom; persisted across restarts.
- **Theme toggle** — top-bar button switches between the existing dark (GitHub dark) palette
  and a new light palette; preference is saved and restored.
### Changed
- Language buttons now reflect the active language with the accent color, matching the
  pre-existing visual convention.

## [3.4.0]
### Changed
- **Scrollable main body** — all cards now live inside a Canvas+Scrollbar scroll area;
  the log panel is pinned to the window bottom and never scrolls away.
- **Plan chips (horizontal)** — scheduled times are displayed as compact inline chips
  (`05:00 ×`, `08:00 ×` …) instead of vertical rows; multiple times fit side by side.
- **Dynamic chat list height** — the chat canvas automatically sizes to show up to 5 rows
  without wasted blank space; taller lists show a scrollbar.
- **Smart scroll dispatch** — a single `bind_all` handler routes the mouse wheel to the
  correct scroll target: chat canvas when hovering the chat list, native scroll for the
  log text widget, main canvas everywhere else.
- **Active card border highlight** — the trigger card glows with the accent colour while
  START is running; the plan card glows while the plan is active.
- **Chat list header hover** — the "▾ Список чатов" header row gets a subtle C2 background
  on mouse-over to indicate it is clickable.
- **Section titles** — label font bumped from size 8 to 9 for better readability.
- **Header accent line** — the separator below the app title bar is now 2 px in the accent
  colour instead of a hairline grey rule.

## [3.3.0]
### Added
- **Scrollable chat list** — the sidebar chat list is now a Canvas + Scrollbar widget;
  all detected chats are shown (no more "… N more" truncation), and the list scrolls
  with the mouse wheel when hovered.
- **Collapsible chat list** — clicking the "Список чатов / Chat list" header collapses
  or expands the chat list in-place (▾ / ▸ arrow). Useful when the list is long and
  you want a more compact window.
- **Scheduled plan (cycles)** — a new "План запусков / Scheduled plan" card lets you
  add multiple trigger times (e.g. 05:00, 08:00, 17:00). Each time runs the full
  cycle independently. Optional "Repeat daily" checkbox: when checked the plan loops
  forever; when unchecked each entry fires once and is removed. The plan button
  (▶ Start plan / ⏹ Stop plan) is mutually exclusive with the single START button —
  you cannot run both simultaneously. The status label shows the next upcoming trigger
  and a live countdown.

## [3.2.0]
### Added
- Time fields (hour/minute) are now editable directly — click and type
  digits instead of only using the +/- steppers. Enter or clicking away
  commits and clamps the value to its valid range.
- Language switcher (RU/EN) at the top of the window. Russian stays the
  default and unchanged; every menu label, button, checkbox, badge, and
  app-level log message gets an English translation. The internal engine
  diagnostic trace (window/chat detection, click attempts) stays
  Russian-only by design — the toggle covers the UI chrome, not the raw
  automation log.
### Changed
- All buttons now have rounded corners (Canvas-based rounded rectangles)
  with a smooth color fade on hover and a brief darkened flash on press,
  instead of the previous flat rectangular labels with an instant color
  swap. Same visual layout, same click behavior — just softer and more
  responsive-feeling.

## [3.1.1]
### Fixed
- `Continue` (Enter) wasn't actually sending the message — after switching
  chats via the sidebar, keyboard focus stayed on the sidebar button, so
  Enter went nowhere. Now the app finds the message input box (`Prompt`)
  and clicks into it first to move focus there before pressing Enter.

## [3.1.0]
### Fixed
- `Continue` checkbox no longer searches for a "Continue" button that usually
  doesn't exist. It now presses **Enter** after switching into each chat,
  independently of whether any button was found — matching how you'd
  actually resume a stalled Claude Code session by hand.
### Removed
- Redundant "Enter after click" checkbox (folded into `Continue`).
- Unused Continue button template capture row (fallback now covers Try again only).

## [3.0.0]
### Added
- Auto button search via UI Automation text matching — no manual template
  capture needed. Matches by visible text (`Name`) on any control type,
  since Electron/React apps often omit proper ARIA button roles.
- Exact-match-first, substring-fallback matching with a minimum-size filter
  to avoid false positives on small unrelated icons.
- Chat switching within a single Claude Desktop window: detects the nav
  sidebar by geometry (not by name — multiple `"Sidebar"` nodes can exist
  for nested artifact panels), filters out UI chrome (Pinned/Recents/More
  options/Relaunch to update).
- Reliable Claude Desktop window detection by process image name, excluding
  the `claude-code` CLI (which also ends in `claude.exe`).
- `bring_to_foreground()` using `AttachThreadInput` — plain
  `SetForegroundWindow` from a background process is often silently ignored
  by Windows, which could leave clicks landing on an overlapping window.
### Changed
- Screenshot template matching (v2) kept as an opt-in fallback only.
### Security
- `templates/` added to `.gitignore` — captured button templates can contain
  personal on-screen content and must never be committed.

## [2.0.0]
### Changed
- Replaced UI Automation button search with screenshot template matching
  (`pyautogui` + `opencv-python-headless`) — the v1 UIA search wasn't
  finding buttons reliably in practice.
### Added
- In-app region capture tool to grab button templates (Try again / Continue).
- Real mouse movement + click instead of simulated clicks via UI Automation
  Invoke/SendKeys.
- Auto-press Enter after a click to send the continued message.
### Fixed
- Desktop shortcut opening an extra console window — now uses `pythonw.exe`.

## [1.0.0] - Initial release
### Added
- Schedule-based auto-click of Try again / Continue buttons in Claude Code.
- Multi-window support — click across the first N detected windows.
- UI Automation BFS tree search, PowerShell SendKeys fallback.
- Watch mode (repeat every N seconds), ring countdown timer, dark GitHub theme.
