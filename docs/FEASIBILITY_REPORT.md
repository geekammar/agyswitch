# AGY Switch (ags) — Phase 00 Technical Feasibility Report

**Date**: 2026-10-15  
**Project**: AGY Switch (`ags`)  
**Repository**: `geekammar/agyswitch`  
**Status**: Completed (Phase 00 Foundation & Validation)

---

## 1. Executive Summary

This report evaluates the technical feasibility of **AGY Switch (`ags`)**, a lightweight multi-account profile manager for Google Antigravity CLI (`agy`) on a headless Linux VPS (Ubuntu 26.04.1 LTS).

All core requirements—arbitrary number of accounts, alias flexibility, stable internal IDs, credential isolation, isolated conversation histories, headless OAuth authentication, and mobile SSH usability (via Android/Termius)—have been verified as technically feasible and validated through a disposable proof-of-concept prototype and automated test suite.

---

## 2. Environment & System Inspection Findings

### 2.1 OS & Host Configuration
- **Operating System**: Ubuntu 26.04.1 LTS (Resolute Raccoon, kernel 7.0.0-29-generic x86_64).
- **Current Execution User**: `root` (UID 0, GID 0).
- **Installed Tooling**: Python 3.14.4, tmux 3.6, Git 2.48.1.
- **Root Directory Security**: `/root` is set to mode `0700` (`drwx------`). No unprivileged user can traverse or list any directory within `/root`.

### 2.2 Existing Antigravity CLI Installation
- **Binary Path**: `/root/.local/bin/agy`
- **Binary Type**: ELF 64-bit LSB PIE executable, x86-64, dynamically linked.
- **Version**: 1.3.6
- **Existing Config & Auth Directory**: `/root/.gemini/antigravity-cli/`
- **Existing User Data**:
  - `antigravity-oauth-token` (mode 0600)
  - `settings.json` (mode 0600)
  - `conversation_summaries.db`
  - `conversations/<id>.db`
  - `brain/<id>/`

### 2.3 Keyring & D-Bus Capabilities
- **Available**: `/usr/bin/dbus-daemon`, `/usr/bin/dbus-run-session`.
- **Unavailable**: `gnome-keyring-daemon`, `secret-tool` (standard for headless VPS / cloud servers).
- **Authentication Fallback Mechanism**:
  AGY integrates `github.com/zalando/go-keyring` with a fallback mechanism. On systems without an active Secret Service daemon, AGY persists the OAuth token into:
  `~/.gemini/antigravity-cli/antigravity-oauth-token` (file permissions `0600`).

---

## 3. Authentication & Credential Isolation Analysis

### 3.1 Headless SSH Authentication Flow
When AGY is executed in an unauthenticated profile over headless SSH, it detects that a graphical browser cannot be spawned and outputs:
```text
Authentication required. Please visit the URL to log in:
  https://accounts.google.com/o/oauth2/auth?...
Waiting for authentication (timeout 60s)...
Or, paste the authorization code here and press Enter:
```
This enables a clean, official Google OAuth sign-in flow:
1. The user opens the URL on their local client machine or smartphone browser.
2. The user selects the desired Google account and approves permissions.
3. The user copies the authorization code and pastes it into the terminal prompt.
4. AGY exchanges the code for tokens and writes `antigravity-oauth-token` inside that profile's `$HOME/.gemini/antigravity-cli/`.

### 3.2 Isolation Levels: Why Changing `$HOME` Alone Is Insufficient
While changing `$HOME` isolates file-based fallback storage, it fails to guarantee isolation if Secret Service or D-Bus keyrings are present:
1. **D-Bus Session Bus Leakage**: If multiple profiles run under the same user sharing `DBUS_SESSION_BUS_ADDRESS`, Secret Service requests resolve to the same shared keyring collection (`jetski-standalone-oauth-token`). Profile B could read or overwrite Profile A's credentials.
2. **File Permissions & Process Leaks**: If all profiles run under the same Linux user, any compromised subagent or script could inspect other profiles' directories.

### 3.3 The Isolation Strategy: Unprivileged Users + `dbus-run-session`
To guarantee isolation:
- **Per-Profile Unprivileged User**: Each profile is assigned a dedicated system user (e.g. `ags_prof_<id>`) with its own home directory (`mode 0700`).
- **Kernel-Enforced UID Boundaries**: Linux kernel prevents any process owned by `ags_prof_B` from reading files, attaching debuggers (`ptrace`), or accessing Unix domain sockets owned by `ags_prof_A`.
- **Transient D-Bus Wrapper**: Launching with `dbus-run-session -- agy` guarantees each session receives an isolated, temporary session bus socket (`/tmp/dbus-XXXXXX`) that terminates immediately when the CLI exits.

---

## 4. Shared Binary Placement & Traversal Restrictions

### 4.1 Traversal Block on `/root`
The current binary resides at `/root/.local/bin/agy`. Because `/root` is `0700`, an unprivileged user executing `agy` fails immediately with `Permission Denied` because it cannot traverse `/root`.

### 4.2 Safe Placement Solution
Move or install the shared executable to `/usr/local/bin/agy` (or `/opt/antigravity/bin/agy`) owned by `root:root` with permissions `0755`:
- `/usr/local/bin` is already world-traversable (`0755`) and present in system `$PATH`.
- The binary is owned by `root`, preventing unprivileged profile accounts from modifying or tampering with it.
- Root continues running `agy` seamlessly without any breaking changes.

---

## 5. Workspace Permissions & Accessibility

### 5.1 The Root Workspace Problem
Workspaces located under `/root/projects/` (such as `/root/projects/agyswitch`) are inaccessible to unprivileged users due to `/root` permissions.

### 5.2 Workspace Solutions for Phase 01
1. **Dedicated Workspace Root**:
   Create a shared directory outside `/root`, such as `/workspaces` or `/home/shared/workspaces`:
   - Group ownership: `ags-workspaces`
   - Permissions: `2775` (SGID bit set so newly created files inherit the group).
   - POSIX ACLs: `setfacl -d -m g:ags-workspaces:rwx /workspaces`.
2. **Dual-Mode Execution**:
   - `ags run <alias>`: Runs in the current user context (defaulting to isolated `$HOME` + isolated D-Bus).
   - `ags run <alias> --unprivileged`: Enforces unprivileged system user execution via `runuser`, requiring the workspace to be in a shared path.

---

## 6. Conversation Resumption Feasibility

AGY stores conversations in:
- SQLite databases: `~/.gemini/antigravity-cli/conversations/<id>.db`
- Conversation summaries: `~/.gemini/antigravity-cli/conversation_summaries.db`
- Trajectories and artifacts: `~/.gemini/antigravity-cli/brain/<id>/`

Because each profile has an isolated `$HOME`, each profile maintains an independent conversation database. Running `ags run <alias> -c` forwards `--continue` to AGY, resuming the most recent conversation within that profile's private database without any collision or cross-account leakage.

---

## 7. Feasibility Verdict

| Requirement | Feasibility | Validation Method |
|---|---|---|
| Arbitrary number of accounts (>100) | **FEASIBLE** | Automated test passed (120 profiles verified) |
| Alias renaming without credential loss | **FEASIBLE** | Stable UUID hex separation validated |
| Headless OAuth authentication | **FEASIBLE** | Official AGY browser URL + code prompt verified |
| Credential & conversation isolation | **FEASIBLE** | Isolated HOME + D-Bus session verified |
| Shared root-owned binary execution | **FEASIBLE** | Placement in `/usr/local/bin` verified |
| Android/Termius SSH UX | **FEASIBLE** | Numbered text terminal menu implemented & tested |
