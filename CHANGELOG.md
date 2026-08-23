# Changelog — claude-auto-continue

All notable changes will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/)

## [Unreleased]

## [3.14.0] - 2026-08-23
### Added
- **Per-profile overrides via settings.json** - any profile field
  (\utton_labels\, \input_names\, \sidebar_chrome\, ...) can be tweaked
  without touching code: \profile_overrides\ merges over the base profile
  with a whitelist of existing keys, so typos cannot break the engine.
  Headless mode reads the same file.
### Fixed
- Selected profile is now persisted on save - since #27 it was only read
  from settings.json, so switching profiles did not survive restarts.

## [3.13.1] - 2026-08-23
### Added
- **Single-instance guard** - a second copy (autostart + manual launch) no
  longer fights the first one for the mouse: named mutex on Windows, flock on
  macOS/Linux. GUI shows an error box, headless exits with code 3.
- \--version\ flag (headless and GUI builds).
- Release workflow smoke-tests the built exe (\--version\ exit code) before
  attaching it to the release.
### Fixed
- \--log-file\ now rotates (~4000 lines -> keeps last half); multi-day
  headless runs no longer grow the log unbounded.

## [3.13.0] - 2026-08-23
### Added
- **App profiles — pivot to universal Electron auto-continue.** The engine is
  no longer bound to claude.exe: a profile registry (`engine.APP_PROFILES`)
  describes process matching, retry button labels, input field names, sidebar
  navigation dictionaries and an optional window-title hint. Claude Desktop is
  the unchanged reference profile; Cursor / Windsurf / VS Code Copilot Chat
  ship as experimental presets.
- GUI "App: …" button cycles profiles; the selection persists in settings.json.
- CLI `--profile NAME` (validated choices) and `--list-profiles`.
- Profile-aware "not found" messages.
- 5 new tests: profile fallback resolution, registry well-formedness,
  reference Claude behavior, experimental marks, CLI validation.


## [3.12.0] - 2026-08-23
### Added
- **CLI / headless mode** - run without the GUI: `--headless --at 05:00`,
  `--now`, `--once`, `--interval SEC`, `--chats N`, `--log-file PATH`.
  Same engine as the GUI; argument validation is testable without UIA and
  console output survives cp1251 terminals.
- **engine.py module** - pure stdlib logic (limit-time parser with context
  filter, reset occurrence helper, CLI target parsing) extracted from the
  monolith; importable without tkinter/UIA, re-exported by the GUI so all
  existing callers keep working.
- **PyInstaller releases** - pushing a `v*` tag builds a one-file
  `ClaudeAutoContinue.exe` (GitHub Actions) and attaches it to the release;
  users no longer need Python installed.
- README: CLI examples and build notes.
### Fixed
- **Limit tracker ignores chat history** - text collection excludes the
  sidebar by geometry, keeps only the last message nodes and requires
  limit/usage/лимит keywords near the time (`require_context=True`), so an
  old "we discussed resets at 3 PM" no longer produces a phantom reset.
- **GUI failed to launch after the #20 squash merge** - duplicate
  `FlatBtn._measure` definitions shadowed each other and the constructor
  called the dead signature (`TypeError` on every button).
- **Limit auto-scan enable crash and dead 3-strike dedup** - worker was
  started without its generation argument and the duplicate handler was
  invoked without a count; generations are now the single liveness
  mechanism (rapid off->on race included) and three identical scans are
  required before auto-scan disables itself.
### Fixed
- **Single tick chain after theme switch** — finishing the generation mechanism:
  `_tick` now takes a generation argument and stale scheduled callbacks exit
  immediately when `_set_theme` bumps the counter; previously two parallel
  10 Hz redraw chains could run at once.
- **Chats are re-resolved by name before each switch** — rectangles captured
  before the first click went stale after Claude re-sorts Recents, so clicks
  landed on the wrong rows; targets are matched by name against a fresh
  sidebar scan, missing chats are skipped with a log line.
- **Negative chat indices no longer select the last chat** — `-1` passed the
  old `i < len(chats)` check due to Python negative indexing.
- **Honest duplicate detection in the limit tracker** — comparing HH:MM strings
  flagged any two scans inside one limit window; duplicates are now detected
  only while the previous reset time is still in the future
  (`next_reset_occurrence`).
- **Import survives read-only install dirs** — `os.makedirs(templates)` at
  module import crashed under Program Files / /Applications.
- **Process path buffer widened to 1024 chars** — long Python paths were
  truncated in `get_process_exe`.
- **Registry handles closed in `finally`** — autostart get/set leaked the key
  handle when `QueryValueEx`/`SetValueEx` raised.
- **Maximized Claude is no longer restored every cycle** — `ShowWindow(SW_RESTORE)`
  fired unconditionally; now only when the window is actually minimized (`IsIconic`).
- **Buttons resize with their label** — `FlatBtn.config(text=…)` re-measures the
  required size, so RU↔EN and ВКЛ↔ВЫКЛ switches no longer clip the caption.
- **First window scan deferred** — `_scan_now()` from `__init__` could hit
  `root.after()` before `mainloop()` on some machines (`RuntimeError`); it is
  scheduled via `after(400, …)` instead.
- **Autostart uses `pythonw.exe` when available** — no console window flash at logon.
- **MouseWheel binding no longer accumulates** — theme rebuilds stacked duplicate
  `bind_all('<MouseWheel>')` handlers, making scroll faster each time.
- **Template capture grabs the screen before restoring the app window** — otherwise
  the de-iconified main window could overlap the captured region.

## [3.11.0] - 2026-08-23
### Changed
- **Ring timer scrolls with the page again** — the countdown ring is back inside the
  scrollable body instead of being pinned between the header and the cards; in short
  windows the fixed ring was eating half the height and squeezing everything else.
- Top bar slimmed to compact buttons only (theme / autostart / RU/EN). The
  "minimize to tray" and "notifications" checkboxes moved into the page next to the
  watch-mode options — at 480 px width they were colliding with the header buttons.
### Fixed
- Plan time chips now wrap in a 4-per-row grid instead of overflowing past the
  card and window edge on long plans.
- Chat list canvas height matches real row height (~26 px) — the last row was clipped.
- Long status lines (window found, limit-tracker result/status, plan status) wrap
  via `wraplength` instead of clipping at the card edge.

## [3.10.0] - 2026-08-23
### Added
- **Safe Enter** — before pressing Enter the message input is read via UIA ValuePattern;
  if it already contains typed text, Enter is skipped with a warning instead of sending
  whatever was typed by hand. Removes the top known limitation.
- **17 unit tests + CI** — extracted pure `parse_limit_text()` out of the UIA engine;
  pytest suite covers AM/PM edge cases, EN/RU phrasings, duration roll-over past midnight,
  false-positive guard, sidebar filter, i18n/theme table parity and plan target math.
  GitHub Actions runs it on windows-latest + ubuntu-latest (guarded imports mean no heavy
  deps needed). Tests immediately caught a real gap: `try again at HH:MM` wasn't matched.
### Fixed
- settings.json written atomically (`tmp` + `os.replace`) — a crash mid-write could
  corrupt the config and break startup.
- Log widget capped at ~500 lines — multi-day watch mode no longer grows memory unbounded.

## [3.9.0] - 2026-08-23
### Fixed
- **FAILSAFE re-enabled** — `pyautogui.FAILSAFE = False` was removed. A stuck cycle
  (mouse hijacked by automation) can now be aborted instantly by flinging the cursor
  into a screen corner; the cycle exits cleanly with a log message instead of being
  swallowed by a generic `except`.
- **Concurrent cycles serialized** — "Now" button, timer worker, plan worker and
  limit-tracker scans could run `run_cycle` at the same time and fight over the mouse.
  All cycles now go through a single lock (`_do_cycle`); overlapping triggers are
  skipped with a warning, tracker scans are guarded by their own lock.
- **Invalid watch interval no longer kills the worker** — non-numeric input in the
  interval Spinbox raised `ValueError` inside the background thread, which died silently
  and left the UI stuck in STOP state. Interval is now validated and clamped (5–600 s).
- **Options snapshotted on START** — the timer/plan workers used to read Tkinter
  variables from background threads (unsafe) mid-run. All options (chats, actions,
  confidence, watch, retry, notifications) are now captured in the main thread when
  START / plan start is pressed.
- **`pending_iso` cleared on STOP** — stopping the countdown didn't rewrite
  settings.json, so an app crash after STOP resurrected the stopped timer on next launch.
- **Fired one-off plan times are persisted** — removing a triggered one-off time only
  mutated memory; it came back after restart. Removal now happens on the main thread
  with an immediate settings save.
- **Theme switch keeps running state** — switching theme while a timer/plan was active
  rebuilt the UI showing an idle START button; active-state visuals are restored.
- **Badge colors follow the theme** — badge state colors were frozen at class definition
  with the dark palette and stayed wrong in light mode.
- **Template status shows real size** — the template row reported the thumbnail size
  instead of the captured image size.
- **Multi-monitor template capture** — the capture overlay was fullscreen-primary-only
  and screenshots missed secondary monitors; the overlay now spans the virtual desktop
  and `ImageGrab.grab(all_screens=True)` is used on Windows.
- **Limit tracker returns to first chat** — scanning left Claude Desktop switched to the
  last visited chat; it now restores the first chat afterwards and caps scans at 30 chats.
- **macOS scrolling fixed** — scroll delta was always divided by 120 (Windows convention),
  making lists barely move on Mac.
- **Sidebar chat filter false positives** — the `'show '` chrome-prefix filter dropped real
  chats titled e.g. "Show me how to…"; replaced with explicit service items.
- **Settings validation** — corrupted settings.json (unknown lang/theme, malformed plan or
  history entries) crashed the app on startup; values are now sanitized.
- **run.bat portability** — hardcoded personal Python path replaced with py-launcher /
  PATH lookup; requirements.txt got a `sys_platform == "win32"` marker for uiautomation.

### Changed
- Remaining hardcoded Russian labels ("Интервал:", "мин", "История сбросов:", retry and
  notification checkboxes, auto-scan logs) moved into the i18n table and retranslate on
  language switch.
- Plan status countdown now refreshes every second while the plan runs.

## [3.8.0]
### Added
- **macOS support** — the app now runs on macOS in addition to Windows. On Mac, Claude
  Desktop is located via `pgrep`, brought to the foreground via `osascript`, and buttons
  are found by screenshot template matching (UIA is Windows-only). Sidebar chat switching
  is not available on Mac, so the app operates on the currently visible chat. Autostart
  is handled via a `~/Library/LaunchAgents/` plist instead of the Windows registry.
### Fixed
- **Light theme readability** — completely reworked light palette with higher contrast
  ratios: darker mid-tone background (`#dce1e8`), distinct card color, deeper accent blue,
  and dark near-black text (`#0f1923`) that reads cleanly against light surfaces.
- **RoundedCard outline** — removed a duplicate polygon vertex that caused `smooth=True`
  Bézier splines to loop back at the top-left corner, producing a crooked-looking outline.
- **Ring timer always visible** — the countdown ring is now positioned in a fixed frame
  between the header and the scrollable card area, so it is always on screen regardless
  of scroll position.
- **Theme switch resetting time** — switching between dark/light themes no longer resets
  the trigger time, plan time, watch interval, button checkboxes, confidence slider, or
  any other form value. Values are now snapshotted into the settings dict before the
  widget tree is rebuilt.

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
