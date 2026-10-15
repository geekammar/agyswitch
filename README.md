# AGY Switch (`ags`)

Multi-account manager for Google Antigravity CLI (`agy`) on Linux VPS.

---

## Status: Phase 01 Complete (Core Account Manager & Dual Real-Account Acceptance)

Phase 01 delivers full multi-account isolation, CLI and numbered terminal menu interfaces, safe argument forwarding, process lifecycle protection, and validated dual-account real-world operation on Linux.

### Key Documentation
- [MVP Architecture Specification](file:///root/projects/agyswitch/docs/ARCHITECTURE.md)
- [Open Source Evaluation & Upstream Issue #785](file:///root/projects/agyswitch/docs/OPEN_SOURCE_EVALUATION.md)
- [Technical Feasibility Report](file:///root/projects/agyswitch/docs/FEASIBILITY_REPORT.md)
- [System Changes Requiring Approval](file:///root/projects/agyswitch/docs/SYSTEM_CHANGES_APPROVAL.md)

---

## Real CLI Commands

`ags` is installed globally in your `PATH` (e.g. `/root/.local/bin/ags` or `/usr/local/bin/ags`).

```bash
# Launch the interactive numbered terminal menu (default when no args provided)
ags

# List all configured profiles, mapped accounts, and auth statuses
ags list

# Add a new profile
ags add personal
ags add test

# Launch an AGY session for a profile
ags run personal

# Continue the most recent conversation in this profile
ags run personal -c

# Pass additional AGY flags (e.g. model selection, agent mode)
ags run personal --model "Gemini 3.8 Flash (High)"

# Override concurrent session protection if a session is already active
ags run personal -f
ags run personal --allow-concurrent

# Rename a profile alias (profile ID, credentials, and conversations remain intact)
ags rename test secondary

# Remove a profile (with interactive confirmation, active session detection)
ags remove secondary

# Force remove a profile (non-interactive)
ags remove secondary -f

# Remove profile from registry but preserve data on disk
ags remove secondary --keep-data
```

---

## Authentication Status Reporting

`ags list` provides clear visibility into profile states without exposing tokens or secrets:

- **Confirmed Working**: The profile has an active stored token and a verified successful session communicating with Google's backend.
- **Credentials Stored**: The profile has stored credentials, but has not yet executed a live backend session.
- **Verification Required [!]**: Stored credentials exist, but Google's backend returned a 403 `VALIDATION_REQUIRED` error (see [Upstream Issue #785](#known-external-limitation-google-eligibility--upstream-issue-785)).
- **Not Authenticated**: No local credentials exist yet; run `ags run <alias>` to sign in.

---

## Security Model & Isolation Boundaries

### Application-State Isolation vs. OS UID Boundary
The isolation implemented in Phase 01 isolates:
- Dedicated **`$HOME`** directory per profile (`~/.agyswitch/profiles/<prof_id>/`)
- Isolated **`XDG_CONFIG_HOME`**, **`XDG_DATA_HOME`**, **`XDG_CACHE_HOME`**, and **`XDG_STATE_HOME`**
- Private transient **D-Bus session bus** via `dbus-run-session`
- Strictly enforced permissions: **`0700`** on profile directories and **`0600`** on registry and token files
- Zero secrets stored in `registry.json`

> [!IMPORTANT]
> **Application-State Isolation Note**:  
> In Phase 01, when running as root without unprivileged system users enabled, isolation operates at the **application-state and credential-storage level**. It cleanly separates Google OAuth tokens, conversation databases, and application caches. It is **not** a complete OS-level security boundary against hostile code running under the same root Linux UID. Dedicated unprivileged Linux user isolation (`runuser` / non-root) is architected for Phase 02.

---

## Concurrent Session Safeguards

Antigravity CLI uses SQLite databases (`conversation_summaries.db`, `conversations/<id>.db`) and presence lockfiles (`presence/<id>.lock`). Running multiple concurrent AGY processes under the same profile can lead to:
- SQLite lock contention (`sqlite3.OperationalError: database is locked`)
- State and conversation summary desynchronization
- Token refresh race conditions

**`ags` Safeguard**:
`ags run` detects running sessions associated with the target profile.
- In interactive terminals: prompts the user with a warning before launching a concurrent session.
- In automated/non-interactive scripts: blocks execution with an error unless `-f`, `--force`, or `--allow-concurrent` is explicitly provided.

---

## Known External Limitation: Google Eligibility & Upstream Issue #785

During real-world validation, certain Google accounts may encounter:
```text
PERMISSION_DENIED (code 403): VALIDATION_REQUIRED
Eligibility check failed
```
This is a documented upstream limitation in Google's Cloud Code / Antigravity backend (Upstream Issue #785) affecting specific Google Workspace or unverified consumer accounts.

- This is an **external Google account eligibility issue**, not an `ags` software defect.
- `ags` detects and reports this status (`Verification Required [!]`) without crashing.
- Other valid profiles (e.g. `personal`, `test`) remain fully operational and completely unaffected.

---

## Android / Termius Optimization Guide

`ags` is optimized for mobile SSH clients (Termius, JuiceSSH, ConnectBot) and desktop terminals:
- **No Curses Flicker**: The menu uses linear scrolling rather than full-screen curses libraries, preventing rendering artifacts on high-latency mobile networks.
- **Single-Key Navigation**: Launch profiles with direct number keys (`1`, `2`, `3`), or quick commands (`c` to continue, `a` to add, `m` to rename, `d` to delete, `q` to quit).
- **Tmux Integration**: When managing long-running agent tasks on mobile, run `tmux` first, then run `ags`. Reconnecting from Termius allows seamless resumption without interrupting the agent.

---

## Automated Test Suite

Run the complete automated test suite offline without requiring live Google accounts:

```bash
python3 -m unittest discover tests -v
```

All 24 automated tests verify:
- Support for >100 accounts without arbitrary limits (tested at 125 profiles)
- Unique alias enforcement & strict sanitization
- Stable internal profile IDs across renames
- Zero credentials or tokens stored in registry JSON
- Directory (0700) and file (0600) permission enforcement
- No cross-profile state or conversation contamination
- Original root AGY state preservation
- Safe argument forwarding & shell injection resistance
- Safe profile deletion and active session protection
- Resilience against interrupted registry writes
- OIDC public email discovery
- Known Google backend eligibility warning detection
- Auth summary distinctions (unauthenticated, stored, confirmed working, blocked)
- Concurrent session safeguards
- Conversation SQLite database isolation
- Full restart persistence across process lifecycles