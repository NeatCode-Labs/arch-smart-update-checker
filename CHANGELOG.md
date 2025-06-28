# Changelog

All notable changes to this project will be documented in this file. The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2025-06-28
### Added
- Non-interactive mode (`--non-interactive`) for use in scripts/cron; returns exit status 1 when relevant news is found.
- Logging option (`--log FILE`) appends one-line summary to a user-specified file.
- User configuration file support (`~/.config/arch-smart-update-checker/config.json`) with `--init-config` helper.
  * Supports `additional_feeds`, `extra_patterns`, and new `cache_ttl_hours` to control feed-cache duration.
- Concurrent RSS fetching for faster execution using thread pool.
- Safer update detection with `checkupdates` (from `pacman-contrib`) when available.
- Starter `PKGBUILD` stub (for future AUR packaging).
- Default feed list moved into config file; added Arch Security Advisories and stable package update feed with smart filtering.

### Changed
- Removed standalone `pacman -Sy` database sync to eliminate partial-upgrade risk.
- Improved package-name matching to reduce false positives for generic names like "linux" or "systemd."
- README updated with new features, options, and safety notes.
- Setup script now recommends installing `pacman-contrib` and no longer references deprecated `-y` flag.

### Fixed
- Minor messaging tweaks for clarity to less-technical users.

--- 