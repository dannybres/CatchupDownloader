# IPTV Catchup Downloader

A command-line tool to generate and download catchup/timeshift recordings from IPTV services using the Xtream Codes API.

Works on macOS and Ubuntu.

---

## Features

- Interactive arrow-key menus (requires `simple-term-menu`) with paginated numbered fallback
- Remembers last used category and channel permanently across sessions
- Auto-resume: if a download is interrupted, you are offered to resume it on next launch
- Chunked downloads — restarts every 10% to avoid server-side bandwidth throttling
- Automatic post-download TS file repair using ffmpeg
- BST (British Summer Time) auto-detection — adjusts timestamps automatically
- URL copied to clipboard after generation
- Proxy support via `config.json` (for VPN/proxy setups on Ubuntu)

---

## Requirements

| Tool    | macOS                  | Ubuntu                      |
|---------|------------------------|-----------------------------|
| Python  | 3.9+                   | 3.9+                        |
| wget    | `brew install wget`    | `sudo apt install wget`     |
| ffmpeg  | `brew install ffmpeg`  | `sudo apt install ffmpeg`   |
| xclip   | not needed             | `sudo apt install xclip`    |

---

## Setup

### macOS

```bash
brew install wget ffmpeg
pip3 install simple-term-menu
cp config.json.example config.json
# edit config.json with your credentials
python3 catchup.py
```

### Ubuntu

```bash
sudo apt install wget ffmpeg xclip
bash setup_ubuntu.sh        # creates venv and installs simple-term-menu
cp config.json.example config.json
# edit config.json with your credentials
venv/bin/python3 catchup.py
```

If you move the project directory, re-run `bash setup_ubuntu.sh` to recreate the venv.

---

## config.json

Create from the example file. It is gitignored and never committed.

**macOS (no proxy):**
```json
{
  "baseURL": "http://your-provider.com/player_api.php",
  "username": "your_username",
  "password": "your_password"
}
```

**Ubuntu with VPN proxy:**
```json
{
  "baseURL": "http://your-provider.com/player_api.php",
  "username": "your_username",
  "password": "your_password",
  "proxy": "http://localhost:8888"
}
```

If `proxy` is present, it is applied automatically at startup. Leave it out on machines that don't need it.

---

## Usage

Run the script and follow the prompts:

1. Select a category
2. Select a channel (only catchup-enabled channels are shown)
3. Select a date (last 7 days)
4. Enter a start time in 24h format — e.g. `1745` for 17:45
5. Enter a duration in minutes (default: 30)
6. The catchup URL is generated and copied to clipboard
7. Choose whether to download
8. Optionally customise the filename
9. Download runs with progress display, then auto-repairs with ffmpeg

### Resume interrupted downloads

If a download is interrupted (crash, Ctrl+C, network drop), on the next launch:

```
⚠️  An incomplete download was found:
   Channel  : Sky Sports Main Event
   File     : Sky_Sports_Main_Event_Sunday_2026-03-29_1400.ts
   Date/Time: 2026-03-29 1400
   Duration : 90 min

Resume this download? (y/n) [y]:
```

Press Enter to resume from where it left off using wget's `-c` flag.

---

## File structure

```
CatchupDownloader/
  catchup.py             main script
  setup_ubuntu.sh        one-time venv setup for Ubuntu
  config.json.example    example config (commit this)
  config.json            your credentials (gitignored, create manually)
  .catchup_cache.json    last used category/channel (auto-created, gitignored)
  .catchup_resume.json   incomplete download state (auto-created/deleted, gitignored)
venv/                    Python venv for Ubuntu (created by setup_ubuntu.sh, gitignored)
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| No arrow-key menus on Ubuntu | Run `bash setup_ubuntu.sh`, then use `venv/bin/python3 catchup.py` |
| 403 Forbidden errors | Check credentials in `config.json` |
| Download stalls | Ctrl+C and relaunch — resume will be offered |
| BST adjustment message | Expected — time is auto-adjusted for British Summer Time |
| ffmpeg not found | `brew install ffmpeg` / `sudo apt install ffmpeg` |
| No clipboard on Linux | `sudo apt install xclip` |

---

## Design Decisions & Development History

This tool was built iteratively. The decisions below explain why things are the way they are.

### Key iterations

1. **Base implementation** — Python script with JSON config, Xtream Codes API integration for categories/streams, URL generation with BST detection.

2. **Interactive menus** — Added `simple-term-menu` for arrow-key navigation. Fixed an issue where pipe characters (`|`) in category names were being interpreted as column separators by the menu library.

3. **Smart date selection** — Changed from manual date entry to a menu showing the last 7 days in reverse order, with day of week shown prominently. Day of week is more useful than the date alone when thinking about TV schedules.

4. **Time format** — Switched to 4-digit 24h input (e.g. `1745`) without colons. Faster to type, less error-prone.

5. **Download integration** — Added built-in downloader using wget with smart filename generation (`ChannelName_DayOfWeek_Date_Time.ts`).

6. **Automatic TS repair** — Integrated ffmpeg repair after every download to fix corrupted packets, missing timestamps, and discontinuities. Made fully automatic (no prompt) — lossless stream copy, no re-encoding.

7. **System-wide access** — Config loading resolves symlinks so the script works when installed via `~/.local/bin/catchup`.

8. **Anti-throttling chunked downloads** — Many IPTV servers throttle bandwidth partway through a download. The downloader restarts wget every 10% using the `-c` resume flag, which resets the server's throttle counter. Real-time speed stats (current, chunk average, overall average) show this working.

9. **Session memory** — The app remembers your last category, channel, and time. Originally had a 1-hour expiry; removed entirely — there's no reason for these defaults to expire.

10. **User-Agent header** — Added a browser User-Agent to all API requests to avoid 403 errors from servers that block Python's default `urllib` agent.

11. **Dynamic server discovery** — Server URL and port are now fetched from the Xtream Codes `player_api.php` endpoint at startup rather than being hardcoded in config. Falls back to `archiveBase` in config if the API call fails.

12. **Auto-resume** — A `.catchup_resume.json` state file is written before every download and deleted on success. On the next launch, if it exists, the user is offered a resume prompt before the normal selection flow begins.

13. **Proxy via config** — Originally there was a separate `runViaVPN.py` wrapper that set proxy env vars and launched the script using a venv Python. Replaced with a `proxy` key in `config.json` — cleaner, one entry point, machine differences stay in config.

14. **Ubuntu venv** — `simple-term-menu` can't be installed system-wide on Ubuntu without `--break-system-packages` (Debian externally-managed-environment restriction). `pipx` was tried but installs into an isolated env the system Python can't import from. Solution: a local venv at `../venv`, created by `setup_ubuntu.sh`, used explicitly via `venv/bin/python3`.

15. **Fallback pagination** — When `simple-term-menu` is not installed, the numbered list fallback now shows 10 items at a time with option 11 to load more. Previously dumped all items at once which was unusable with large category/channel lists.

### Design principles

- **One file**: Everything lives in `catchup.py`. No modules, no packages.
- **Config over arguments**: Machine differences (proxy, credentials) live in `config.json`, not CLI flags.
- **No prompts for automatic steps**: Repair runs automatically after download. No confirmation needed.
- **JSON config**: Handles special characters in passwords reliably; easier to read and edit than env files.
- **Symlink-aware**: `os.path.realpath(__file__)` ensures config and cache files are always found next to the real script, not the symlink.
