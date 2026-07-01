# Changelog — claude-auto-continue

All notable changes will be documented here.

Format: [Keep a Changelog](https://keepachangelog.com/)

## [Unreleased]

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
