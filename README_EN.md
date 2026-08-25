<div align="center">

**English** • [Русский](README.md)

</div>

# Electron Auto-Continue

<p align="center">
  <a href="https://github.com/Mukller">
    <img src="https://img.shields.io/badge/Anton%20Petnitsky-Developer-0d1117?style=for-the-badge&logo=github&logoColor=white&labelColor=0d1117&color=58a6ff" alt="Anton Petnitsky" />
  </a>
</p>

> [!NOTE]
> Previously **claude-auto-continue**, targeting Claude Desktop only.
> The engine is now app-agnostic: Claude works out of the box, while
> Cursor / Windsurf / Copilot Chat ship as experimental profiles.

Universal auto-resume for Electron AI chats: automatically finds the
**Try again / Retry / Resume** button when the server rate-limits you and
presses **Enter** to continue the stalled session. Fires on a schedule and
can switch between sidebar chats within one window.

Buttons are located via **UI Automation text search** (Windows) or
**screenshot templates** (macOS). Electron apps often lack proper ARIA roles,
so matching runs on visible text of any element type.

[![Main window](screenshots/app-idle.png)](screenshots/app-idle.png)
[![Countdown](screenshots/app-running.png)](screenshots/app-running.png)

---

## Features

- **App profiles** — Claude Desktop out of the box; Cursor / Windsurf /
  Copilot Chat as experimental presets. A profile = process exe + retry
  button labels + input field names + sidebar navigation dictionaries
- **Schedule** — fire at an exact time (e.g. nightly limit reset)
- **Plan of triggers (cycles)** — multiple times, daily repeat or one-shot entries
- **Two actions per chat:** `Try again` — click the real button; `Continue` — press Enter after switching (draft-safe: if the input already has typed text, Enter is skipped)
- **Watch mode** — re-check every N seconds
- **Limit tracker** — reads the reset time from Claude's message and adds it to the plan
- **Screenshot fallback** — capture a button template with the mouse
- **CLI/headless** — night runs without a window, log to file
- Dark/light theme, system tray, notifications, autostart, stats and trigger history
- **macOS**: sidebar chat switching via Accessibility API (grant the permission when prompted); without pyobjc - current-view mode

## Install

```bash
pip install -r requirements.txt
```

**Windows:** `pyautogui`, `pillow`, `uiautomation` are required.
**macOS:** `pyautogui`, `pillow`; `uiautomation` is Windows-only.
`opencv-python-headless` — only for the template fallback.

## Run GUI

```bash
python claude_continue_gui.py
```

Or via `run.bat` (Windows). The **"App: …"** button in the window card cycles
profiles; after switching press **"↻ Find"** to rescan.

### CLI / headless

```bash
python claude_continue_gui.py --headless --at 05:00                  # fire at 05:00
python claude_continue_gui.py --headless --now --profile cursor      # Cursor cycle now
python claude_continue_gui.py --list-profiles                        # list profiles
```

Flags: `--once`, `--interval SEC`, `--chats N`, `--no-try-again`,
`--no-continue`, `--confidence`, `--log-file PATH`. Full list: `--help`.

### Build exe

Pushing a `v*` tag builds a one-file `ClaudeAutoContinue.exe` via PyInstaller
(`.github/workflows/release.yml`) and attaches it to the release.

## Profiles

| Profile | App | Status | Process |
|---|---|---|---|
| `claude` | Claude Desktop | reference | `claude.exe` |
| `cursor` | Cursor | experimental | `cursor.exe` |
| `windsurf` | Windsurf | experimental | `windsurf.exe` |
| `copilot` | VS Code Copilot Chat | experimental | `code.exe` + window title |

Experimental profiles are best-effort presets: each app's UIA tree was not
verified element-by-element, and button labels depend on app version and UI
language. If a profile misses — tweak `APP_PROFILES` in `engine.py` and send a PR.

### Profile fine-tuning

Any profile field can be overridden in `settings.json` without touching code:

```json
{
  "profile": "cursor",
  "profile_overrides": {
    "cursor": { "button_labels": ["Try again", "Erneut"] }
  }
}
```

Only keys that already exist in the profile are applied; typos are ignored.

## Known limitations

- If the app window stays covered because `bring_to_foreground` failed, a click may land elsewhere — the app logs a warning
- The screenshot fallback is sensitive to scale/theme — recapture templates after changing theme or DPI
- Experimental profiles: element names change between app versions

## Emergency stop

Flinging the mouse into a **screen corner** (FAILSAFE) instantly aborts a running cycle — clicks stop and an emergency-stop entry appears in the log.

## Documentation

- [CHANGELOG.md](CHANGELOG.md) — release history
- [CONTRIBUTING.md](CONTRIBUTING.md) — contributing guide
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) — code of conduct
- [RELEASE_INFO.md](RELEASE_INFO.md) — release installation
- [LICENSE.md](LICENSE.md) — MIT license
