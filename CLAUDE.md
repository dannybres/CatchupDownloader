# CLAUDE.md — CatchupDownloader

Notes for Claude Code when working in this project.

---

## What this project is

A single-file Python CLI (`catchup.py`) for downloading IPTV catchup recordings via the Xtream Codes API. Runs on macOS and Ubuntu.

## Run commands

- **macOS**: `python3 catchup.py`
- **Ubuntu**: `venv/bin/python3 catchup.py`

The venv lives at `venv/` inside the project directory. It is created by `setup_ubuntu.sh`.

## Key files

- `catchup.py` — the entire app, one file, one class (`CatchupGenerator`)
- `config.json` — gitignored, per-machine credentials + optional `proxy` key
- `config.json.example` — committed, shows the config structure without real credentials
- `setup_ubuntu.sh` — creates the venv at `../venv` and installs `simple-term-menu`
- `.catchup_cache.json` — auto-created, stores last category/channel selection (no expiry)
- `.catchup_resume.json` — auto-created when a download starts, deleted on success

## Architecture decisions

- **One script**: Everything is in `catchup.py`. Do not split into modules.
- **No wrapper scripts**: There used to be a `runViaVPN.py` wrapper. It was deleted. Proxy config now lives in `config.json` under the `proxy` key and is applied in `apply_proxy()`.
- **Venv for Ubuntu only**: `simple-term-menu` cannot be installed system-wide on Ubuntu without `--break-system-packages`. The venv at `../venv` is the safe approach. macOS can use a plain `pip3 install`.
- **No expiry on cache**: The category/channel cache (`.catchup_cache.json`) has no time expiry — it just remembers your last pick permanently as a default.
- **Resume state**: `.catchup_resume.json` is written before every download and deleted on success. On startup, if it exists, the user is offered a resume prompt before the normal flow.

## What NOT to do

- Do not add a time expiry back to `.catchup_cache.json`
- Do not re-introduce a wrapper script for the proxy — use `config.json`
- Do not split `catchup.py` into multiple files
- Do not install packages system-wide on Ubuntu with `--break-system-packages`
- Do not use `pipx` for `simple-term-menu` — it installs in an isolated env that the system Python cannot import from
