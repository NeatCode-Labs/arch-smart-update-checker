#!/usr/bin/env python3
"""
Arch Smart Update Checker by NeatCode Labs
A smart replacement for 'sudo pacman -Syu' that checks Arch Linux news feeds
and informs you about news related to your installed packages.

Author: NeatCode Labs
Website: https://neatcodelabs.com
GitHub: https://github.com/NeatCode-Labs/arch-smart-update-checker
"""

import os
import sys
import re
import subprocess
import feedparser
import argparse
from datetime import datetime, timedelta
from typing import List, Dict, Tuple, Optional
from colorama import init, Fore, Style, Back
import textwrap
from urllib.parse import urlparse
import json
import hashlib

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

class ArchUpdateChecker:
    def __init__(self):
        # Always check these feeds
        self.news_feeds = [
            {
                "name": "Arch Linux News",
                "url": "https://archlinux.org/feeds/news/",
                "priority": 1
            },
            {
                "name": "Arch32 News",
                "url": "https://bbs.archlinux32.org/extern.php?action=feed&fid=12&type=atom",
                "priority": 2
            }
        ]
        
        # Detect distribution and add relevant feeds
        distro = self.detect_distribution()
        
        if distro == "endeavouros":
            self.news_feeds.append({
                "name": "EndeavourOS News",
                "url": "https://endeavouros.com/feed/",
                "priority": 3
            })
        elif distro == "manjaro":
            self.news_feeds.append({
                "name": "Manjaro Stable Updates",
                "url": "https://forum.manjaro.org/c/announcements/stable-updates/12.rss",
                "priority": 3
            })
        
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
                if datetime.now() - cache_time < timedelta(hours=1):
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
                    'date': published.isoformat() if published else None,
                    'content': content,
                    'source': feed_info['name'],
                    'priority': feed_info['priority']
                })
            
            # Cache the results
            with open(cache_file, 'w') as f:
                json.dump(news_items, f)
            
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
        
        # Extract mentioned packages
        mentioned_packages = self.extract_package_names(full_text)
        
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
    
    def display_news_item(self, news_item: Dict, affected_packages: List[str]):
        """Display a formatted news item"""
        print(f"\n{Colors.INFO}📰 News:{Colors.RESET}")
        print(f"{Colors.BOLD}{news_item['title']}{Colors.RESET}")
        print(f"{Colors.INFO}Source: {news_item['source']} | Date: {news_item['date'].strftime('%Y-%m-%d') if news_item['date'] else 'Unknown'}")
        
        # Wrap content
        wrapper = textwrap.TextWrapper(width=80, initial_indent="  ", subsequent_indent="  ")
        wrapped_content = wrapper.wrap(news_item['content'][:500] + "..." if len(news_item['content']) > 500 else news_item['content'])
        print()
        for line in wrapped_content[:5]:  # Show first 5 lines
            print(line)
        
        if len(wrapped_content) > 5:
            print(f"  {Colors.INFO}[...truncated. See full article: {news_item['link']}]")
        
        # Show affected packages
        if affected_packages:
            print(f"\n  {Colors.WARNING}Your affected packages:{Colors.RESET}")
            for pkg in affected_packages[:10]:  # Show max 10 packages
                version = self.installed_packages.get(pkg, "unknown")
                print(f"    • {pkg} ({version})")
            if len(affected_packages) > 10:
                print(f"    • ... and {len(affected_packages) - 10} more")
    
    def check_pending_updates(self) -> List[str]:
        """Check which packages have updates available"""
        try:
            # First sync package databases
            print(f"{Colors.INFO}Syncing package databases...{Colors.RESET}")
            subprocess.run(["sudo", "pacman", "-Sy"], check=True, capture_output=True)
            
            # Check for updates
            result = subprocess.run(
                ["pacman", "-Qu"],
                capture_output=True,
                text=True
            )
            
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
    
    def run(self, show_all_news: bool = False):
        """Main execution flow"""
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
        
        # Fetch news from all sources
        print(f"\n{Colors.INFO}Fetching news from RSS feeds...{Colors.RESET}")
        all_news = []
        for feed in self.news_feeds:
            print(f"  • Checking {feed['name']}...", end='', flush=True)
            news_items = self.fetch_news_feed(feed)
            all_news.extend(news_items)
            print(f" {Colors.SUCCESS}✓{Colors.RESET} ({len(news_items)} items)")
        
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
        
        # Simple recommendation
        if relevant_warnings:
            print(f"\n{Colors.WARNING}📰 Recommendation: Review the news above before updating{Colors.RESET}")
        else:
            print(f"\n{Colors.SUCCESS}✓ No special considerations needed for this update{Colors.RESET}")
        
        # Ask for confirmation
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
        '--clear-cache',
        action='store_true',
        help='Clear the news cache before checking'
    )
    
    args = parser.parse_args()
    
    # Check if running as root
    if os.geteuid() == 0:
        print(f"{Colors.WARNING}Warning: Running as root is not recommended{Colors.RESET}")
    
    checker = ArchUpdateChecker()
    
    if args.clear_cache:
        import shutil
        shutil.rmtree(checker.cache_dir, ignore_errors=True)
        os.makedirs(checker.cache_dir, exist_ok=True)
        print(f"{Colors.SUCCESS}Cache cleared{Colors.RESET}")
    
    try:
        checker.run(show_all_news=args.all_news)
    except KeyboardInterrupt:
        print(f"\n\n{Colors.INFO}Update check cancelled by user{Colors.RESET}")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.ERROR}Error: {e}{Colors.RESET}")
        sys.exit(1)

if __name__ == "__main__":
    main()
