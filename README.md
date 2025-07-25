<div align="center">

> ⚠️ **LEGACY VERSION (v1.0)**: This branch contains the original single-file implementation.  
> For the current version with GUI and modular architecture, see the [main branch](https://github.com/NeatCode-Labs/arch-smart-update-checker).

<img src="screenshots/icon.png" alt="Arch Smart Update Checker Icon" width="270" height="72">

<h1>🛡️ Arch Smart Update Checker</h1>

[![GitHub](https://img.shields.io/badge/GitHub-NeatCode--Labs-blue?style=flat-square&logo=github)](https://github.com/NeatCode-Labs/arch-smart-update-checker)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Arch Linux](https://img.shields.io/badge/Arch%20Linux-Compatible-1793D1?style=flat-square&logo=arch-linux)](https://archlinux.org/)
[![Python](https://img.shields.io/badge/Python-3.6%2B-blue?style=flat-square&logo=python)](https://www.python.org/)

**A smart replacement for `sudo pacman -Syu` that checks Arch Linux news feeds and informs you about news related to your installed packages before updating.**

**Created by [NeatCode Labs](https://neatcodelabs.com)**

**Inspired by [informant](https://github.com/bradford-smith94/informant)**

</div>

---

## 📋 Table of Contents

- [Features](#-features)
- [Screenshots](#-screenshots)
- [Monitored News Sources](#-monitored-news-sources)
- [Installation](#-installation)
- [Usage](#-usage)
- [How It Works](#️-how-it-works)
- [Package Detection](#-package-detection)
- [Cache Management](#-cache-management)
- [Requirements](#-requirements)
- [Troubleshooting](#-troubleshooting)
- [Contributing](#-contributing)
- [License](#-license)

## ✨ Features

- 📰 **News Feed Monitoring**: Checks multiple Arch Linux news RSS feeds for news about packages
- 📦 **Package Analysis**: Compares your installed packages against warnings in news feeds
- 🎯 **Smart Distribution Detection**: Automatically detects your Arch-based distro and monitors relevant feeds
- 🎨 **User-Friendly Interface**: Colored terminal output with clear warnings and recommendations
- ⚡ **Caching**: Caches news feeds for 1 hour to reduce network requests
- 🔄 **Interactive Prompts**: Allows you to review warnings and decide whether to proceed
- 🚦 **Non-interactive Mode**: Run in scripts/cron; exits with status 1 if news requires attention
- 📝 **Config File Support**: Extend/override feeds & patterns via `~/.config/arch-smart-update-checker/config.json`
- 📄 **Pagination Support**: Automatically paginates long news lists for easy reading in terminal-only environments
- ⚙️ **Safer Update Detection**: Uses `checkupdates` from `pacman-contrib` when available (avoids partial-upgrade risk)

## 📸 Screenshots

<div align="center">

### 🔍 Scanning System and Checking Updates
![System Scanning](screenshots/ss1.png)

### 📰 News Analysis and Package Matching
![News Analysis](screenshots/ss2.png)

### ✅ Safe Update Summary
![Update Summary](screenshots/ss3.png)

</div>

## 📡 Monitored News Sources

The tool intelligently detects your distribution and monitors relevant feeds:

### Always Monitored:
- 🏛️ **Arch Linux News** - Official Arch Linux announcements
- 🔒 **Arch Linux Security Advisories** - Security updates and advisories
- 📦 **Arch Stable Package Updates** - High-volume package update feed (with smart filtering)
- 💾 **Arch32 News** - News for 32-bit architecture support

### Distribution-Specific (only if detected):
- 🚀 **EndeavourOS News** - Only checked on EndeavourOS systems
- 🍃 **Manjaro Stable Updates** - Only checked on Manjaro systems

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/NeatCode-Labs/arch-smart-update-checker.git
cd arch-smart-update-checker
```

### 2. Run the Setup Script
```bash
./setup.sh
```

This will:
- ✅ Check and install Python dependencies (`feedparser`, `colorama`)
- 🔧 Add convenient alias to your `.bashrc`
- 🎯 Auto-detect your distribution

### 3. Reload Your Shell
```bash
source ~/.bashrc
```

### 4. (Optional) Create Your Personal Configuration

Run the tool once with `--init-config` to generate a starter file at
`~/.config/arch-smart-update-checker/config.json`.

```bash
asuc --init-config
```

If you skip this, `asuc` works with built-in defaults (Arch news, security
advisories, stable-repo package feed, plus distro-specific feeds).  Creating
the file simply gives you a place to:

* Disable or add RSS feeds (e.g. AUR "new packages" feed).
* Adjust `cache_ttl_hours`.
* Add extra regex patterns for niche packages.

Re-running `--init-config` later will not overwrite an existing file, so it is
safe to do at any time.

## 📖 Usage

### Basic Usage
Instead of running `sudo pacman -Syu`, use:
```bash
asuc
```

### Command Line Options

| Option | Description |
|--------|-------------|
| `-a, --all-news` | Show all recent news, not just relevant ones |
| `--non-interactive` | Run without prompts; exit status 1 if relevant news found |
| `--log FILE` | Append a one-line summary to FILE (useful in cron) - format: `[timestamp] Updates: X, Relevant news: Y` |
| `--clear-cache` | Clear the news cache before checking |
| `--init-config` | Create a default user config file and exit |
| `-h, --help` | Show help message |

### Examples
```bash
# Standard check with interactive prompts
asuc

# Show all news including non-relevant items
asuc -a

# Clear cache and check fresh news
asuc --clear-cache
```

## ⚙️ How It Works

1. **📊 Package Scanning**: Retrieves list of all installed packages using `pacman -Q`
2. **🔄 Update Check**: Uses `checkupdates` (from pacman-contrib) or falls back to `pacman -Qu` to check for available updates
3. **📡 News Fetching**: Downloads and parses RSS feeds from configured sources
4. **🔍 Pattern Matching**: Searches news content for package names that match your installed packages
5. **📄 Pagination**: Automatically paginates news when content exceeds terminal height
   - Press `SPACE` to continue to next page
   - Press `q` to skip remaining news
   - Similar to `less` or `more` commands
   - Also paginates package lists when using the "details" option
6. **💬 User Interaction**: Presents findings and allows you to proceed, cancel, refresh, or view details

## 🎯 Package Detection

The tool looks for package names in news feeds using multiple patterns:
- 📌 Explicit version mentions (e.g., `package-1.2.3`)
- 💬 Quoted package names
- 📝 Code blocks with backticks
- ⚠️ Critical system packages (kernel, nvidia, xorg, systemd, etc.)

## 💾 Cache Management

News feeds are cached in `~/.cache/arch-smart-update-checker/` for 1 hour to reduce network requests. Use `--clear-cache` to force fresh downloads.

## 📝 Configuration File

Advanced users can add extra RSS feeds or package-matching patterns without editing the script:

```bash
asuc --init-config   # Creates ~/.config/arch-smart-update-checker/config.json
```

Open the generated file and add entries, e.g.

```json
{
  "cache_ttl_hours": 1,
  "feeds": [
    {"name": "Arch Linux News", "url": "https://archlinux.org/feeds/news/", "priority": 1},
    {"name": "Arch Linux Security Advisories", "url": "https://security.archlinux.org/advisory/feed.atom", "priority": 1},
    {"name": "Arch Stable Package Updates", "url": "https://archlinux.org/feeds/packages/all/stable-repos/", "priority": 4, "type": "package"}
  ],
  "extra_patterns": ["\\b(my-special-package)\\b"]
}
```

## ⚠️ Safer Update Checks

The tool prefers `checkupdates` (provided by the `pacman-contrib` package) to check for pending updates safely. If it's not installed, the script falls back to a less robust method and will warn you. Installing `pacman-contrib` is recommended:

```bash
sudo pacman -S pacman-contrib
```

## 📋 Requirements

- 🐧 Arch Linux (or Arch-based distribution)
- 🐍 Python 3.6+
- 📦 pacman package manager
- 🌐 Internet connection for fetching news feeds

## 🔧 Troubleshooting

### "Error getting installed packages"
- Ensure you have proper permissions to run `pacman -Q`
- Check if pacman is installed and in PATH

### "Could not check for pending updates"
- The script needs sudo access to sync package databases
- Ensure you have sudo privileges

### Feed parsing errors
- Check your internet connection
- Try clearing the cache with `--clear-cache`
- Some feeds might be temporarily unavailable

## 🤝 Contributing

Feel free to submit issues, feature requests, or pull requests! Some ideas for improvement:
- 🌐 Additional news sources
- 🧠 Better package name detection
- ⚙️ Configuration file support
- 📧 Email notifications for critical updates

## 📄 License

This project is open source and available under the MIT License.

---

<div align="center">

**Created with ❤️ by [NeatCode Labs](https://neatcodelabs.com)**  
Visit us for more useful tools and projects!

[![Website](https://img.shields.io/badge/Website-neatcodelabs.com-blue?style=for-the-badge)](https://neatcodelabs.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/neatcodelabs)

</div> 
