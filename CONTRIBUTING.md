# Contributing Guide

Thank you for interest in contributing! Read [CODE_OF_CONDUCT](CODE_OF_CONDUCT.md) first.

## Setup

```bash
git clone https://github.com/Mukller/claude-auto-continue
cd claude-auto-continue
pip install -r requirements.txt
```

## Development

1. Create feature branch: `git checkout -b feature/name`
2. Make changes
3. Test: `python claude_continue_gui.py`
4. Commit: `git commit -m "feat: description"`
5. Push: `git push origin feature/name`
6. Create Pull Request

## Commit Format

```
<type>: <description>
```

Types: feat, fix, docs, refactor, test, chore

## Code Style

- Follow PEP 8
- No hardcoded secrets
- Add docstrings for non-obvious functions (why, not what)

## Testing

- Test manually against a real Claude Desktop window
- Ensure no breaking changes to window/sidebar/button detection
- Update README.md and README_EN.md if behavior changes

## Questions?

Open an Issue or Discussion.

Thank you! 🚀
