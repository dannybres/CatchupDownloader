#!/usr/bin/env python3
"""
IPTV Catchup URL Generator
Command-line version of the HTML-based generator
"""

import json
import sys
import os
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
    def __init__(self, config_file="config.json"):
        # If relative path, look in the script's directory (resolve symlinks)
        if not os.path.isabs(config_file):
            # Resolve symlinks to get the actual script location
            script_path = os.path.realpath(__file__)
            script_dir = os.path.dirname(script_path)
            self.config_file = os.path.join(script_dir, config_file)
        else:
            self.config_file = config_file
        self.config = self.load_config()

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
            with urllib.request.urlopen(url, timeout=10) as response:
                return json.loads(response.read().decode())
        except Exception as e:
            print(f"⛔ Error fetching data: {e}")
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

    def download_file(self, url, filename):
        """Download file using wget or urllib"""
        print(f"\nDownloading: {filename}\n")

        # Check if wget is available
        if shutil.which('wget'):
            try:
                # Use wget with clean progress bar (suppress verbose output)
                result = subprocess.run(
                    ['wget', '-q', '--show-progress', '-O', filename, url],
                    check=True
                )
                print(f"\n✅ Download complete: {filename}\n")
                return True
            except subprocess.CalledProcessError as e:
                print(f"⛔ Download failed: {e}\n")
                return False
        else:
            # Fallback to urllib
            try:
                def progress_hook(block_num, block_size, total_size):
                    if total_size > 0:
                        percent = min(100, (block_num * block_size * 100) // total_size)
                        bar_length = 40
                        filled = int(bar_length * percent / 100)
                        bar = '█' * filled + '░' * (bar_length - filled)
                        mb_downloaded = (block_num * block_size) / (1024 * 1024)
                        mb_total = total_size / (1024 * 1024)
                        print(f'\r{bar} {percent}% ({mb_downloaded:.1f}/{mb_total:.1f} MB)', end='', flush=True)

                urllib.request.urlretrieve(url, filename, reporthook=progress_hook)
                print(f"\n✅ Download complete: {filename}\n")
                return True
            except Exception as e:
                print(f"⛔ Download failed: {e}\n")
                return False

    def generate_url(self, stream_id, start_datetime, duration_minutes):
        """Generate the catchup URL"""
        # Adjust for BST if needed
        if self.is_bst(start_datetime):
            from datetime import timedelta
            start_datetime = start_datetime - timedelta(hours=1)
            print("🇬🇧 BST detected – 1 hour was subtracted from the time.")

        start_str = self.format_start_time(start_datetime)
        url = f"{self.config['archiveBase']}/{self.config['username']}/{self.config['password']}/{duration_minutes}/{start_str}/{stream_id}.ts"
        return url

    def select_from_list_interactive(self, items, title, name_key='name'):
        """Interactive selection using arrow keys"""
        if not INTERACTIVE_MODE:
            return self.select_from_list_fallback(items, title, name_key)

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
        )

        menu_entry_index = terminal_menu.show()

        if menu_entry_index is None:
            print("\n👋 Goodbye!")
            sys.exit(0)

        return items[menu_entry_index]

    def select_from_list_fallback(self, items, title, name_key='name'):
        """Fallback selection for when simple-term-menu is not installed"""
        print(f"\n{title}")
        print("-" * 60)
        for idx, item in enumerate(items, 1):
            print(f"  {idx}. {item[name_key]}")
        print()

        while True:
            try:
                choice = input(f"Select (1-{len(items)}): ").strip()
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

    def get_time_input(self):
        """Get time in 24h format without colon (e.g., 1745)"""
        while True:
            try:
                time_str = input("\nEnter time (24h format, e.g., 1745 for 5:45 PM): ").strip()

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

        # Get categories
        print("Loading categories...")
        categories = self.get_categories()
        print(f"✅ Loaded {len(categories)} categories")

        if INTERACTIVE_MODE:
            print("💡 Use arrow keys to navigate, Enter to select, q to quit\n")

        # Select category
        selected_category = self.select_from_list_interactive(
            categories,
            "Select a Category:",
            'category_name'
        )

        print(f"\n✅ Selected: {selected_category['category_name']}")

        # Get streams
        print("Loading streams with catchup...")
        streams = self.get_streams(selected_category['category_id'])

        if not streams:
            print("⛔ No streams with catchup found in this category")
            sys.exit(1)

        print(f"✅ Loaded {len(streams)} streams")

        # Select stream
        selected_stream = self.select_from_list_interactive(
            streams,
            "Select a Stream:",
            'name'
        )

        print(f"\n✅ Selected: {selected_stream['name']}")

        # Get date from menu (last 7 days)
        selected_date = self.select_date()
        print(f"\n✅ Selected: {selected_date.strftime('%A, %Y-%m-%d')}")

        # Get time in 24h format
        hours, minutes = self.get_time_input()
        print(f"✅ Selected time: {hours:02d}:{minutes:02d}")

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
                download_choice = input("Do you want to download this file? (y/n) [n]: ").strip().lower()
                if download_choice == '' or download_choice == 'n':
                    print("👋 Goodbye!")
                    return
                elif download_choice == 'y':
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
        success = self.download_file(url, filename)

        if success:
            # Automatically repair the file
            self.repair_ts_file(filename)


def main():
    generator = CatchupGenerator()
    generator.run_interactive()


if __name__ == "__main__":
    main()
