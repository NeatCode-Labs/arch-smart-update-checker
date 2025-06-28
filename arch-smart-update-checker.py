#!/usr/bin/env python3
"""
Arch Smart Update Checker by NeatCode Labs
A smart replacement for 'sudo pacman -Syu' that checks Arch Linux news feeds
and informs you about news related to your installed packages.

Inspired by informant (https://github.com/bradford-smith94/informant)

Author: NeatCode Labs
Website: https://neatcodelabs.com
GitHub: https://github.com/NeatCode-Labs/arch-smart-update-checker
"""

# Standard library imports
import os
import sys
import re
import subprocess
import json
import hashlib
import shutil
import textwrap
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional

# Third-party imports
import feedparser
from colorama import init, Fore, Style

# Concurrency
import concurrent.futures

# CLI helpers
import argparse
from urllib.parse import urlparse

# Initialize colorama for cross-platform colored output
init(autoreset=True)

class Colors:
    """Terminal color constants"""
    HEADER = Fore.CYAN + Style.BRIGHT
    WARNING = Fore.YELLOW
    ERROR = Fore.RED
    SUCCESS = Fore.GREEN
    INFO = Fore.BLUE
    RESET = Style.RESET_ALL
    BOLD = Style.BRIGHT

class Pager:
    """Simple pager for displaying content that doesn't fit on screen"""
    def __init__(self):
        self.lines = []
        self.current_line = 0

    def add_line(self, line: str):
        """Add a line to the pager buffer"""
        # Handle ANSI color codes properly when wrapping
        wrapper = textwrap.TextWrapper(width=self.get_terminal_width() - 2)
        # Split on newlines first
        for part in line.split('\n'):
            if part:
                # Wrap long lines
                wrapped = wrapper.wrap(part)
                if wrapped:
                    self.lines.extend(wrapped)
                else:
                    self.lines.append('')
            else:
                self.lines.append('')

    def add_lines(self, lines: List[str]):
        """Add multiple lines to the pager buffer"""
        for line in lines:
            self.add_line(line)

    def get_terminal_size(self) -> Tuple[int, int]:
        """Get terminal size (width, height)"""
        try:
            size = shutil.get_terminal_size((80, 24))
            return size.columns, size.lines
        except:
            return 80, 24

    def get_terminal_width(self) -> int:
        """Get terminal width"""
        return self.get_terminal_size()[0]

    def get_terminal_height(self) -> int:
        """Get terminal height"""
        return self.get_terminal_size()[1]

    def display(self):
        """Display the content with pagination"""
        if not self.lines:
            return

        terminal_height = self.get_terminal_height()
        # Reserve lines for prompt
        display_height = terminal_height - 3

        total_lines = len(self.lines)

        while self.current_line < total_lines:
            # Clear screen
            os.system('clear' if os.name != 'nt' else 'cls')

            # Display lines for current page
            end_line = min(self.current_line + display_height, total_lines)
            for i in range(self.current_line, end_line):
                print(self.lines[i])

            # Check if we've reached the end
            if end_line >= total_lines:
                print(f"\n{Colors.INFO}(END) Press any key to continue...{Colors.RESET}")
                try:
                    # Get single keypress
                    import termios, tty
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        sys.stdin.read(1)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
                except:
                    # Fallback for non-Unix systems
                    input()
                break
            else:
                # Show progress and prompt
                progress = f"Lines {self.current_line + 1}-{end_line} of {total_lines}"
                prompt = f"{Colors.INFO}{progress} -- Press SPACE for next page, 'q' to skip...{Colors.RESET}"
                print(f"\n{prompt}")

                try:
                    # Get single keypress
                    import termios, tty
                    fd = sys.stdin.fileno()
                    old_settings = termios.tcgetattr(fd)
                    try:
                        tty.setraw(sys.stdin.fileno())
                        key = sys.stdin.read(1)
                    finally:
                        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

                    if key.lower() == 'q':
                        break
                    else:
                        self.current_line = end_line
                except:
                    # Fallback for non-Unix systems
                    response = input()
                    if response.lower() == 'q':
                        break
                    else:
                        self.current_line = end_line

        # Clear the buffer after display
        self.lines = []
        self.current_line = 0

class ArchUpdateChecker:
    def __init__(self):
        self.news_feeds: List[Dict] = []  # will be filled from user/default config

        # Default feed definitions (used if config is missing)
        self.default_feeds = [
            { "name": "Arch Linux News", "url": "https://archlinux.org/feeds/news/", "priority": 1 },
            { "name": "Arch Linux Security Advisories", "url": "https://security.archlinux.org/advisory/feed.atom", "priority": 1 },
            { "name": "Arch32 News", "url": "https://bbs.archlinux32.org/extern.php?action=feed&fid=12&type=atom", "priority": 2 },
            # High-volume package feed – marked as type "package" so we can filter strictly
            { "name": "Arch Stable Package Updates", "url": "https://archlinux.org/feeds/packages/all/stable-repos/", "priority": 4, "type": "package" }
        ]

        # Distro-specific feeds (auto-appended if not already in config)
        distro = self.detect_distribution()
        if distro == "endeavouros":
            self.default_feeds.append({ "name": "EndeavourOS News", "url": "https://endeavouros.com/feed/", "priority": 3 })
        elif distro == "manjaro":
            self.default_feeds.append({ "name": "Manjaro Stable Updates", "url": "https://forum.manjaro.org/c/announcements/stable-updates/12.rss", "priority": 3 })

        # Common package name patterns to look for in news
        self.critical_patterns = [
            r'\b(linux|linux-\w+)\b',  # Kernel packages
            r'\b(nvidia|nvidia-\w+)\b',  # NVIDIA drivers
            r'\b(xorg-server|xorg-\w+)\b',  # X.org packages
            r'\b(systemd)\b',  # Systemd
            r'\b(grub|grub-\w+)\b',  # Bootloader
            r'\b(glibc)\b',  # C library
            r'\b(gcc|gcc-\w+)\b',  # Compiler
            r'\b(python|python3)\b',  # Python
            r'\b(pacman)\b',  # Package manager itself
            r'\b(openssl)\b',  # SSL library
            r'\b(pam)\b',  # PAM
            r'\b(dbus)\b',  # D-Bus
        ]

        self.cache_dir = os.path.expanduser("~/.cache/arch-smart-update-checker")
        os.makedirs(self.cache_dir, exist_ok=True)

        # Cache TTL in hours (default 1)
        self.cache_ttl_hours: int = 1

        # Load user configuration (feeds, patterns, etc.)
        self.load_user_config()

        # Ensure we have at least the default feeds
        if not self.news_feeds:
            self.news_feeds = self.default_feeds.copy()

        # Generic names that often cause false positives
        self.generic_names = {
            "linux", "systemd", "python", "gcc", "glibc", "pam", "dbus"
        }

        # Placeholder attributes set later
        self.installed_packages: Dict[str, str] = {}
        self.non_interactive: bool = False
        self.log_file: Optional[str] = None

    def detect_distribution(self) -> str:
        """Detect which Arch-based distribution is being used"""
        try:
            # Check /etc/os-release
            if os.path.exists("/etc/os-release"):
                with open("/etc/os-release", "r") as f:
                    content = f.read().lower()
                    if "endeavouros" in content:
                        return "endeavouros"
                    elif "manjaro" in content:
                        return "manjaro"
                    elif "arch" in content:
                        return "arch"

            # Check for distro-specific files
            if os.path.exists("/usr/share/endeavouros"):
                return "endeavouros"
            elif os.path.exists("/etc/manjaro-release"):
                return "manjaro"

            # Default to Arch
            return "arch"

        except Exception:
            return "arch"

    def get_installed_packages(self) -> Dict[str, str]:
        """Get list of installed packages with versions"""
        try:
            result = subprocess.run(
                ["pacman", "-Q"],
                capture_output=True,
                text=True,
                check=True
            )

            packages = {}
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split()
                    if len(parts) >= 2:
                        packages[parts[0]] = parts[1]

            return packages
        except subprocess.CalledProcessError as e:
            print(f"{Colors.ERROR}Error getting installed packages: {e}")
            return {}

    def fetch_news_feed(self, feed_info: Dict) -> List[Dict]:
        """Fetch and parse a single RSS feed"""
        try:
            # Check cache first (1 hour cache)
            cache_file = os.path.join(
                self.cache_dir,
                hashlib.md5(feed_info['url'].encode()).hexdigest() + ".json"
            )

            if os.path.exists(cache_file):
                cache_time = datetime.fromtimestamp(os.path.getmtime(cache_file))
                if datetime.now() - cache_time < timedelta(hours=self.cache_ttl_hours):
                    with open(cache_file, 'r') as f:
                        cached_items = json.load(f)
                        # Convert date strings back to datetime objects
                        for item in cached_items:
                            if item.get('date'):
                                try:
                                    item['date'] = datetime.fromisoformat(item['date'])
                                except:
                                    item['date'] = None
                        return cached_items

            # Fetch fresh data
            feed = feedparser.parse(feed_info['url'])

            if feed.bozo:
                print(f"{Colors.WARNING}Warning: Failed to parse {feed_info['name']} feed properly")
                return []

            news_items = []
            for entry in feed.entries[:10]:  # Last 10 entries
                # Parse date
                published = None
                if hasattr(entry, 'published_parsed') and entry.published_parsed:
                    published = datetime(*entry.published_parsed[:6])
                elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                    published = datetime(*entry.updated_parsed[:6])

                # Extract content
                content = ""
                if hasattr(entry, 'summary'):
                    content = entry.summary
                elif hasattr(entry, 'description'):
                    content = entry.description

                # Clean HTML tags
                content = re.sub('<.*?>', '', content)
                content = content.strip()

                news_items.append({
                    'title': entry.title,
                    'link': entry.link,
                    'date': published,  # Store as datetime object, not string
                    'content': content,
                    'source': feed_info['name'],
                    'priority': feed_info['priority'],
                    'source_type': feed_info.get('type', 'news')
                })

            # Cache the results - convert datetime to string for JSON
            cache_items = []
            for item in news_items:
                cache_item = item.copy()
                if cache_item['date']:
                    cache_item['date'] = cache_item['date'].isoformat()
                cache_items.append(cache_item)

            with open(cache_file, 'w') as f:
                json.dump(cache_items, f)

            return news_items

        except Exception as e:
            print(f"{Colors.WARNING}Error fetching {feed_info['name']}: {e}")
            return []

    def extract_package_names(self, text: str) -> List[str]:
        """Extract potential package names from news text"""
        packages = set()

        # Look for explicit package mentions
        # Pattern 1: package-name-1.2.3
        pattern1 = re.findall(r'\b([a-z0-9][a-z0-9\-_]+[a-z0-9])\s*[-]?\s*\d+[\.\d\-\w]*\b', text, re.IGNORECASE)
        packages.update(p.lower() for p in pattern1)

        # Pattern 2: quoted package names
        pattern2 = re.findall(r'["\']([a-z0-9][a-z0-9\-_]+[a-z0-9])["\']', text, re.IGNORECASE)
        packages.update(p.lower() for p in pattern2)

        # Pattern 3: backtick code blocks
        pattern3 = re.findall(r'`([a-z0-9][a-z0-9\-_]+[a-z0-9])`', text, re.IGNORECASE)
        packages.update(p.lower() for p in pattern3)

        # Check against critical patterns
        for pattern in self.critical_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            packages.update(m.lower() for m in matches)

        return list(packages)

    def analyze_news_relevance(self, news_item: Dict, installed_packages: Dict[str, str]) -> Tuple[bool, List[str]]:
        """Analyze if a news item is relevant to the system"""
        full_text = f"{news_item['title']} {news_item['content']}"

        # Special handling for feeds that are pure package update listings
        if news_item.get('source_type') == 'package':
            # Package name is first token in title
            pkg_name = news_item['title'].split()[0].lower()
            mentioned_packages = [pkg_name]
        else:
            mentioned_packages = self.extract_package_names(full_text)

        # Filter overly generic names unless they appear in the title (reduces false positives)
        filtered_packages = []
        title_lower = news_item["title"].lower()
        for pkg in mentioned_packages:
            if pkg in self.generic_names and pkg not in title_lower:
                continue
            filtered_packages.append(pkg)
        mentioned_packages = filtered_packages

        # Find which mentioned packages are installed
        affected_packages = []
        for pkg in mentioned_packages:
            if pkg in installed_packages:
                affected_packages.append(pkg)
            # Also check for partial matches (e.g., 'linux' matches 'linux-lts')
            else:
                for installed_pkg in installed_packages:
                    if pkg in installed_pkg or installed_pkg in pkg:
                        affected_packages.append(installed_pkg)
                        break

        # Remove duplicates
        affected_packages = list(set(affected_packages))

        # Check if news is recent (within 30 days)
        is_recent = True
        if news_item['date']:
            age = datetime.now() - news_item['date']
            is_recent = age.days <= 30

        is_relevant = len(affected_packages) > 0 and is_recent

        return is_relevant, affected_packages

    def format_news_item(self, news_item: Dict, affected_packages: List[str]) -> List[str]:
        """Format a news item and return as list of lines"""
        lines = []

        lines.append(f"\n{Colors.INFO}📰 News:{Colors.RESET}")
        lines.append(f"{Colors.BOLD}{news_item['title']}{Colors.RESET}")
        lines.append(f"{Colors.INFO}Source: {news_item['source']} | Date: {news_item['date'].strftime('%Y-%m-%d') if news_item['date'] else 'Unknown'}")

        # Wrap content
        wrapper = textwrap.TextWrapper(width=80, initial_indent="  ", subsequent_indent="  ")
        wrapped_content = wrapper.wrap(news_item['content'][:500] + "..." if len(news_item['content']) > 500 else news_item['content'])
        lines.append("")
        for line in wrapped_content[:5]:  # Show first 5 lines
            lines.append(line)

        if len(wrapped_content) > 5:
            lines.append(f"  {Colors.INFO}[...truncated. See full article: {news_item['link']}]")

        # Show affected packages
        if affected_packages:
            lines.append(f"\n  {Colors.WARNING}Your affected packages:{Colors.RESET}")
            for pkg in affected_packages[:10]:  # Show max 10 packages
                version = self.installed_packages.get(pkg, "unknown")
                lines.append(f"    • {pkg} ({version})")
            if len(affected_packages) > 10:
                lines.append(f"    • ... and {len(affected_packages) - 10} more")

        lines.append("")  # Add spacing between items
        return lines

    def display_news_item(self, news_item: Dict, affected_packages: List[str]):
        """Display a formatted news item"""
        lines = self.format_news_item(news_item, affected_packages)
        for line in lines:
            print(line)

    def check_pending_updates(self) -> List[str]:
        """Check which packages have updates available"""
        try:
            # Prefer checkupdates if available (from pacman-contrib) – safe because it works on a copy of the database
            if shutil.which("checkupdates"):
                result = subprocess.run(["checkupdates"], capture_output=True, text=True)
            else:
                print(f"{Colors.WARNING}checkupdates not found. Falling back to 'pacman -Qu' (database may be stale).{Colors.RESET}")
                result = subprocess.run(["pacman", "-Qu"], capture_output=True, text=True)

            updates = []
            if result.stdout:
                for line in result.stdout.strip().split('\n'):
                    if line:
                        # Extract package name from update line
                        parts = line.split()
                        if parts:
                            updates.append(parts[0])

            return updates

        except subprocess.CalledProcessError:
            print(f"{Colors.WARNING}Could not check for pending updates")
            return []

    def run(self, show_all_news: bool = False, non_interactive: bool = False, log_file: Optional[str] = None):
        """Main execution flow"""
        self.non_interactive = non_interactive
        self.log_file = log_file

        print(f"{Colors.HEADER}{'='*80}")
        print(f"{Colors.HEADER}Arch Smart Update Checker")
        print(f"{Colors.HEADER}{'='*80}{Colors.RESET}\n")

        # Show detected distribution
        distro = self.detect_distribution()
        if distro != "arch":
            print(f"{Colors.INFO}Detected distribution: {distro.capitalize()}{Colors.RESET}")

        # Get installed packages
        print(f"{Colors.INFO}Scanning installed packages...{Colors.RESET}")
        self.installed_packages = self.get_installed_packages()
        print(f"  Found {len(self.installed_packages)} installed packages")

        # Check pending updates
        pending_updates = self.check_pending_updates()
        if pending_updates:
            print(f"\n{Colors.INFO}Found {len(pending_updates)} packages with updates available{Colors.RESET}")
        else:
            print(f"\n{Colors.SUCCESS}Your system is up to date!{Colors.RESET}")
            if not show_all_news:
                return

        # Fetch news from all sources concurrently for speed
        print(f"\n{Colors.INFO}Fetching news from RSS feeds...{Colors.RESET}")
        all_news = []
        max_workers = max(1, min(8, len(self.news_feeds)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_feed = {executor.submit(self.fetch_news_feed, feed): feed for feed in self.news_feeds}
            for future in concurrent.futures.as_completed(future_to_feed):
                feed = future_to_feed[future]
                try:
                    news_items = future.result()
                except Exception as e:
                    print(f"  • {feed['name']} {Colors.ERROR}✗ ({e}){Colors.RESET}")
                    continue
                all_news.extend(news_items)
                print(f"  • {feed['name']} {Colors.SUCCESS}✓{Colors.RESET} ({len(news_items)} items)")

        # Sort by date and priority
        all_news.sort(key=lambda x: (x['date'] or datetime.min, x['priority']), reverse=True)

        # Analyze relevance
        print(f"\n{Colors.INFO}Analyzing news relevance...{Colors.RESET}")
        relevant_warnings = []
        other_news = []

        for news_item in all_news:
            is_relevant, affected_packages = self.analyze_news_relevance(
                news_item, self.installed_packages
            )

            if is_relevant:
                relevant_warnings.append({
                    'news': news_item,
                    'packages': affected_packages
                })
            elif show_all_news:
                other_news.append(news_item)

        # Display results
        if relevant_warnings:
            # Check if we need pagination
            total_lines = 0
            for warning in relevant_warnings:
                lines = self.format_news_item(warning['news'], warning['packages'])
                total_lines += len(lines)

            # Get terminal height
            terminal_height = shutil.get_terminal_size((80, 24)).lines

            # Use pager if content won't fit on screen (leave some room for headers)
            if total_lines > terminal_height - 10:
                print(f"\n{Colors.INFO}{'='*80}")
                print(f"{Colors.INFO}📰 Important news available regarding your installed packages")
                print(f"{Colors.INFO}   Please read before updating to avoid potential problems")
                print(f"{Colors.INFO}   (News will be displayed in pages - press SPACE to continue)")
                print(f"{Colors.INFO}{'='*80}{Colors.RESET}")

                # Prepare content for pager
                pager = Pager()
                pager.add_line(f"{Colors.INFO}{'='*80}")
                pager.add_line(f"{Colors.INFO}📰 Important news available regarding your installed packages")
                pager.add_line(f"{Colors.INFO}   Please read before updating to avoid potential problems")
                pager.add_line(f"{Colors.INFO}{'='*80}{Colors.RESET}")

                for warning in relevant_warnings:
                    lines = self.format_news_item(warning['news'], warning['packages'])
                    pager.add_lines(lines)

                # Display with pagination
                pager.display()

                # Clear screen after pager
                os.system('clear' if os.name != 'nt' else 'cls')

                # Show brief summary after paging
                print(f"\n{Colors.INFO}Displayed {len(relevant_warnings)} news items affecting your packages{Colors.RESET}")
            else:
                # Display normally if it fits on screen
                print(f"\n{Colors.INFO}{'='*80}")
                print(f"{Colors.INFO}📰 Important news available regarding your installed packages")
                print(f"{Colors.INFO}   Please read before updating to avoid potential problems")
                print(f"{Colors.INFO}{'='*80}{Colors.RESET}")

                for warning in relevant_warnings:
                    self.display_news_item(
                        warning['news'],
                        warning['packages']
                    )
        else:
            print(f"\n{Colors.SUCCESS}✓ No news found affecting your installed packages{Colors.RESET}")

        # Show other news if requested
        if show_all_news and other_news:
            print(f"\n{Colors.INFO}{'='*80}")
            print(f"{Colors.INFO}Other Recent News (Not Affecting Your System)")
            print(f"{Colors.INFO}{'='*80}{Colors.RESET}")

            for news in other_news[:5]:
                print(f"\n• {news['title']}")
                print(f"  {Colors.INFO}{news['source']} | {news['date'].strftime('%Y-%m-%d') if news['date'] else 'Unknown'}{Colors.RESET}")

        # Summary and prompt
        print(f"\n{Colors.HEADER}{'='*80}")
        print(f"{Colors.HEADER}SUMMARY")
        print(f"{Colors.HEADER}{'='*80}{Colors.RESET}")

        print(f"Pending updates: {len(pending_updates)} packages")
        print(f"News items affecting your packages: {len(relevant_warnings)}")

        if not pending_updates:
            return

        # Handle logging (if requested)
        if log_file:
            try:
                with open(log_file, "a") as lf:
                    lf.write(f"[ {datetime.now().isoformat()} ] Updates: {len(pending_updates)}, Relevant news: {len(relevant_warnings)}\n")
            except Exception as e:
                print(f"{Colors.WARNING}Could not write log file: {e}{Colors.RESET}")

        # Non-interactive mode: exit status indicates whether action is needed
        if non_interactive:
            sys.exit(1 if relevant_warnings else 0)

        # Interactive prompt
        print(f"\n{Colors.BOLD}Do you want to proceed with the system update?{Colors.RESET}")
        print(f"This will run: {Colors.INFO}sudo pacman -Syu{Colors.RESET}")

        while True:
            response = input(f"\n{Colors.BOLD}Proceed? [y/N/r(efresh)/d(etails)]: {Colors.RESET}").lower().strip()

            if response == 'y':
                print(f"\n{Colors.INFO}Running system update...{Colors.RESET}")
                try:
                    subprocess.run(["sudo", "pacman", "-Syu"], check=True)
                    print(f"\n{Colors.SUCCESS}✓ Update completed successfully!{Colors.RESET}")
                except subprocess.CalledProcessError:
                    print(f"\n{Colors.ERROR}✗ Update failed or was cancelled{Colors.RESET}")
                    sys.exit(1)
                break

            elif response == 'r':
                print(f"\n{Colors.INFO}Refreshing analysis...{Colors.RESET}\n")
                self.run(show_all_news=show_all_news)
                break

            elif response == 'd':
                # Show detailed package list
                print(f"\n{Colors.INFO}Packages to be updated:{Colors.RESET}")
                for pkg in pending_updates:
                    print(f"  • {pkg}")
                continue

            else:  # Default is No
                print(f"\n{Colors.INFO}Update cancelled by user{Colors.RESET}")
                break

    # ------------------------------------------------------------------
    # Configuration handling
    # ------------------------------------------------------------------

    def load_user_config(self):
        """Merge user configuration from ~/.config/arch-smart-update-checker/config.json"""
        config_path = os.path.expanduser("~/.config/arch-smart-update-checker/config.json")

        if not os.path.exists(config_path):
            return  # Nothing to merge

        try:
            with open(config_path, "r") as f:
                cfg = json.load(f)

            # Feeds list can fully override defaults if provided
            if isinstance(cfg.get("feeds"), list) and cfg["feeds"]:
                self.news_feeds = cfg["feeds"]
            else:
                # Start with defaults, then merge additional_feeds for legacy compatibility
                self.news_feeds = self.default_feeds.copy()

            # Legacy key: additional_feeds → still supported and appended
            extra_feeds = cfg.get("additional_feeds", [])
            if isinstance(extra_feeds, list):
                self.news_feeds.extend(extra_feeds)

            # Cache TTL override
            if isinstance(cfg.get("cache_ttl_hours"), (int, float)) and cfg["cache_ttl_hours"] > 0:
                self.cache_ttl_hours = int(cfg["cache_ttl_hours"])

            # Extra patterns
            extra_patterns = cfg.get("extra_patterns", [])
            if isinstance(extra_patterns, list):
                self.critical_patterns.extend(extra_patterns)

        except Exception as e:
            print(f"{Colors.WARNING}Could not load user config: {e}{Colors.RESET}")

        # If config file missing feeds, use defaults
        if not self.news_feeds:
            self.news_feeds = self.default_feeds.copy()

    def init_default_config(self):
        """Create a starter configuration file for the user"""
        config_dir = os.path.expanduser("~/.config/arch-smart-update-checker")
        os.makedirs(config_dir, exist_ok=True)
        config_path = os.path.join(config_dir, "config.json")

        if os.path.exists(config_path):
            print(f"{Colors.INFO}Config file already exists at {config_path}{Colors.RESET}")
            return

        default_cfg = {
            "feeds": self.default_feeds,
            "additional_feeds": [
                # {"name": "Your Feed Name", "url": "https://example.com/feed", "priority": 5}
            ],
            "cache_ttl_hours": 1,
            "extra_patterns": [
                # "\\b(your-package)\\b"
            ]
        }

        with open(config_path, "w") as f:
            json.dump(default_cfg, f, indent=2)

        print(f"{Colors.SUCCESS}Default configuration created at {config_path}{Colors.RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Smart update checker for Arch Linux - informs you about news related to your packages"
    )
    parser.add_argument(
        '-a', '--all-news',
        action='store_true',
        help='Show all recent news, not just relevant ones'
    )
    parser.add_argument(
        '--non-interactive',
        action='store_true',
        help='Exit with status 1 if relevant news found; 0 otherwise (no prompts)'
    )
    parser.add_argument(
        '--log',
        metavar='FILE',
        help='Append a one-line result summary to FILE'
    )
    parser.add_argument(
        '--init-config',
        action='store_true',
        help='Create a default user configuration file and exit'
    )
    parser.add_argument(
        '--clear-cache',
        action='store_true',
        help='Clear the news cache before checking'
    )

    args = parser.parse_args()

    if os.geteuid() == 0:
        print(f"{Colors.WARNING}Warning: Running as root is not recommended{Colors.RESET}")

    checker = ArchUpdateChecker()

    if args.init_config:
        checker.init_default_config()
        sys.exit(0)

    if args.clear_cache:
        shutil.rmtree(checker.cache_dir, ignore_errors=True)
        os.makedirs(checker.cache_dir, exist_ok=True)
        print(f"{Colors.SUCCESS}Cache cleared{Colors.RESET}")

    try:
        checker.run(
            show_all_news=args.all_news,
            non_interactive=args.non_interactive,
            log_file=args.log
        )
    except KeyboardInterrupt:
        print(f"\n\n{Colors.INFO}Update check cancelled by user{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.ERROR}Error: {e}{Colors.RESET}")
        sys.exit(1)

# ------------------------------------------------------------------
# Module entry point
# ------------------------------------------------------------------

if __name__ == "__main__":
    main()
