# Agent Guidelines

## Python environment
- ALWAYS use the project venv: `./venv/bin/python` (never system python, never ad-hoc venvs).
- It contains: Home Assistant 2026.8.3, `pytest-homeassistant-custom-component`, `ruff`, `playwright` (+ chromium), `aiohttp`.
- `venv/lib/python3.14/site-packages/pymicro_vad.py` is a deliberate stub (the real package
  does not build on this machine; only needed so Home Assistant core can import all components).

## Commands
- Tests: `./venv/bin/python -m pytest test_*.py -q`
- Lint: `./venv/bin/ruff check custom_components/ scripts/`
- Watchdog (live check of all providers): `./venv/bin/python -m scripts.watchdog`

## Local live Home Assistant instance (development only)
- Config dir: `/var/folders/z1/9p244qqn3l5g2rw5qc3m71xw0000gn/T/opencode/ha-live/config`
- Start: `nohup ./venv/bin/python -m homeassistant -c <config-dir> &`
- Web UI: http://localhost:8123 (user `admin`, password `testpass123`)
- Playwright UI scripts live in `/var/folders/z1/9p244qqn3l5g2rw5qc3m71xw0000gn/T/opencode/ha-live/`
  (onboard.py, login.py, flow scripts); browser state: `state.json` in the same dir.

## Conventions
- Code, comments, commits, PR descriptions: English.
- Conventional Commits, subject <= 50 chars.
- Release flow: bump `version` in both manifests, push, tag `vX.Y.Z` (release pipeline
  creates the GitHub release with the changelog).
- `watchdog` GitHub workflow runs daily and opens an issue (label `watchdog`) if a provider breaks.