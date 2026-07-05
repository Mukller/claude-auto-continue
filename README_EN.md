<div align="center">

**English** • [Русский](README.md)

</div>

# ⚡ Claude Code Auto-Continue

Automatically finds and clicks the **Try again** button in Claude Desktop on a schedule — when the server temporarily rate-limits requests. It can switch between multiple chats in a single window's sidebar and press **Enter** to resume a session that's simply waiting for input after hitting a usage limit.

The button is located via **UI Automation text search**, with no manual template capture needed. Electron apps often don't assign the correct ARIA role (`ControlType=Button`) to their elements, so the search matches visible text (`Name`) on any control type — exact match takes priority, with a minimum-size filter so it doesn't latch onto a random tiny icon.

<div align="center">
<img src="screenshots/app-idle.png" width="46%" alt="Main screen — schedule, detected Claude Desktop window and chat list" />
<img src="screenshots/app-running.png" width="46%" alt="Countdown running before the scheduled trigger" />
</div>

---

## Features

- **Schedule** — fire at an exact time (e.g. when limits reset overnight)
- **Scheduled plan (cycles)** — add multiple trigger times (05:00, 08:00, 17:00…), each fires the full cycle independently. Optional daily repeat, or one-shot entries that remove themselves after firing.
- **Auto button search** — no manual template capture; finds "Try again" by text via UI Automation
- **Switch between chats in the sidebar** — visits the first N chats in the list and processes each one (sorted top-to-bottom, same order as the UI)
- **Scrollable and collapsible chat list** — all detected chats are shown in a scrollable area; click the "Chat list" header to collapse or expand the block
- **Two independent per-chat actions:**
  - `Try again` — finds and clicks the real button (server temporarily rate-limiting requests)
  - `Continue` — presses **Enter** after switching into the chat, regardless of whether any button was found (after a limit, Claude Code usually just waits for input with no button at all)
- **Watch mode** — repeats the check every N seconds
- **Fallback option** — if auto-search doesn't find the button (rare edge case / different app version), you can capture a button template from a screenshot once
- Real mouse control (move + click), not simulated via SendKeys
- Ring countdown timer, dark GitHub theme

---

## Installation

```bash
pip install -r requirements.txt
```

`pyautogui`, `pillow`, `uiautomation` are required. `opencv-python-headless` is only needed for the fallback (tolerant template matching).

## Run

```bash
python claude_continue_gui.py
```

Or via `run.bat` (shows a console with errors if something goes wrong).

The desktop shortcut uses `pythonw.exe` — opens without a console window.

---

## How to use

1. Open Claude Desktop, click **"🔍 Найти"** in the app — it shows the detected window and the list of chats in the sidebar.
2. Choose how many of the first chats to check ("Switch to the first N chats").
3. Check the actions you want — `Try again` and/or `Continue` (both at once is fine).
4. Click **"🔍 Проверить сейчас"** to test finding the Try again button without switching chats or pressing Enter.
5. Set the time and click **START**.
6. At the scheduled moment, the app brings the Claude window to the foreground, visits each selected chat in turn, and performs the checked actions in each.

---

## How it works technically

- `find_claude_windows` — finds the `Claude.exe` process window (the official app), distinguishing it from the `claude-code` CLI.
- `find_sidebar_chats` — locates the navigation sidebar by geometry, not by name (the tree can contain several `"Sidebar"`-named nodes, e.g. nested file panels inside code artifacts), then collects chat buttons, filtering out UI chrome (Pinned/Recents/More options/Relaunch to update, etc.).
- `find_button_uia` — walks the tree in reverse child order (the last elements are usually at the bottom of the chat, where the button appears), prioritizing exact text match, with substring match only as a fallback, filtered by minimum size.
- `bring_to_foreground` — brings the Claude window to the front via `AttachThreadInput` before clicking (a plain `SetForegroundWindow` call from a background process is often silently ignored by Windows — the window can stay behind another one, e.g. a video call window, and the click lands in the wrong place).
- `find_message_input` — clicks the message input box (the `"Prompt"` container, also a custom editor with no standard Edit role) before sending Enter. Without this, focus stays on the sidebar chat button and Enter goes nowhere.

---

## Known limitations

- If the Claude window is covered by a modal viewer (PDF / fullscreen artifact) or another window on top, and `bring_to_foreground` fails, a click can land in the wrong place. The app logs a warning in that case.
- The fallback template search is sensitive to UI scale/theme — if you use it, recapture the template after a theme or DPI scaling change.
- `Continue` presses Enter "blindly" — if the chat's input box already has manually typed text in it, that will be sent.

## Requirements

- Windows 10/11
- Python 3.9+

---

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — version history
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — code of conduct
- [RELEASE_INFO.md](RELEASE_INFO.md) — release installation
- [LICENSE.md](LICENSE.md) — MIT license
