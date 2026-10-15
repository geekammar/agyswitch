# AGY Switch (`ags`)

Multi-account manager for Google Antigravity CLI (`agy`) on Linux VPS.

---

## Status: Phase 00 Complete (Foundation & Validation)

Phase 00 validates the core architecture, isolation boundaries, metadata registry, official Google OAuth flows, and CLI/menu UX.

### Key Documentation
- [Technical Feasibility Report](file:///root/projects/agyswitch/docs/FEASIBILITY_REPORT.md)
- [MVP Architecture Specification](file:///root/projects/agyswitch/docs/ARCHITECTURE.md)
- [System Changes Requiring Approval](file:///root/projects/agyswitch/docs/SYSTEM_CHANGES_APPROVAL.md)

---

## Running the Automated Tests

The automated test suite runs offline, simulating 100+ accounts without requiring real Google credentials:

```bash
python3 -m unittest discover -s tests -v
```

All tests verify:
- Support for >100 accounts without arbitrary limits
- Unique alias enforcement
- Strict alias sanitization (blocking command injection and path traversal)
- Stable internal profile IDs across renames
- Zero credentials or tokens stored in registry JSON
- Confined filesystem access (0700 permissions)
- Robust handling of missing profiles and invalid operations

---

## Running the Safe Validation Prototype

Run the disposable proof-of-concept validation:

```bash
python3 prototype/validate_poc.py
```

Validates:
- Profile HOME directory isolation
- Independent D-Bus session bus addresses per invocation
- Headless token storage mechanism
- Path accessibility analysis (`/root` vs `/usr/local/bin`)
- Conversation database resumption feasibility

---

## CLI Usage (Prototype Preview)

```bash
# Add a new profile
python3 -m ags.cli add work

# List profiles
python3 -m ags.cli list

# Rename a profile (credentials and history preserved)
python3 -m ags.cli rename work company

# Launch interactive numbered menu (optimized for Android/Termius)
python3 -m ags.cli menu

# Run a profile
python3 -m ags.cli run company

# Continue most recent conversation
python3 -m ags.cli run company -c

# Remove a profile
python3 -m ags.cli remove company -f
```