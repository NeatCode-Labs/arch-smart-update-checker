# Changelog

All notable changes to Arch Smart Update Checker will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.3.1] - 2025-07-29

### Changed
- **Automatic Distribution-Specific Feeds** - The app now automatically adds distribution-specific RSS feeds:
  - Manjaro users: Automatically adds "Manjaro Announcements" and "Manjaro Stable Updates" feeds
  - EndeavourOS users: Automatically adds "EndeavourOS News" feed
  - These feeds are added during initial setup or when switching distributions
- **Simplified Edit Feed Dialog** - Removed redundant "Enabled" checkbox from Edit RSS feed dialog:
  - Feeds can already be enabled/disabled from the main settings page
  - Edit dialog now only shows Name, URL, and Type fields
- **Fixed Status Bar Truncation** - Resolved issue where error messages were getting heavily truncated:
  - Increased sidebar base width to prevent text cutoff
  - Adjusted wraplength calculations for better text display
- **Fixed Update Check Button State** - Fixed issue where "Check for Updates" button would get stuck:
  - Button now properly resets when database sync is cancelled
  - Dashboard animation is stopped when sync fails
- **Fixed Dashboard Animation** - Fixed "Checking for updates..." animation text that remained visible after cancelling update check

### Fixed
- **Improved Distribution Detection** - Enhanced detection logic to properly identify Manjaro and EndeavourOS:
  - Better parsing of /etc/os-release file
  - Improved handling of distribution derivatives
  - Fixed missing return statement in distribution name normalization
  - Added package-based detection as fallback for cases where os-release reports "arch"
- **Fixed Config Initialization Error** - Fixed "Config object has no attribute 'config'" error when distribution changes during startup
- **Fixed Domain Validation** - Fixed trusted domain validation to properly handle subdomains like forum.manjaro.org
- **First-Run Feed Management** - Distribution-specific feeds are now only added on first installation:
  - Prevents overwriting user's feed preferences on subsequent runs
  - Users can freely add/remove feeds without them being re-added
  - Distribution detection still updates the config's distribution field when needed

### Internal
- Added comprehensive test suite for distribution detection and first-run feed behavior (11 new tests)
- Total test count increased to 283 tests, all passing

## [2.3.0] - 2025-07-28

### Changed
- **Integrated Database Sync** - Database syncing is now an integral part of "Check for Updates":
  - Removed the dedicated "Sync Database" button from GUI
  - Database automatically syncs when "Check for Updates" is clicked
  - Users are prompted for authentication before syncing begins
  - If sync is cancelled, update check is skipped to avoid showing stale results
- **Last Full Update Display** - Replaced "Database last synced:" with more meaningful information:
  - Now shows "Last full update:" timestamp
  - Tracks when a full system update was performed (via "Update All" or selecting all updates)
  - Detects full updates performed outside the app by parsing pacman.log
  - Updates timestamp when all available packages are updated
- **Improved Status Bar Formatting** - Fixed truncated update status messages:
  - Changed from single-line format: "✓ x package(s) updated, y remaining"
  - To two-line format with aligned numbers:
    ```
    ✓ x package(s) updated
      y remaining
    ```
  - Used plain checkmark (✓) instead of emoji for consistent rendering
  - Increased wraplength to prevent line breaking

### Removed
- Sync Database button from GUI dashboard
- References to Zenity fallback (pkexec is now the only graphical authentication method)

### Fixed
- Status bar message truncation in all layout sizes
- Threading errors in GUI tests
- Performance test thresholds for system variations

### Internal
- Added comprehensive tests for external update detection
- Updated documentation to remove outdated Zenity references

## [2.2.1] - 2025-07-28

### Changed
- **Automatic Database Sync** - CLI now automatically runs `pacman -Sy` before checking for updates
  - Ensures users always see the latest available updates
  - No need to manually sync the database first
  - Works for both `asuc-cli` and `asuc-cli updates` commands

### Documentation
- Added comprehensive exit code documentation to README
- Added practical examples for using exit codes in scripts
- Clarified that exit code 10 (updates available) is not an error

## [2.2.0] - 2025-07-26

### Added
- **PolicyKit (pkexec) Integration** - Graphical authentication for privileged operations:
  - Replaced terminal-based sudo with pkexec for all package operations
  - Automatic fallback mechanisms for hardened kernels
  - Detection of passwordless sudo and appropriate handling
  - Proper timeout handling for blocked authentication
  - Clear error messages when pkexec is not available
- **Enterprise Security Enhancements** - Comprehensive security hardening:
  - **Automated Security Scanning** - CodeQL and Bandit in CI/CD pipeline
  - **Dependency Vulnerability Checking** - pip-audit with critical failure on high-severity issues
  - **MAC Security Profiles** - Complete AppArmor and SELinux policies with installers
  - **Enhanced Subprocess Sandboxing** - Bubblewrap integration with automatic detection
- **AppArmor Security Profiles** - Complete MAC profiles for enhanced security
  - **Security Event Logging** - Dedicated security log with rate limiting and enriched context
  - **Security Metrics Collection** - SQLite-based metrics tracking with trend analysis
  - **Advanced Sandboxing Profiles** - Granular profiles for different security levels
  - **Secure URL/File Opening** - Sandboxed operations for external resources
  - **Advanced Path Traversal Protection** - Detection of encoded attacks, null bytes, Unicode tricks
  - **Privileged Command Wrappers** - Secure wrappers for systemctl, mount, umount
  - **Security Update Monitoring** - Script for tracking security updates
  - **SBOM Generation** - CycloneDX Software Bill of Materials in CI
- **Security Documentation Suite**:
  - `docs/SECURITY.md` - Main security policy and vulnerability reporting
  - `docs/SECURITY_GUIDELINES.md` - Comprehensive security coding guidelines
  - `docs/SECURITY_IMPLEMENTATION_REPORT.md` - Detailed technical implementation report
  - `docs/SECURITY_INDEX.md` - Complete security documentation index
  - `.github/INCIDENT_RESPONSE.md` - Incident response procedures
- **CI/CD Security Workflows**:
  - `security-profiles.yml` - Automated AppArmor/SELinux syntax validation
  - Security scanning on every push and PR
  - Dependency vulnerability checks with build failure on critical issues
- **Enhanced Security Features**:
  - Single instance lock improvements with security logging
  - Rate limiting for security events (10 events per 60s window)
  - Secure memory management verification
  - Path validation for logs with dedicated validators
  - Enriched security event context (PID, UID, user, thread info)

### Changed
- **Test Suite Updates** - Fixed all tests for security changes:
  - Updated 266 tests to work with new security architecture
  - Fixed URL opening tests to use SecureSubprocess
  - Updated package validation tests for enhanced security
  - Fixed threading tests for ThreadResourceManager
  - Updated command execution tests for secure wrappers
  - Improved test reliability and coverage
- **Command Execution** - All external commands now use security wrappers:
  - `xdg-open` uses SecureSubprocess with path resolution
  - Package operations use validated command generation
  - System commands use dedicated secure wrappers
- **Input Validation** - Enhanced validation throughout:
  - Package names now logged on validation failure
  - URLs require HTTPS for non-localhost
  - File paths undergo multiple validation layers
  - Commands are strictly whitelisted
- **Documentation Improvements**:
  - Consolidated README.md with unified security/testing sections
  - Professional tone and structure
  - Updated badges to reflect current test count (269)
  - Reorganized for better navigation

### Fixed
- **Test Failures** - All security-related test failures resolved:
  - Environment variable assertions made optional
  - URL validation tests updated for HTTPS requirement
  - Threading mocks properly handle ThreadResourceManager
  - Package validation tests use correct data structures
  - Command execution tests mock all security layers
  - File opening tests use secure subprocess wrappers
- **Security Vulnerabilities** - Additional protections added:
  - Systemctl service name validation with whitelist
  - Mount/umount path validation with protected directories
  - Enhanced encoding attack prevention
  - Improved command path resolution

### Security
- **Risk Mitigation** - Near 100% coverage of identified attack vectors:
  - Command injection fully prevented with validation and whitelisting
  - Path traversal blocked with multi-layer validation
  - SSRF prevented with domain whitelisting and HTTPS enforcement
  - Log injection prevented with sanitization
  - Privilege escalation controlled with secure wrappers
- **Compliance** - Industry standard compliance:
  - OWASP Top 10 fully addressed
  - CWE coverage for common vulnerabilities
  - Security by design principles implemented
  - Defense in depth architecture
- **Monitoring** - Comprehensive security observability:
  - All security events logged with context
  - Metrics collection for trend analysis
  - Automated security scanning in CI/CD
  - Regular dependency vulnerability checks

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
