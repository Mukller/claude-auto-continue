<div align="center">

**English** • [Русский](README.md)

</div>

# ⚡ Claude Code Auto-Continue

Automatically finds and clicks the **Try again** button in Claude Desktop on a schedule — when the server temporarily rate-limits requests. It can switch between multiple chats in a single window's sidebar and press **Enter** to resume a session that's simply waiting for input after hitting a usage limit.

The button is located via **UI Automation text search** (Windows) or **screenshot template matching** (macOS). Electron apps often don't assign the correct ARIA role to their elements, so the search matches visible text on any control type.

<div align="center">
<img src="screenshots/app-idle.png" width="46%" alt="Main screen — schedule, detected Claude Desktop window and chat list" />
<img src="screenshots/app-running.png" width="46%" alt="Countdown running before the scheduled trigger" />
</div>

---

## Features

- **Schedule** — fire at an exact time (e.g. when limits reset overnight)
- **Scheduled plan (cycles)** — add multiple trigger times (05:00, 08:00, 17:00…), each fires the full cycle independently. Optional daily repeat, or one-shot entries that remove themselves after firing.
- **Auto button search** — no manual template capture; finds "Try again" by text via UI Automation (Windows) or by screenshot (macOS)
- **Switch between chats in the sidebar** — visits selected chats and processes each one (Windows; on macOS — current view only)
- **Two independent per-chat actions:**
  - `Try again` — finds and clicks the real button (server temporarily rate-limiting requests)
  - `Continue` — presses **Enter** after switching into the chat, regardless of whether any button was found
- **Watch mode** — repeats the check every N seconds
- **Fallback option** — if auto-search doesn't find the button, capture a button template from a screenshot once
- **Dark and light theme**, one-click toggle
- **System tray** and **desktop notifications** (optional dependencies)
- **Autostart** on login (Windows Registry / macOS LaunchAgent)
- Ring countdown timer

---

## Installation

```bash
pip install -r requirements.txt
```

**Windows:** `pyautogui`, `pillow`, `uiautomation` are required.  
**macOS:** `pyautogui`, `pillow` are required; `uiautomation` is Windows-only and not needed.  
`opencv-python-headless` is only needed for the fallback (tolerant template matching).

## Run

```bash
python claude_continue_gui.py
```

---

## How to use

1. Open Claude Desktop, click **"↻ Find"** in the app — it shows the detected window and the list of chats in the sidebar.
2. Check the chats you want to process.
3. Check the actions you want — `Try again` and/or `Continue` (both at once is fine).
4. Click **"🔍 Check now"** to test finding the Try again button without switching chats or pressing Enter.
5. Set the time and click **START**.

> **macOS:** Sidebar chat switching is not available (no UI Automation). The app activates Claude via `osascript` and clicks the button in the currently visible chat.

---

## Platform support

| Feature | Windows | macOS |
|---|---|---|
| Find Claude window | ✅ UI Automation | ✅ `pgrep` |
| Bring to foreground | ✅ AttachThreadInput | ✅ `osascript` |
| Sidebar chat switching | ✅ | ❌ |
| Find Try again button | ✅ UI Automation + template | ✅ template |
| Autostart on login | ✅ Registry | ✅ LaunchAgent |

---

## Known limitations

- If the Claude window is covered by another window and `bring_to_foreground` fails, a click can land in the wrong place. The app logs a warning in that case.
- The fallback template search is sensitive to UI scale/theme — recapture the template after a theme or DPI change.
- `Continue` presses Enter "blindly" — if the chat's input box already has manually typed text, that will be sent.

## Requirements

- Windows 10/11 or macOS 12+
- Python 3.9+

---

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — version history
- [CONTRIBUTING.md](CONTRIBUTING.md) — how to contribute
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — code of conduct
- [RELEASE_INFO.md](RELEASE_INFO.md) — release installation
- [LICENSE.md](LICENSE.md) — MIT license
