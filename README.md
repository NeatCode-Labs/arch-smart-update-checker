# Arch Smart Update Checker

[![Version](https://img.shields.io/badge/version-2.1.0-blue.svg)](https://github.com/neatcodelabs/arch-smart-update-checker)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue.svg)](LICENSE)
[![Security](https://img.shields.io/badge/security-enterprise--grade-green.svg)](docs/Security/SECURITY_EXECUTIVE_SUMMARY.md)
[![Tests](https://img.shields.io/badge/tests-243%20passing-brightgreen.svg)](TEST_REPORT.md)
[![Security Report](https://img.shields.io/badge/security-report-blue.svg)](SECURITY_REPORT.md)

A smart replacement for `sudo pacman -Syu` that checks Arch Linux news feeds and informs you about news related to your installed packages before updating.

**Version 2.1.0** - Complete rewrite with modern GUI, enhanced CLI, enterprise-grade security, and comprehensive features!

## 🌟 What's New in v2.0+

From a simple 833-line script to a full-featured application:

- **🎨 Beautiful GUI Application** - Modern Tkinter interface with dashboard, news browser, package manager, and settings
- **🔧 Advanced CLI Tool** - `asuc-cli` with multiple commands and JSON output support
- **🔒 Enterprise-Grade Security** - 12 security vulnerabilities fixed, comprehensive protection
- **📜 Update History Tracking** - Record, view, and export your update history
- **🖥️ Adaptive Layout** - Automatically scales to different screen sizes (12.5" minimum)
- **🚀 Performance** - Multi-threaded operations, concurrent RSS fetching
- **📦 Multiple Installation Methods** - pipx, pip, virtual environment, or system-wide
- **🎯 Smart Distribution Detection** - Works on all Arch derivatives

## 📸 Screenshots

<p align="center">
  <img src="./screenshots/Screenshot from 2025-07-25 12-32-57.png" alt="Dashboard">
</p>

### GUI Application
- **Dashboard** - Real-time system overview with update status
- **News Browser** - View relevant Arch news and security advisories
- **Package Manager** - Monitor critical packages and available updates
- **Update History** - Track all updates with export capabilities
- **Settings** - Configure feeds, themes, and application behavior

### CLI Tool
```bash
# Check for updates and news (default)
asuc-cli

# List updates only
asuc-cli updates

# View relevant news
asuc-cli news

# Show update history
asuc-cli history

# Manage configuration
asuc-cli config get
asuc-cli config set theme dark
```

## 🚀 Features

### Core Functionality
- **📰 Smart News Filtering** - Only shows news relevant to your installed packages
- **🔍 Package Analysis** - Intelligent pattern matching reduces false positives
- **📡 Multiple RSS Feeds** - Arch news, security advisories, and distribution-specific feeds
- **⚡ Caching** - Intelligent caching reduces network requests
- **🌐 Cross-Distribution** - Works on Arch Linux and all derivatives

### Distribution Support
ASUC automatically detects your Arch derivative and configures appropriate news feeds:

- **Arch Linux** - Base feeds for news and security advisories
- **Manjaro** - Adds Manjaro Stable Updates announcements feed  
- **EndeavourOS** - Adds EndeavourOS News feed
- **Other Derivatives** - Detects Garuda, ArcoLinux, Artix, Parabola, and Hyperbola

Distribution-specific feeds are added alongside Arch Linux's base feeds, ensuring you see both upstream Arch news and distribution-specific announcements. All feeds can be customized in Settings.

### GUI Features
- **Modern Design** - Professional interface with light/dark themes
- **Real-time Updates** - Dashboard shows live system status
- **Thread-Safe** - All operations run in background threads
- **Responsive Layout** - Adapts to different screen sizes
- **TTY Preservation** - See pacman's progress bars and animations

### CLI Features
- **Multiple Commands** - check, updates, news, history, config, clear-cache
- **JSON Output** - Machine-readable output for scripting
- **Pagination** - Automatic pagination for long lists
- **Non-Interactive Mode** - Perfect for scripts and automation
- **Exit Codes** - Meaningful exit codes for scripting

### Security Features
- **Command Injection Prevention** - Secure command generation with validation
- **Path Traversal Protection** - Comprehensive path validation
- **Input Sanitization** - All user inputs validated and sanitized
- **Secure Subprocess Execution** - No shell execution, timeout protection
- **Memory Protection** - Secure handling of sensitive data

## 📦 Installation

### 📋 System Requirements

**Minimum Requirements:**
- **Operating System**: Arch Linux or derivatives only
- **Python**: Version 3.8 or higher
- **Screen Size**: 12.5" diagonal, 1366×768 resolution (GUI only)
- **Dependencies**: python, python-pip, tk (for GUI)

### 🔧 Quick Install (Recommended)

```bash
# Clone the repository
git clone https://github.com/NeatCode-Labs/arch-smart-update-checker.git
cd arch-smart-update-checker

# Run the smart installer
./install.sh
```

The installer will:
- ✅ Verify you're on Arch Linux or derivative
- ✅ Check Python version and dependencies
- ✅ Offer multiple installation methods
- ✅ Install required Python packages
- ✅ Create convenient command shortcuts

### 📚 Installation Methods

| Method | Command | Best For | Location |
|--------|---------|----------|----------|
| **pipx** (Recommended) | `./install.sh` | Most users | `~/.local/pipx/` |
| **pip --user** | `./install.sh --user` | Single user | `~/.local/` |
| **Virtual Environment** | `./install.sh --venv` | Development | `./venv/` |
| **System-wide** | `sudo ./install.sh --system` | All users | `/usr/local/` |

### 🎯 First-Time Setup

1. **Install system dependencies** (if not already installed):
   ```bash
   sudo pacman -S python python-pip tk
   ```

2. **Clone and install**:
   ```bash
   git clone https://github.com/NeatCode-Labs/arch-smart-update-checker.git
   cd arch-smart-update-checker
   ./install.sh
   ```

3. **Run the application**:
   ```bash
   # GUI version
   asuc-gui
   
   # CLI version
   asuc-cli
   ```

## 📖 Usage

### GUI Application

```bash
asuc-gui
```

The GUI provides:
- **Dashboard**: Overview of system status and available updates
- **Quick Actions**: Check updates, view critical packages, refresh news
- **Navigation**: Easy access to all features via sidebar
- **Settings**: Configure feeds, themes, and behavior

### CLI Tool

```bash
# Default: Check for updates and news
asuc-cli

# Show available updates only
asuc-cli updates

# Show relevant news only
asuc-cli news

# View update history
asuc-cli history
asuc-cli history --limit 10
asuc-cli history --export history.csv

# Manage configuration
asuc-cli config get
asuc-cli config set cache_ttl_hours 2
asuc-cli config set theme dark

# Clear caches
asuc-cli clear-cache

# JSON output for scripting
asuc-cli --json
asuc-cli updates --json
```

### Exit Codes

- `0`: Success, no updates available
- `10`: Updates available
- `20`: Error occurred
- `30`: Update failed (when using upgrade command)

## ⚙️ Configuration

Configuration file: `~/.config/arch-smart-update-checker/config.json`

### Key Settings

```json
{
  "cache_ttl_hours": 1,
  "max_news_items": 10,
  "max_news_age_days": 30,
  "theme": "light",
  "update_history_enabled": false,
  "update_history_retention_days": 365,
  "critical_packages": ["linux", "nvidia", "xorg", "systemd"],
  "feeds": [
    {
      "name": "Arch Linux News",
      "url": "https://archlinux.org/feeds/news/",
      "priority": 1
    }
  ]
}
```

### GUI Settings

Access via Settings panel:
- Enable/disable update history
- Change themes (light/dark)
- Configure RSS feeds
- Set critical packages
- Adjust cache settings

### CLI Configuration

```bash
# View all settings
asuc-cli config get

# Change specific setting
asuc-cli config set theme dark
asuc-cli config set update_history_enabled true

# Edit config file directly
asuc-cli config edit
```

## 🗑️ Uninstallation

To completely remove Arch Smart Update Checker and all its data:

### Automated Uninstall

Use the provided uninstall script:

```bash
# Basic uninstall (with confirmation prompt)
./uninstall.sh

# Skip confirmation prompt
./uninstall.sh --force

# Preview what will be removed (dry run)
./uninstall.sh --dry-run

# If you used a custom config location
./uninstall.sh --config /path/to/custom/config.json
```

The uninstall script will remove:
- Configuration directory: `~/.config/arch-smart-update-checker/`
- Cache directory: `~/.cache/arch-smart-update-checker/`
- Update history data
- Custom log files (if configured)
- Systemd user service files
- Desktop entries
- Temporary files

**Note**: The script does NOT remove the executables (`asuc-cli` and `asuc-gui`). To remove them:
- If installed via `install.sh`: Remove the installation directory
- If installed via AUR: Use your package manager (`yay -R arch-smart-update-checker`)

### Manual Uninstall

If you prefer manual removal:

```bash
# Remove configuration and cache
rm -rf ~/.config/arch-smart-update-checker
rm -rf ~/.cache/arch-smart-update-checker

# Remove executables (location depends on installation method)
# For pipx:
pipx uninstall arch-smart-update-checker

# For pip --user:
pip uninstall arch-smart-update-checker

# For system-wide installation:
sudo pip uninstall arch-smart-update-checker

# Remove from virtual environment:
# Simply delete the venv directory
```

## 🔒 Security

This application implements enterprise-grade security:

### Protections
- ✅ **Command Injection Prevention** - All commands validated
- ✅ **Path Traversal Protection** - File access restricted
- ✅ **Input Validation** - Comprehensive sanitization
- ✅ **Secure Subprocess** - No shell execution
- ✅ **Memory Protection** - Sensitive data handling

### Audit Results
- **12 vulnerabilities fixed** (3 critical, 4 high, 4 medium, 1 low)
- **95% risk reduction** achieved
- **OWASP Top 10** compliant
- **Ready for production** use



## 🛠️ Technical Details

### Architecture

The application uses a modular architecture:

```
src/
├── checker.py          # Core update checking logic
├── config.py           # Configuration management
├── news_fetcher.py     # RSS feed handling
├── package_manager.py  # Package operations
├── cli/                # CLI implementation
├── gui/                # GUI implementation
├── utils/              # Shared utilities
└── models.py          # Data models
```

### Key Technologies

- **GUI**: Tkinter with modern theming
- **CLI**: Colorama for colored output
- **Networking**: Requests with SSL verification
- **RSS Parsing**: Feedparser with security hardening
- **Concurrency**: ThreadPoolExecutor for parallel operations
- **Process Management**: Secure subprocess execution

### Performance Features

- **Concurrent RSS Fetching** - All feeds fetched in parallel
- **Smart Caching** - Reduces network requests
- **Thread-Safe Operations** - GUI remains responsive
- **Efficient Pattern Matching** - Optimized package detection
- **Memory Management** - Automatic cleanup and limits

### Testing

Full test suite with 62+ tests:

```bash
# Run all tests
python -m pytest

# With coverage
python -m pytest --cov=src

# Specific test file
python -m pytest tests/test_checker.py
```

## 🆘 Troubleshooting

### Common Issues

**"Command not found: asuc-gui"**
- Run `./install.sh` to create command shortcuts
- Or use: `python -m src.gui_app`

**"Screen size not supported"**
- Minimum 12.5" diagonal, 1366×768 resolution required
- CLI version works on any screen: `asuc-cli`

**"Permission denied"**
- Don't use sudo with pip install
- For system-wide: `sudo ./install.sh --system`

**"No module named 'tkinter'"**
- Install: `sudo pacman -S tk`
- Or use CLI version: `asuc-cli`

### Diagnostics

```bash
# Check installation
./install.sh --check-only

# Verify dependencies
python -c "import tkinter, requests, feedparser, colorama, psutil"

# Test configuration
asuc-cli config path
asuc-cli config get
```

## 📚 Version History

### Current Version (v2.1.0)
The current version is a complete rewrite with modular architecture, GUI, and enterprise features.

### Legacy Version (v1.0)
The original implementation is preserved for historical reference:
- **Browse code**: [v1.0-legacy branch](https://github.com/NeatCode-Labs/arch-smart-update-checker/tree/v1.0-legacy)
- **Download**: [v1.0 release](https://github.com/NeatCode-Labs/arch-smart-update-checker/releases/tag/v1.0)
- **Features**: Single-file script, MIT license, terminal-only

> **Note**: The legacy version is no longer maintained. New users should use the current version.

## 📊 Testing & Security

### Test Suite
- **243 comprehensive tests** covering all major functionality
- Unit tests, integration tests, and security tests
- All tests passing ✅
- View detailed [Test Report](TEST_REPORT.md)

### Security
- Enterprise-grade security implementation
- Comprehensive vulnerability protection
- Regular security audits
- View detailed [Security Report](SECURITY_REPORT.md)

## 🤝 Contributing

Contributions are welcome! Please note:

- All commits must include DCO sign-off: `git commit -s`
- Code must pass security validation
- Tests must pass: `python -m pytest`
- Follow existing code style

See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## 📄 License

This project is licensed under GPL-3.0-or-later. See [LICENSE](LICENSE) for details.


## 🙏 Acknowledgments

- Inspired by [informant](https://github.com/bradford-smith94/informant)
- Thanks to all contributors and testers

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/NeatCode-Labs/arch-smart-update-checker/issues)


---

<div align="center">

**Made with ❤️ for the Arch Linux community**  
Visit us for more useful tools and projects!

[![Website](https://img.shields.io/badge/Website-neatcodelabs.com-blue?style=for-the-badge)](https://neatcodelabs.com)
[![Ko-fi](https://img.shields.io/badge/Ko--fi-Support%20Us-ff5e5b?style=for-the-badge&logo=ko-fi)](https://ko-fi.com/neatcodelabs)

</div> 