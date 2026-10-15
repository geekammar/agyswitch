# Changelog

All notable changes to AGY Switch will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-15

### Added
- **Mobile-Optimized Numbered Menu (`ags menu`)**:
  - Compact vertical card layout designed specifically for narrow Android/Termius screens (<55 columns).
  - Quick-resume shortcuts (`1c`, `2c`) to directly continue conversation on a selected profile.
  - Interactive continue option (`c`) with smart defaults pointing to the most recently used profile.
  - Explicit warning prompts and confirmation before launching profiles with Google verification issues (Upstream Issue #785).
  - Graceful interrupt handling for `Ctrl+C` and `EOFError` without tracebacks.
  - Post-session return prompt (`Press Enter to return to menu...`) preventing terminal flooding.
- **Conversation Continuity & Metadata Discovery**:
  - Added `get_latest_conversation` to query profile SQLite conversation databases in read-only mode.
  - Displays conversation titles and IDs in the menu and compact CLI listings.
  - Safe forwarding of `-c` / `--continue` flags to `agy`.
- **Responsive CLI & Commands**:
  - Responsive `ags list`: automatically displays compact card format on narrow terminals (<80 columns) or with `--compact`.
  - Added `ags version` and `-v` / `--version` flags.
  - Added `ags update` command to pull latest git commits while guaranteeing zero interference with profile data.
- **Idempotent Installation & Updater (`install.sh`)**:
  - Minimal user-local installer symlinking `bin/ags` to `~/.local/bin/ags`.
  - Zero required daemons, Docker, or external pip dependencies.
  - Clear separation between repository code and persistent runtime data in `~/.agyswitch`.
  - Prerequisite verification (`./install.sh --check`) for Python 3.8+, `dbus-run-session`, and `agy`.
  - Clean uninstall option (`./install.sh --uninstall`) preserving user credentials and conversation histories.
- **Continuous Integration (`.github/workflows/ci.yml`)**:
  - GitHub Actions workflow testing Python 3.10, 3.11, and 3.12.
  - Offline execution with zero external network dependencies or token leaks.
  - Automated secret and credential leakage scanning step.
- **Documentation**:
  - Comprehensive `README.md` covering architecture, installation, mobile SSH usage, multiple account setup, migration, and troubleshooting.
  - Updated `docs/ARCHITECTURE.md` aligning filesystem paths and security boundaries.

### Fixed
- Fixed wide table wrapping on mobile smartphone terminals in portrait orientation.
- Fixed unclosed SQLite connection handles in metadata discovery.

### Security
- Reaffirmed boundary model: application-state isolation and transient D-Bus sessions.
- Documented single-admin VPS trust model and security guidelines when executing as root.
