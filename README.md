# AGY Switch (`ags`)

> **Lightweight multi-account profile manager for Google Antigravity CLI (`agy`) on Linux VPS.**

AGY Switch allows you to run multiple independent Google accounts on a single headless Linux server with isolated OAuth credentials, separate conversation histories, and an interactive numbered menu optimized for Android / Termius mobile SSH.

---

## What AGY Switch Does

Google Antigravity CLI natively stores its authentication tokens and conversation histories under `~/.gemini/antigravity-cli`. Switching accounts manually requires wiping tokens, logging in through browser redirects, and losing conversation context.

**AGY Switch solves this by providing:**
- **Arbitrary Named Profiles**: Manage unlimited named accounts (`personal`, `test`, `work`, `client-a`).
- **Complete Credential & History Isolation**: Each profile gets its own dedicated `HOME`, private SQLite conversation databases, caches, and isolated D-Bus sessions.
- **Session Continuity**: Resume conversations instantly with `ags run <alias> -c` or quick-resume menu shortcuts (`1c`, `2c`).
- **Zero-Loss Renaming**: Rename profiles without losing credentials, conversations, or settings.
- **Mobile-Friendly Numbered Menu**: Renders cleanly on narrow Android/Termius screens (<55 columns) without curses flicker or text wrapping.
- **Zero-Daemon Architecture**: Pure Python 3 standard library. No background daemons, no Docker required, no external databases.

---

## Requirements

- **Operating System**: Linux (Ubuntu 20.04+, Debian 11+, or compatible Linux VPS)
- **Python**: Python 3.8 or higher (standard library only)
- **Google Antigravity CLI**: `agy` installed (in `PATH` or `~/.local/bin/agy`)
- **D-Bus Support (Recommended)**: `dbus-run-session` for session token isolation (`apt-get install -y dbus-x11 dbus-bin`)

---

## Installation

### Simple User-Local Installation (Recommended)

Clone the repository and run the idempotent installer:

```bash
git clone https://github.com/geekammar/agyswitch.git ~/.local/share/agyswitch
cd ~/.local/share/agyswitch
./install.sh
```

The installer links `bin/ags` to `~/.local/bin/ags`.

If `~/.local/bin` is not yet in your `$PATH`, add it to your shell configuration:
```bash
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### System-Wide Installation (Optional for Root Administrators)

```bash
sudo ./install.sh --system
```

This installs `ags` into `/usr/local/bin/ags`.

### Verifying Prerequisites

You can verify prerequisites without making any changes:
```bash
./install.sh --check
```

---

## Quick Start

```bash
# 1. Open the interactive mobile-friendly menu
ags

# 2. Add your first Google account profile
ags add personal

# 3. Authenticate and start using the profile
ags run personal

# 4. Resume your latest conversation in that profile
ags run personal -c
```

---

## Numbered Menu Usage (Mobile SSH / Termius)

Running `ags` without arguments opens the interactive numbered menu:

```text
==================================================
         AGY Switch (ags) - Account Manager
==================================================
 Available Profiles:

  [1] personal
      Google Account: khaledysamo@gmail.com
      Status:         Confirmed Working
      Latest Chat:    "AI Model Identity Inquiry"
      Last Used:      2026-10-15 22:07

  [2] test
      Google Account: adamjsamy@gmail.com
      Status:         Confirmed Working
      Latest Chat:    "General Greeting"
      Last Used:      2026-10-15 22:07

 Actions:
  [1..N] Launch profile (new session)
  [c]    Resume previous conversation (-c)
  [a]    Add a new profile
  [m]    Rename an existing profile
  [d]    Delete / remove a profile
  [q]    Quit menu
--------------------------------------------------
Enter choice (or <num>c to resume) > 
```

### Mobile Shortcuts
- **Launch session**: Type `1` then Enter.
- **Quick Resume**: Type `1c` (or `c1`) then Enter to resume profile 1's conversation directly with `-c`.
- **Continue latest**: Type `c` then Enter to resume your most recently used profile.
- **Add Profile**: Type `a` then Enter.
- **Rename Profile**: Type `m` then Enter.
- **Delete Profile**: Type `d` then Enter.
- **Return to Menu**: After finishing an AGY session, press Enter when prompted to redraw the menu cleanly.

---

## Basic CLI Commands (Scripting & Desktop)

| Command | Description |
|---|---|
| `ags` (or `ags menu`) | Open interactive numbered menu |
| `ags list` (or `ags ls`) | List profiles with identities and auth status |
| `ags list --compact` | Mobile-friendly card view of all profiles |
| `ags add <alias>` | Create a new isolated profile |
| `ags run <alias>` | Start an interactive session for profile |
| `ags run <alias> -c` | Resume the latest conversation for profile |
| `ags run <alias> [args...]` | Forward arguments directly to `agy` (e.g. `--model`) |
| `ags rename <old> <new>` | Rename profile alias (preserves all data) |
| `ags remove <alias>` | Safely remove profile and its isolated directory |
| `ags remove <alias> -f` | Non-interactive removal without confirmation |
| `ags remove <alias> --keep-data` | Unregister profile while keeping data on disk |
| `ags update` | Pull latest application updates from git |
| `ags version` (or `-v`) | Show current AGY Switch version |

---

## Multiple Account Setup

To configure multiple distinct Google accounts:

1. **Add profiles**:
   ```bash
   ags add personal
   ags add work
   ags add testing
   ```

2. **Authenticate each profile independently**:
   ```bash
   ags run personal
   ```
   Follow the Google OAuth URL prompt in your browser, log in with your personal Google account, and complete authentication.

   Then authenticate the second account:
   ```bash
   ags run work
   ```
   Log in with your work Google account.

Both accounts are now permanently authenticated on your VPS and will never overwrite or interfere with each other.

---

## Resuming Conversations

Conversations are saved to each profile's independent SQLite database (`conversation_summaries.db`).

- To resume the latest conversation from the CLI:
  ```bash
  ags run personal -c
  ```
- To resume from the menu:
  Enter `1c` at the main menu prompt, or enter `c` and select the profile.
- To continue a specific conversation by ID:
  ```bash
  ags run personal --conversation <conv-id>
  ```

---

## Updating AGY Switch

Application code is kept completely separate from your profile authentication data and conversation histories (which live in `~/.agyswitch`). Updating the application will **never** delete your accounts or session history.

### Method 1: Using the CLI
```bash
ags update
```

### Method 2: Using the Installer
```bash
cd ~/.local/share/agyswitch
./install.sh --update
```

---

## Moving to Another VPS

To transfer your profiles, Google accounts, and conversation histories to a new Linux server:

1. **On the source server**, archive the profile data directory:
   ```bash
   tar -czvf agyswitch-backup.tar.gz -C "$HOME" .agyswitch
   ```
   > [!WARNING]
   > `agyswitch-backup.tar.gz` contains sensitive Google OAuth tokens. Protect this file and transfer it strictly over encrypted channels (e.g., `scp`, `rsync` over SSH).

2. **On the destination server**, install AGY Switch:
   ```bash
   git clone https://github.com/geekammar/agyswitch.git ~/.local/share/agyswitch
   ~/.local/share/agyswitch/install.sh
   ```

3. **Restore the data archive**:
   ```bash
   tar -xzvf agyswitch-backup.tar.gz -C "$HOME"
   chmod 700 "$HOME/.agyswitch"
   chmod 600 "$HOME/.agyswitch/registry.json"
   ```

4. Verify on the new server:
   ```bash
   ags list
   ```

---

## Security Model & Limitations

AGY Switch MVP is built for a single administrator running personal accounts on a Linux VPS.

### Isolation Scope
- Each profile runs with a dedicated `$HOME`, `$XDG_*` paths, and an isolated transient D-Bus bus.
- Directory permissions are strictly enforced at `0700` and credential files at `0600`.
- Zero tokens or passwords are stored in `registry.json`.

### Limitations
- **Application-State vs. OS-Level Isolation**: When running as root, AGY Switch isolates application data and Google session tokens. It does **not** create an OS-level sandbox. Running AGY as root grants the underlying CLI full root permissions across the host VPS.
- **Untrusted Workloads**: If running untrusted agent prompts or shared multi-user systems, run AGY inside an isolated virtual machine or container.
- **Future Hardening**: Linux UID-per-profile execution (`runuser`) is deferred to a future security-hardening milestone.

---

## Troubleshooting

### Upstream Issue #785 (`VALIDATION_REQUIRED`)
If a profile shows status `Verification Required [!]`:
```text
PERMISSION_DENIED (code 403): VALIDATION_REQUIRED
Eligibility check failed
```
This is a known Google backend eligibility requirement affecting certain Google Workspace or unverified accounts. This is an external Google restriction, not an `ags` issue. Other profiles on your server will continue to work normally.

### Concurrent Session Warning
If you see:
```text
Warning: Profile 'personal' currently has active session(s) (PID: 12345).
Running concurrent sessions on the same profile risks database lock contention.
```
Another terminal or background process is currently running with that profile. To prevent SQLite corruption, close the active session or override with `-f` / `--allow-concurrent`.

### Missing `dbus-run-session`
If D-Bus session isolation is reported unavailable, install it with:
```bash
sudo apt-get update && sudo apt-get install -y dbus-x11 dbus-bin
```

---

## Automated Test Suite

Run the full offline test suite:

```bash
python3 -m unittest discover tests -v
```

All 34 automated unit and integration tests run offline without connecting to external networks or leaking secrets.

---

## License

MIT License. See [LICENSE](LICENSE) for details.