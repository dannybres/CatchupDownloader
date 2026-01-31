#!/usr/bin/env python3
"""
IPTV Catchup URL Generator
Command-line version of the HTML-based generator
"""

import json
import sys
import os
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
import urllib.request
import urllib.parse
import subprocess
import shutil
import re

try:
    from simple_term_menu import TerminalMenu
    INTERACTIVE_MODE = True
except ImportError:
    INTERACTIVE_MODE = False
    print("💡 For better interactive menus, install: pip3 install simple-term-menu")
    print()


class CatchupGenerator:
    CACHE_EXPIRY_HOURS = 1

    def __init__(self, config_file="config.json"):
        # If relative path, look in the script's directory (resolve symlinks)
        if not os.path.isabs(config_file):
            # Resolve symlinks to get the actual script location
            script_path = os.path.realpath(__file__)
            script_dir = os.path.dirname(script_path)
            self.config_file = os.path.join(script_dir, config_file)
            self.cache_file = os.path.join(script_dir, ".catchup_cache.json")
        else:
            self.config_file = config_file
            self.cache_file = os.path.join(os.path.dirname(config_file), ".catchup_cache.json")
        self.config = self.load_config()
        self.cache = self.load_cache()

    def load_cache(self):
        """Load cached selections if they exist and are recent"""
        if not os.path.exists(self.cache_file):
            return {}
        try:
            with open(self.cache_file, 'r') as f:
                cache = json.load(f)
            # Check if cache is expired
            cached_time = datetime.fromisoformat(cache.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(hours=self.CACHE_EXPIRY_HOURS):
                return {}
            return cache
        except (json.JSONDecodeError, ValueError):
            return {}

    def save_cache(self, category_id, category_name, stream_id, stream_name, date_str, time_str):
        """Save current selections to cache"""
        cache = {
            'timestamp': datetime.now().isoformat(),
            'category_id': category_id,
            'category_name': category_name,
            'stream_id': stream_id,
            'stream_name': stream_name,
            'date': date_str,
            'time': time_str
        }
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(cache, f)
        except Exception:
            pass  # Silently fail on cache write errors

    def load_config(self):
        """Load configuration from JSON file"""
        if not os.path.exists(self.config_file):
            print(f"⛔ Configuration file '{self.config_file}' not found!")
            print("Please create a config.json file with your credentials.")
            sys.exit(1)

        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)

            # Validate required fields
            required = ['username', 'password', 'baseURL', 'archiveBase']
            missing = [field for field in required if field not in config]
            if missing:
                print(f"⛔ Missing required fields in config: {', '.join(missing)}")
                sys.exit(1)

            return config
        except json.JSONDecodeError as e:
            print(f"⛔ Invalid JSON in config file: {e}")
            sys.exit(1)

    def fetch_json(self, url):
        """Fetch JSON data from URL"""
        try:
            req = urllib.request.Request(url)
            req.add_header('User-Agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            with urllib.request.urlopen(req, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"⛔ Error fetching data: {e}")
            print(f"   URL: {url}")
            return None

    def get_categories(self):
        """Fetch available categories"""
        url = f"{self.config['baseURL']}?username={self.config['username']}&password={self.config['password']}&action=get_live_categories"
        data = self.fetch_json(url)

        if not data:
            print("⛔ Failed to load categories")
            sys.exit(1)

        return data

    def get_streams(self, category_id):
        """Fetch streams for a category (only those with catchup)"""
        url = f"{self.config['baseURL']}?username={self.config['username']}&password={self.config['password']}&action=get_live_streams&category_id={category_id}"
        data = self.fetch_json(url)

        if not data:
            print("⛔ Failed to load streams")
            return []

        # Filter only streams with catchup/archive enabled
        return [s for s in data if s.get('tv_archive') == 1]

    def is_bst(self, dt):
        """Check if date is in British Summer Time"""
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo('Europe/London')
            localized = dt.replace(tzinfo=tz)
            return localized.dst().total_seconds() != 0
        except ImportError:
            # Fallback for Python < 3.9 without zoneinfo
            # Simple heuristic: BST is roughly last Sunday of March to last Sunday of October
            month = dt.month
            return 3 < month < 10 or (month == 3 and dt.day > 24) or (month == 10 and dt.day < 25)

    def format_start_time(self, dt):
        """Format datetime for the catchup URL"""
        return dt.strftime("%Y-%m-%d:%H-%M")

    def sanitize_filename(self, filename):
        """Sanitize filename to remove invalid characters"""
        # Remove or replace invalid characters
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        # Remove any control characters
        filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
        # Limit length
        if len(filename) > 200:
            filename = filename[:200]
        return filename.strip()

    def repair_ts_file(self, input_file):
        """Repair TS file using ffmpeg to fix corrupted or problematic streams"""
        if not shutil.which('ffmpeg'):
            print("⚠️  ffmpeg not installed - skipping repair")
            print("💡 Install with: brew install ffmpeg (macOS) or apt install ffmpeg (Ubuntu)\n")
            return False

        # Generate output filename
        base_name = input_file.rsplit('.ts', 1)[0]
        temp_output = f"{base_name}_repaired.ts"

        print(f"Repairing file with ffmpeg...")

        try:
            # Run ffmpeg with error detection and genpts flags
            result = subprocess.run(
                [
                    'ffmpeg',
                    '-err_detect', 'ignore_err',
                    '-fflags', '+genpts',
                    '-i', input_file,
                    '-map', '0',
                    '-c', 'copy',
                    '-y',  # Overwrite without asking
                    temp_output
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True
            )

            # Replace original with repaired version
            os.replace(temp_output, input_file)
            print(f"✅ Repaired: {input_file}\n")
            return True

        except subprocess.CalledProcessError as e:
            print(f"⚠️  Repair failed, keeping original file\n")
            # Clean up temp file if it exists
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False
        except Exception as e:
            print(f"⚠️  Repair error: {e}\n")
            if os.path.exists(temp_output):
                os.remove(temp_output)
            return False

    def download_file(self, url, filename, chunk_percent=10, duration_minutes=30):
        """Download file using wget with chunked restarts to avoid throttling"""
        print(f"\nDownloading: {filename}")
        print(f"Restarting every {chunk_percent}% to avoid bandwidth throttling\n")

        if not shutil.which('wget'):
            print("⛔ wget is required for downloads. Install with: brew install wget")
            return False

        # Initialize tracking
        chunk_num = 0
        last_restart_percent = 0
        total_start_time = time.time()
        initial_size = os.path.getsize(filename) if os.path.exists(filename) else 0

        download_complete = False

        while not download_complete:
            chunk_num += 1
            target_percent = min(last_restart_percent + chunk_percent, 100)
            chunk_start_time = time.time()
            chunk_start_size = os.path.getsize(filename) if os.path.exists(filename) else 0
            we_terminated = False

            print(f"Chunk {chunk_num}: {last_restart_percent}% -> {target_percent}%")

            # Start wget with progress output
            if chunk_num == 1 and not os.path.exists(filename):
                cmd = ['wget', '--progress=dot:mega', '-O', filename, url]
            else:
                cmd = ['wget', '--progress=dot:mega', '-c', '-O', filename, url]

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                bufsize=1
            )

            current_percent = last_restart_percent
            try:
                for line in process.stdout:
                    # Parse wget's dot progress output for percentage and speed
                    # Format: "    50M .......... .......... .......... ..........  73% 10.2M"
                    match = re.search(r'\s(\d+)%\s+([\d.]+[KMG]?)', line)
                    if match:
                        current_percent = int(match.group(1))
                        current_speed = match.group(2)

                        # Calculate chunk average
                        chunk_elapsed = time.time() - chunk_start_time
                        current_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                        chunk_downloaded = current_size - chunk_start_size
                        chunk_avg_mbps = chunk_downloaded / chunk_elapsed / (1024 * 1024) if chunk_elapsed > 0 else 0

                        # Calculate overall average
                        total_elapsed = time.time() - total_start_time
                        total_downloaded = current_size - initial_size
                        overall_avg_mbps = total_downloaded / total_elapsed / (1024 * 1024) if total_elapsed > 0 else 0

                        # Show progress
                        print(f"\r  Progress: {current_percent}% | "
                              f"Speed: {current_speed}B/s | "
                              f"Chunk avg: {chunk_avg_mbps:.1f} MB/s | "
                              f"Overall avg: {overall_avg_mbps:.1f} MB/s   ", end='', flush=True)

                        # Check if we hit target percentage
                        if current_percent >= target_percent and current_percent < 100:
                            print()  # New line
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
                            we_terminated = True
                            last_restart_percent = current_percent
                            break

                # Process ended - check why
                if not we_terminated:
                    exit_code = process.poll()
                    if exit_code == 0 or current_percent >= 100:
                        print()  # New line after progress
                        download_complete = True
                    elif exit_code is not None and exit_code != 0:
                        print(f"\n⛔ Download failed with exit code {exit_code}")
                        return False

            except KeyboardInterrupt:
                process.terminate()
                current_size = os.path.getsize(filename) if os.path.exists(filename) else 0
                print(f"\n\n⚠️  Download interrupted at {current_size / (1024 * 1024):.1f} MB")
                print(f"💡 Resume with: wget -c -O '{filename}' '{url}'")
                return False

        # Final stats
        final_size = os.path.getsize(filename) if os.path.exists(filename) else 0
        total_elapsed = time.time() - total_start_time
        total_downloaded = final_size - initial_size
        overall_avg_speed = total_downloaded / total_elapsed / (1024 * 1024) if total_elapsed > 0 else 0

        print(f"\n✅ Download complete: {filename}")
        print(f"   Size: {final_size / (1024 * 1024):.1f} MB | Time: {total_elapsed:.0f}s | Avg speed: {overall_avg_speed:.1f} MB/s")
        print(f"   Chunks: {chunk_num} (restarted {chunk_num - 1} times)\n")
        return True

    def generate_url(self, stream_id, start_datetime, duration_minutes):
        """Generate the catchup URL"""
        # Adjust for BST if needed
        if self.is_bst(start_datetime):
            start_datetime = start_datetime - timedelta(hours=1)
            print("🇬🇧 BST detected – 1 hour was subtracted from the time.")

        start_str = self.format_start_time(start_datetime)
        url = f"{self.config['archiveBase']}/{self.config['username']}/{self.config['password']}/{duration_minutes}/{start_str}/{stream_id}.ts"
        return url

    def select_from_list_interactive(self, items, title, name_key='name', default_value=None, id_key=None):
        """Interactive selection using arrow keys"""
        if not INTERACTIVE_MODE:
            return self.select_from_list_fallback(items, title, name_key, default_value, id_key)

        # Find default cursor position
        cursor_index = 0
        if default_value and id_key:
            for i, item in enumerate(items):
                if item.get(id_key) == default_value:
                    cursor_index = i
                    break

        # Replace | with a visual separator to avoid column splitting
        options = [item[name_key].replace('|', ' │ ') for item in items]
        terminal_menu = TerminalMenu(
            options,
            title=title,
            menu_cursor="➤ ",
            menu_cursor_style=("fg_cyan", "bold"),
            menu_highlight_style=("bg_cyan", "fg_black"),
            cycle_cursor=True,
            clear_screen=False,
            multi_select=False,
            show_multi_select_hint=False,
            cursor_index=cursor_index,
        )

        menu_entry_index = terminal_menu.show()

        if menu_entry_index is None:
            print("\n👋 Goodbye!")
            sys.exit(0)

        return items[menu_entry_index]

    def select_from_list_fallback(self, items, title, name_key='name', default_value=None, id_key=None):
        """Fallback selection for when simple-term-menu is not installed"""
        # Find default index
        default_idx = None
        if default_value and id_key:
            for i, item in enumerate(items):
                if item.get(id_key) == default_value:
                    default_idx = i + 1
                    break

        print(f"\n{title}")
        print("-" * 60)
        for idx, item in enumerate(items, 1):
            marker = " *" if idx == default_idx else ""
            print(f"  {idx}. {item[name_key]}{marker}")
        print()

        prompt = f"Select (1-{len(items)})"
        if default_idx:
            prompt += f" [default: {default_idx}]"
        prompt += ": "

        while True:
            try:
                choice = input(prompt).strip()
                if not choice and default_idx:
                    return items[default_idx - 1]
                idx = int(choice) - 1
                if 0 <= idx < len(items):
                    return items[idx]
                print("⛔ Invalid selection. Please try again.")
            except (ValueError, KeyboardInterrupt):
                print("\n👋 Goodbye!")
                sys.exit(0)

    def get_last_7_days(self):
        """Generate list of last 7 days in reverse order (today first)"""
        days = []
        today = datetime.now()

        for i in range(7):
            day = today - timedelta(days=i)
            days.append({
                'date': day,
                'display': f"{day.strftime('%A')} - {day.strftime('%Y-%m-%d')}"
            })

        return days

    def select_date(self):
        """Interactive date selection from last 7 days"""
        days = self.get_last_7_days()

        if INTERACTIVE_MODE:
            selected = self.select_from_list_interactive(days, "Select Date:", 'display')
            return selected['date']
        else:
            print("\nSelect Date:")
            print("-" * 60)
            for idx, day in enumerate(days, 1):
                print(f"  {idx}. {day['display']}")
            print()

            while True:
                try:
                    choice = input(f"Select (1-{len(days)}): ").strip()
                    idx = int(choice) - 1
                    if 0 <= idx < len(days):
                        return days[idx]['date']
                    print("⛔ Invalid selection. Please try again.")
                except (ValueError, KeyboardInterrupt):
                    print("\n👋 Goodbye!")
                    sys.exit(0)

    def get_time_input(self, default_time=None):
        """Get time in 24h format without colon (e.g., 1745)"""
        while True:
            try:
                prompt = "\nEnter time (24h format, e.g., 1745 for 5:45 PM)"
                if default_time:
                    prompt += f" [{default_time[:2]}:{default_time[2:]}]"
                prompt += ": "

                time_str = input(prompt).strip()

                # Use default if empty and default exists
                if not time_str and default_time:
                    time_str = default_time

                if not time_str:
                    print("⛔ Please enter a time")
                    continue

                # Remove any colons if user includes them
                time_str = time_str.replace(':', '')

                # Validate format
                if len(time_str) == 3:
                    # Handle 3-digit input like 945 as 0945
                    time_str = '0' + time_str
                elif len(time_str) != 4:
                    print("⛔ Invalid format. Please enter 4 digits (e.g., 1745)")
                    continue

                hours = int(time_str[:2])
                minutes = int(time_str[2:])

                if hours > 23 or minutes > 59:
                    print("⛔ Invalid time. Hours must be 00-23, minutes 00-59")
                    continue

                return hours, minutes

            except ValueError:
                print("⛔ Invalid format. Please enter numbers only (e.g., 1745)")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)

    def run_interactive(self):
        """Run interactive mode"""
        print("=" * 60)
        print("IPTV Catchup URL Generator")
        print("=" * 60)
        print()

        # Show cache info if available
        if self.cache:
            print(f"💡 Last session: {self.cache.get('stream_name', 'Unknown')} (press Enter to reuse)\n")

        # Get categories
        print("Loading categories...")
        categories = self.get_categories()
        print(f"✅ Loaded {len(categories)} categories")

        if INTERACTIVE_MODE:
            print("💡 Use arrow keys to navigate, Enter to select, q to quit\n")

        # Select category (with cached default)
        selected_category = self.select_from_list_interactive(
            categories,
            "Select a Category:",
            'category_name',
            default_value=self.cache.get('category_id'),
            id_key='category_id'
        )

        print(f"\n✅ Selected: {selected_category['category_name']}")

        # Get streams
        print("Loading streams with catchup...")
        streams = self.get_streams(selected_category['category_id'])

        if not streams:
            print("⛔ No streams with catchup found in this category")
            sys.exit(1)

        print(f"✅ Loaded {len(streams)} streams")

        # Select stream (with cached default if same category)
        default_stream = None
        if self.cache.get('category_id') == selected_category['category_id']:
            default_stream = self.cache.get('stream_id')

        selected_stream = self.select_from_list_interactive(
            streams,
            "Select a Stream:",
            'name',
            default_value=default_stream,
            id_key='stream_id'
        )

        print(f"\n✅ Selected: {selected_stream['name']}")

        # Get date from menu (last 7 days)
        selected_date = self.select_date()
        print(f"\n✅ Selected: {selected_date.strftime('%A, %Y-%m-%d')}")

        # Get time in 24h format (with cached default if same stream)
        default_time = None
        if self.cache.get('stream_id') == selected_stream['stream_id']:
            default_time = self.cache.get('time')

        hours, minutes = self.get_time_input(default_time=default_time)
        print(f"✅ Selected time: {hours:02d}:{minutes:02d}")

        # Save to cache
        self.save_cache(
            category_id=selected_category['category_id'],
            category_name=selected_category['category_name'],
            stream_id=selected_stream['stream_id'],
            stream_name=selected_stream['name'],
            date_str=selected_date.strftime('%Y-%m-%d'),
            time_str=f"{hours:02d}{minutes:02d}"
        )

        # Combine date and time
        start_dt = selected_date.replace(hour=hours, minute=minutes, second=0, microsecond=0)

        # Get duration
        while True:
            try:
                duration_str = input("\nDuration (minutes) [default: 30]: ").strip()
                if not duration_str:
                    duration = 30
                else:
                    duration = int(duration_str)
                    if duration <= 0:
                        print("⛔ Duration must be positive")
                        continue
                break
            except ValueError:
                print("⛔ Invalid duration. Please enter a number.")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                sys.exit(0)

        # Generate URL
        print("\n" + "=" * 60)
        url = self.generate_url(selected_stream['stream_id'], start_dt, duration)
        print("Generated Catchup URL:")
        print("=" * 60)
        print(url)
        print("=" * 60)

        # Copy to clipboard (optional, best effort)
        try:
            if sys.platform == 'darwin':  # macOS
                subprocess.run(['pbcopy'], input=url.encode(), check=True)
                print("✅ URL copied to clipboard!")
            elif sys.platform == 'linux':  # Linux
                # Try xclip first, then xsel
                try:
                    subprocess.run(['xclip', '-selection', 'clipboard'], input=url.encode(), check=True)
                    print("✅ URL copied to clipboard!")
                except FileNotFoundError:
                    try:
                        subprocess.run(['xsel', '--clipboard', '--input'], input=url.encode(), check=True)
                        print("✅ URL copied to clipboard!")
                    except FileNotFoundError:
                        print("💡 Install xclip or xsel for clipboard support")
        except Exception:
            pass

        # Ask if user wants to download
        print()
        while True:
            try:
                download_choice = input("Do you want to download this file? (y/n) [y]: ").strip().lower()
                if download_choice == 'n':
                    print("👋 Goodbye!")
                    return
                elif download_choice == '' or download_choice == 'y':
                    break
                else:
                    print("⛔ Please enter 'y' or 'n'")
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                return

        # Generate default filename
        # Format: StreamName_DayOfWeek_Date_Time.ts
        stream_name = self.sanitize_filename(selected_stream['name'])
        day_of_week = start_dt.strftime('%A')
        date_str = start_dt.strftime('%Y-%m-%d')
        time_str = start_dt.strftime('%H%M')
        default_filename = f"{stream_name}_{day_of_week}_{date_str}_{time_str}.ts"

        # Ask for filename
        print(f"\nDefault filename: {default_filename}")
        try:
            custom_filename = input("Enter filename (press Enter for default): ").strip()
            if custom_filename:
                # Make sure it has .ts extension
                if not custom_filename.endswith('.ts'):
                    custom_filename += '.ts'
                filename = self.sanitize_filename(custom_filename)
            else:
                filename = default_filename
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            return

        # Download the file
        success = self.download_file(url, filename, duration_minutes=duration)

        if success:
            # Automatically repair the file
            self.repair_ts_file(filename)


def main():
    generator = CatchupGenerator()
    generator.run_interactive()


if __name__ == "__main__":
    main()
