# Arch Smart Update Checker

[![Version](https://img.shields.io/badge/version-2.3.1-blue.svg)](https://github.com/neatcodelabs/arch-smart-update-checker)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![AUR](https://img.shields.io/aur/version/arch-smart-update-checker?color=1793d1&label=AUR&logo=arch-linux)](https://aur.archlinux.org/packages/arch-smart-update-checker)
[![Security](https://img.shields.io/badge/security-enterprise--grade-green.svg)](docs/SECURITY.md)
[![Tests](https://img.shields.io/badge/tests-283%20passing-brightgreen.svg)](docs/TEST_REPORT.md)

> **⚠️ NOTICE**: This is **100% AI-generated software** (with human supervision). Please read the [DISCLAIMER](docs/DISCLAIMER.md) before use.

ASUC is a replacement tool for `sudo pacman -Syu` that checks Arch Linux news feeds and informs you about news related to your installed packages before updating.

## 🌟 Overview

Arch Smart Update Checker (ASUC) is an enterprise-grade update management tool for Arch Linux and its derivatives. It intelligently filters Arch news and security advisories to show only what's relevant to your system, preventing update-related breakage and improving system stability.

### Key Features

- **🎨 Modern GUI & CLI** - Choose between a beautiful Tkinter interface or powerful command-line tool
- **📰 Smart News Filtering** - Shows only news relevant to your installed packages
- **🔒 Enterprise Security** - Comprehensive protection with AppArmor/SELinux profiles
- **📜 Update History** - Complete audit trail of all system updates
- **🌐 Multi-Distribution** - Automatic detection and support for all Arch derivatives
- **⚡ High Performance** - Multi-threaded operations with intelligent caching

## 📸 Screenshots

<p align="center">
  <img src="./screenshots/Screenshot from 2025-07-25 12-32-57.png" alt="Dashboard">
</p>

## 🚀 Quick Start

### System Requirements

- **OS**: Arch Linux or derivatives (Manjaro, EndeavourOS, etc.)
- **Python**: 3.8 or higher
- **Display**: 1366×768 minimum (GUI only)

### Installation

#### 📦 AUR Package (Recommended)

```bash
# Using yay
yay -S arch-smart-update-checker

# Using paru  
paru -S arch-smart-update-checker

# Manual AUR installation
git clone https://aur.archlinux.org/arch-smart-update-checker.git
cd arch-smart-update-checker
makepkg -si
```

#### 🔧 From Source

```bash
# Clone the repository
git clone https://github.com/NeatCode-Labs/arch-smart-update-checker.git
cd arch-smart-update-checker

# Run the smart installer
./install.sh
```

### Basic Usage

```bash
# GUI Application
asuc-gui

# CLI Tool
asuc-cli                    # Check updates and news
asuc-cli updates            # List available updates
asuc-cli news               # Show relevant news
asuc-cli history            # View update history
```

## 📖 Documentation

- [How ASUC Works (Technical Overview)](docs/HOW_ASUC_WORKS.md): A detailed technical explanation of the app's architecture, update flow, and security model for advanced users and contributors.

### User Guide

#### GUI Application
The GUI provides an intuitive interface with:
- **Dashboard**: Real-time system status and update overview
- **News Browser**: Filtered Arch news and security advisories
- **Package Manager**: Monitor critical packages and updates
- **Update History**: Complete audit trail with export capabilities
- **Settings**: Configure feeds, themes, and behavior

#### CLI Tool
Comprehensive command-line interface:
```bash
# Check for updates with news (default)
# Note: Automatically syncs package database (sudo pacman -Sy) before checking
asuc-cli

# List updates only
# Note: Also syncs database automatically
asuc-cli updates [--json]

# Show relevant news
asuc-cli news [--all] [--json]

# View update history
asuc-cli history [--limit N] [--export FILE]

# Manage configuration
asuc-cli config get [KEY]
asuc-cli config set KEY VALUE
asuc-cli config edit

# Clear caches
asuc-cli clear-cache
```

#### Exit Codes
- `0`: Success - Command completed successfully, no updates available
- `10`: Success - Command completed successfully, updates are available (NOT an error)
- `2`: Error - Invalid command line arguments or syntax
- `20`: Error - General error (network issues, parsing failures, etc.)
- `30`: Error - Package upgrade failed
- `130`: Interrupted - User pressed Ctrl+C

**Note**: Exit code 10 is NOT an error! It's an informational code indicating that updates were found.

##### Using Exit Codes in Scripts
```bash
#!/bin/bash
asuc-cli --quiet
case $? in
    0)  echo "System is up to date" ;;
    10) echo "Updates available - consider upgrading" ;;
    2)  echo "Command syntax error" ;;
    20) echo "Error occurred during check" ;;
    30) echo "Update failed" ;;
    130) echo "Operation cancelled by user" ;;
esac
```

### Configuration

Configuration is stored in `~/.config/arch-smart-update-checker/config.json`

Key settings:
- `cache_ttl_hours`: Cache lifetime (default: 1)
- `max_news_age_days`: Maximum age for news items (default: 30)
- `theme`: Application theme (light/dark)
- `update_history_enabled`: Enable update tracking
- `critical_packages`: Packages to monitor closely
- `feeds`: RSS feed configuration

### Distribution Support

ASUC automatically detects and configures feeds for:
- **Arch Linux** - Official news and security advisories
- **Manjaro** - Stable update announcements  
- **EndeavourOS** - Distribution news
- **Garuda, ArcoLinux, Artix** - Distribution-specific feeds
- **Other derivatives** - Automatic detection

**First Run Behavior:**
- Distribution-specific RSS feeds are automatically added on first installation
- For Manjaro: Both "Manjaro Announcements" and "Manjaro Stable Updates" feeds
- For EndeavourOS: "EndeavourOS News" feed  
- These feeds are only added once - subsequent runs respect your feed preferences
- You can freely add/remove feeds without them being re-added

## 🔒 Security & Testing

### Security Features

ASUC implements enterprise-grade security with multiple layers of protection:

#### Core Security
- **Input Validation** - All user inputs sanitized and validated
- **Command Injection Prevention** - Secure command generation with validation
- **Path Traversal Protection** - Comprehensive file system access controls
- **Secure Subprocess Execution** - No shell execution, timeout protection
- **Memory Protection** - Secure handling and clearing of sensitive data

#### Advanced Security
- **MAC Profiles** - AppArmor and SELinux policies included
- **Sandboxing** - Bubblewrap integration for isolation
- **AppArmor Support** - Comprehensive security profiles available
- **Security Logging** - Complete audit trail of security events
- **Single Instance Lock** - Prevents concurrent execution
- **HTTPS Enforcement** - Secure communication for all feeds

#### Security Documentation
- [Security Overview](docs/SECURITY.md) - Main security policy
- [Security Index](docs/SECURITY_INDEX.md) - Complete security documentation guide
- [Implementation Report](docs/SECURITY_IMPLEMENTATION_REPORT.md) - Technical details
- [Security Guidelines](docs/SECURITY_GUIDELINES.md) - For contributors
- [All Security Measures](docs/ALL_SECURITY_MEASURES.md) - Comprehensive, versioned list of all active security measures

### Testing

Comprehensive test suite with 283 tests ensuring reliability:

```bash
# Run all tests
python -m pytest

# Run with coverage report
python -m pytest --cov=src --cov-report=html

# Run specific test categories
python -m pytest tests/test_security.py    # Security tests
python -m pytest tests/test_gui.py         # GUI tests
python -m pytest tests/test_cli.py         # CLI tests
```

Test coverage includes:
- ✅ Unit tests for all core functionality
- ✅ Integration tests for package operations
- ✅ Security tests for vulnerability protection
- ✅ Performance tests for optimization
- ✅ GUI tests for user interface

View the detailed [Test Report](docs/TEST_REPORT.md) for comprehensive results.

## 🛠️ Technical Architecture

### Project Structure
```
arch-smart-update-checker/
├── src/                    # Source code
│   ├── checker.py         # Core update logic
│   ├── cli/               # CLI implementation
│   ├── gui/               # GUI implementation
│   └── utils/             # Shared utilities
├── tests/                  # Test suite
├── security/               # MAC profiles
│   ├── apparmor/          # AppArmor profile
│   └── selinux/           # SELinux policy
└── docs/                   # Documentation
```

### Technology Stack
- **GUI**: Tkinter with modern theming
- **CLI**: Colorama for enhanced output
- **Networking**: Requests with SSL verification
- **RSS**: Feedparser with security hardening
- **Concurrency**: ThreadPoolExecutor
- **Testing**: Pytest with comprehensive coverage

### Performance Optimizations
- Concurrent RSS feed fetching
- Intelligent caching system
- Thread-safe GUI operations
- Optimized pattern matching
- Automatic memory management

## 🗑️ Uninstallation

### AUR Package

```bash
# Uninstall package
yay -Rns arch-smart-update-checker
# or
paru -Rns arch-smart-update-checker

# Cleanup instructions will be displayed after removal
# To remove all user data (optional):
rm -rf ~/.config/arch-smart-update-checker ~/.cache/arch-smart-update-checker
```

### Source Installation

Complete removal with the uninstall script:

```bash
# Standard uninstall
./uninstall.sh

# Skip confirmation
./uninstall.sh --force

# Preview what will be removed
./uninstall.sh --dry-run
```

## 🤝 Contributing

We welcome contributions! Please ensure:

1. All commits include DCO sign-off: `git commit -s`
2. Code passes security validation
3. Tests pass: `python -m pytest`
4. Follow existing code style

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

## 📄 License

Licensed under GPL-3.0-or-later. See [LICENSE](LICENSE) for details.

## 🙏 Acknowledgments

- Inspired by [informant](https://github.com/bradford-smith94/informant)
- Built for the Arch Linux community
- Thanks to all contributors and testers

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/NeatCode-Labs/arch-smart-update-checker/issues)
- **Security**: See [SECURITY.md](docs/SECURITY.md) for vulnerability reporting

---

<div align="center">

**Made with ❤️ for the Arch Linux community**

[![Website](https://img.shields.io/badge/Website-neatcodelabs.com-blue?style=for-the-badge)](https://neatcodelabs.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/neatcodelabs)

</div> 
