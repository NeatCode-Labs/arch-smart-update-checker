# Changelog

All notable changes to Arch Smart Update Checker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- pkexec (PolicyKit) integration for privileged operations
- Replace terminal-based sudo operations with graphical authentication

## [2.1.0] - 2025-01-22

### Added
- **Complete GUI Application** - Modern Tkinter interface with multiple views:
  - **Dashboard** - Real-time system overview with update counts, news items, and system info
  - **News Browser** - View and filter Arch news with search capabilities  
  - **Package Manager** - Search, filter, and monitor critical packages
  - **Update History** - Track, view, and export all update history
  - **Settings** - Configure feeds, themes, critical packages, and behavior
- **Advanced CLI Tool** (`asuc-cli`) - Feature-rich command-line interface:
  - Multiple commands: check, updates, news, history, config, clear-cache
  - JSON output support for all commands
  - Automatic pagination for long output
  - Meaningful exit codes for scripting
  - Configuration management via CLI
- **Update History Feature** - Complete update tracking system:
  - Record all updates with timestamps, packages, and results
  - GUI viewer with sorting, filtering, and search
  - Export to JSON/CSV formats
  - Configurable retention period
  - Toggle recording on/off
- **Adaptive Layout System** - Automatic UI scaling:
  - Detects screen size and resolution
  - 11 predefined layouts for common screen sizes
  - Minimum 12.5" diagonal, 1366×768 resolution
  - Proportional scaling for all UI elements
- **Enterprise-Grade Security** - Comprehensive security implementation:
  - Fixed 12 security vulnerabilities (3 critical, 4 high, 4 medium, 1 low)
  - Command injection prevention with whitelisting
  - Path traversal protection with validation
  - Input sanitization for all user inputs
  - Secure subprocess execution (no shell)
  - Memory protection for sensitive data
  - SSL/TLS enforcement for network operations
  - OWASP Top 10 compliance
- **Enhanced Installation** - Smart installer script (`install.sh`):
  - Automatic Arch Linux derivative detection
  - Multiple installation modes (pipx, user, venv, system)
  - Dependency checking and validation
  - PEP 668 compliance for managed environments
  - Colored output with progress information
  - Installation verification
- **TTY Preservation** - See pacman's real progress:
  - Three-tier approach: unbuffer → script → standard
  - Preserves progress bars and animations
  - Works with ILoveCandy and other pacman eye candy
- **Thread Management** - Enterprise-grade threading:
  - Resource limits and monitoring
  - Memory usage tracking
  - Automatic cleanup and leak prevention
  - Component-based thread limits
- **Secure Callbacks** - Memory-safe callback system:
  - Protects sensitive data in callbacks
  - Automatic cleanup on exit
  - Prevents memory leaks
- **Enhanced Validation** - Comprehensive input validation:
  - Package name validation with patterns
  - URL validation with domain checking
  - Path validation with traversal prevention
  - Numeric input validation with ranges
  - Configuration JSON schema validation

### Changed
- **Complete Architecture Rewrite** - From monolithic to modular:
  - Single 833-line script → organized module structure
  - Separation of concerns (checker, config, news, packages, UI, utils)
  - Shared backend between GUI and CLI
  - Type-safe with full annotations
- **License Migration** - MIT → GPL-3.0-or-later:
  - Enhanced user freedoms
  - DCO requirement for contributions
  - Comprehensive migration plan
- **Configuration System** - Enhanced configuration:
  - JSON-based with schema validation
  - GUI settings panel
  - CLI config command
  - More configuration options
- **Performance Improvements**:
  - Concurrent RSS feed fetching
  - Smart caching with TTL
  - Efficient pattern matching
  - Background thread operations
- **User Experience**:
  - Modern UI with themes (light/dark)
  - Better error messages
  - Progress indicators
  - Responsive design

### Fixed
- **Security Vulnerabilities**:
  - Command injection in package operations
  - Path traversal in file operations
  - XML injection in RSS parsing
  - SSRF in URL handling
  - Cache poisoning vulnerabilities
  - Information disclosure in errors
- **Usability Issues**:
  - Gray border flickering in GUI
  - Scrollbar visibility problems
  - Window positioning glitches
  - Double window creation
  - Virtual environment compatibility

### Removed
- **Removed Features**:
  - Standalone `pacman -Sy` (partial upgrade risk)
  - Direct dependency installation from launchers
  - Shell-based command execution
  - Unvalidated user inputs

## [2.0.0] - 2025-07-05

### Added
- **Modular Architecture** - Complete rewrite with proper structure:
  - `src/` directory with logical module separation
  - Proper Python packaging with `pyproject.toml`
  - Type annotations throughout
  - Custom type stubs for external libraries
- **Test Suite** - Comprehensive testing:
  - 62+ unit tests with high coverage
  - Test runner script
  - MyPy type checking
  - Flake8 linting
- **Cross-Distribution Support** - Works on all Arch derivatives:
  - Automatic distribution detection
  - Distribution-specific feed support
  - Fallback mechanisms
- **Multiple Installation Methods**:
  - pipx (isolated environment)
  - pip --user (user installation)
  - Virtual environment
  - System-wide installation
- **Enhanced Features**:
  - Better pattern matching for packages
  - Improved caching with corruption handling
  - Better error messages
  - Colored terminal output
- **Development Tools**:
  - Black code formatting
  - Comprehensive .gitignore
  - Development dependencies

### Changed
- **Core Improvements**:
  - Better code organization
  - Proper exception handling
  - Type safety with MyPy
  - Modern Python practices
- **User Interface**:
  - Enhanced terminal colors
  - Better pagination
  - Clearer output formatting

### Security
- Initial security considerations
- Basic input validation
- Safe subprocess execution

## [1.0] - 2025-06-28 (Legacy Branch)

### Features
- Single-file Python script (833 lines)
- Basic RSS feed checking
- Package matching against news
- Terminal interface with colors
- Simple caching (1 hour)
- Interactive prompts
- Non-interactive mode for scripts
- Configuration file support
- MIT License

### Technical Details
- Uses colorama for terminal colors
- Feedparser for RSS parsing
- Basic pattern matching
- Simple pagination system
- ThreadPoolExecutor for concurrent fetching

---

**Note**: Version 1.0 represents the original monolithic implementation preserved in the `v1.0-legacy` branch. Version 2.0+ represents the complete rewrite with modular architecture, comprehensive testing, and enterprise features. 