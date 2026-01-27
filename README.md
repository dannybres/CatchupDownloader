# IPTV Catchup Downloader

A powerful command-line tool to generate and download catchup/timeshift content from IPTV services with automatic stream repair.

![Python](https://img.shields.io/badge/python-3.6+-blue.svg)
![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Ubuntu-lightgrey.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## Features

- **Interactive keyboard navigation** with arrow keys (no scrolling needed!)
- **Built-in file downloader** with progress bar
- **Automatic TS file repair** with ffmpeg (fixes corrupted streams automatically)
- Automatically filters streams to show only those with catchup/archive
- Smart filename generation (StreamName_Day_Date_Time.ts)
- **BST (British Summer Time) detection** and automatic adjustment
- Clipboard support on macOS and Linux
- JSON configuration file for easy credential management
- Fallback mode if interactive library not installed
- **Run from anywhere** - install once, use everywhere

## Quick Start

```bash
# Install dependencies
pip3 install simple-term-menu

# Configure your credentials
cp config.json.example config.json
# Edit config.json with your IPTV credentials

# Run
python3 catchup.py
```

Or install system-wide:
```bash
mkdir -p ~/.local/bin
ln -sf "$(pwd)/catchup.py" ~/.local/bin/catchup
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
source ~/.bash_profile

# Now run from anywhere
catchup
```

## Requirements

- Python 3.6 or higher
- Internet connection
- Optional but recommended:
  - `simple-term-menu` - for interactive keyboard navigation
  - `wget` - for better download progress display
  - `ffmpeg` - for automatic stream repair

## Installation

### 1. Install Python Dependencies

```bash
pip3 install simple-term-menu
```

*Note: The script will work without this, but you'll get a better interactive experience with arrow key navigation.*

### 2. Install Optional Tools

**macOS:**
```bash
brew install wget ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt install wget ffmpeg xclip
```

### 3. Configure Credentials

Edit `config.json` with your IPTV credentials:

```json
{
  "username": "your_username",
  "password": "your_password",
  "baseURL": "http://your-api-url.com/player_api.php",
  "archiveBase": "http://your-archive-url.com/timeshift"
}
```

### 4. Make Script Executable

```bash
chmod +x catchup.py
```

### 5. Install System-Wide (Optional)

To run `catchup` from anywhere:

```bash
# Create local bin directory
mkdir -p ~/.local/bin

# Create symlink
ln -sf "/full/path/to/catchup.py" ~/.local/bin/catchup

# Add to PATH (bash)
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bash_profile
source ~/.bash_profile

# Or for zsh
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc
source ~/.zshrc
```

## Usage

### Run Directly

```bash
python3 catchup.py
# or
./catchup.py
```

### Run System-Wide

```bash
catchup
```

### Interactive Workflow

The script guides you through:

1. **Select Category** - Arrow keys to browse IPTV categories
2. **Select Stream** - Choose from available catchup-enabled streams
3. **Select Date** - Pick from last 7 days (shows day of week prominently)
4. **Enter Time** - 24h format, no colon (e.g., `1745` for 5:45 PM)
5. **Enter Duration** - In minutes (default: 30)
6. **Download** - Optional download with smart filename
7. **Auto-Repair** - Automatic ffmpeg repair of downloaded file

### Example Session

```
============================================================
IPTV Catchup URL Generator
============================================================

Loading categories...
✅ Loaded 25 categories
💡 Use arrow keys to navigate, Enter to select, q to quit

Select a Category:
  ➤ UK Entertainment │ HD
    Sports │ Live Events
    Movies │ On Demand
    ...

✅ Selected: UK Entertainment │ HD
Loading streams with catchup...
✅ Loaded 42 streams

Select a Stream:
  ➤ BBC One
    BBC Two
    ITV
    ...

✅ Selected: BBC One

Select Date:
  ➤ Monday - 2026-01-27
    Sunday - 2026-01-26
    Saturday - 2026-01-25
    ...

✅ Selected: Monday, 2026-01-27

Enter time (24h format, e.g., 1745 for 5:45 PM): 2000
✅ Selected time: 20:00

Duration (minutes) [default: 30]: 60

============================================================
Generated Catchup URL:
============================================================
http://beams-tv.online/timeshift/username/password/60/2026-01-27:20-00/12345.ts
============================================================
✅ URL copied to clipboard!

Do you want to download this file? (y/n) [n]: y

Default filename: BBC_One_Monday_2026-01-27_2000.ts
Enter filename (press Enter for default):

Downloading: BBC_One_Monday_2026-01-27_2000.ts

BBC_One_Monday_2026- 100%[===================>] 144.01M  11.0MB/s    in 17s

✅ Download complete: BBC_One_Monday_2026-01-27_2000.ts

Repairing file with ffmpeg...
✅ Repaired: BBC_One_Monday_2026-01-27_2000.ts
```

## Configuration

### config.json Structure

```json
{
  "username": "your_iptv_username",
  "password": "your_iptv_password",
  "baseURL": "http://your-api-url.com/player_api.php",
  "archiveBase": "http://your-archive-url.com/timeshift"
}
```

The script automatically loads this from the same directory as the script itself, even when run via symlink.

## Features in Detail

### Smart Date Selection

- Shows last 7 days in reverse chronological order (today first)
- Displays day of week prominently (more important than date for TV scheduling)
- Format: `Monday - 2026-01-27`

### Time Input

- 24-hour format without colon: `1745` for 5:45 PM
- Accepts 3 or 4 digits (`945` becomes `0945`)
- Automatically strips colons if entered

### Filename Generation

Default format: `StreamName_DayOfWeek_YYYY-MM-DD_HHMM.ts`

Example: `BBC_One_Monday_2026-01-27_2000.ts`

- Automatically sanitizes invalid characters
- Preserves channel name and timing info
- Always adds `.ts` extension

### BST Detection

Automatically detects British Summer Time and adjusts the time by subtracting 1 hour when needed. Displays notification when adjustment occurs.

### Automatic Repair

After download, the script automatically repairs the TS file using:

```bash
ffmpeg -err_detect ignore_err -fflags +genpts -i input.ts -map 0 -c copy output.ts
```

This fixes:
- Corrupted packets
- Missing timestamps
- Discontinuities in the stream
- Other common IPTV stream issues

The repair is lossless (stream copy, no re-encoding) and typically very fast.

## Download & Repair Support

### Downloading

- **wget** (preferred): Clean progress bar, better display
- **urllib** (fallback): Built-in Python, works without wget

### File Repair

- **ffmpeg** required for automatic repair
- If not installed, download still works but repair is skipped
- Install: `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Ubuntu)

### Clipboard

- **macOS**: Automatic (pbcopy)
- **Linux**: Requires `xclip` or `xsel`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Configuration file not found" | Make sure `config.json` exists in the same directory as the script |
| "Failed to load categories" | Check your internet connection and API credentials |
| BST adjustment notification | Normal - script automatically adjusts for British Summer Time |
| No arrow key navigation | Install `simple-term-menu`: `pip3 install simple-term-menu` |
| "ffmpeg not installed" | Install with `brew install ffmpeg` (macOS) or `sudo apt install ffmpeg` (Ubuntu) |
| No clipboard support (Linux) | Install `xclip`: `sudo apt install xclip` |

## Development Story

This tool was developed through an iterative, user-driven design process using Claude Code. Here's how it evolved:

### Initial Request
Started with an HTML-based IPTV catchup URL generator and a request to create a command-line equivalent with the same functionality and configuration management.

### Key Development Iterations

1. **Base Implementation** → Created Python script with JSON config, API integration for categories/streams, URL generation with BST detection

2. **Interactive Menus** → Added `simple-term-menu` for arrow-key navigation, eliminating scrolling through long lists. Fixed issue where pipe characters (`|`) in category names were being interpreted as column separators.

3. **Smart Date Selection** → Changed from manual date entry to menu-based selection showing last 7 days in reverse order, prominently displaying day of week (more important than dates for TV schedules)

4. **Time Format Optimization** → Switched to 4-digit 24h format (e.g., `1745`) without colons for faster input

5. **Download Integration** → Added built-in downloader with smart filename generation (`ChannelName_DayOfWeek_Date_Time.ts`), using wget when available with clean progress display

6. **Automatic Repair** → Integrated ffmpeg-based TS file repair to fix corrupted streams, packet issues, and timestamp problems. Made automatic (no prompt) per user request.

7. **System-Wide Access** → Modified config loading to resolve symlinks, enabling system-wide installation via `~/.local/bin/catchup`

8. **Output Cleanup** → Reduced verbose wget output using `-q --show-progress` flags for cleaner, more professional display

### Design Decisions

- **JSON over plain text config**: Better handling of special characters in passwords, easier programmatic parsing, less prone to errors
- **Interactive mode as default**: More user-friendly than command-line arguments for this use case
- **Automatic repair**: User prefers seamless workflow without prompts
- **Day of week prominent**: More natural for TV scheduling than dates alone
- **No colons in time**: Faster to type, fewer keystrokes
- **Symlink-aware config**: Enables system-wide installation while keeping config in one place

### Technologies Used

- **Python 3.6+**: Core language
- **simple-term-menu**: Interactive arrow-key menus
- **urllib/wget**: File downloading
- **ffmpeg**: Stream repair
- **JSON**: Configuration storage

## License

MIT License - feel free to use and modify as needed.

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

## Author

Created with Claude Code through iterative development and user feedback.
