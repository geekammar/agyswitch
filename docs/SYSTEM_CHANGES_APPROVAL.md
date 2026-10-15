# AGY Switch (ags) — System Changes Requiring Approval for Phase 01

In accordance with strict safety rules, **NO system changes have been made during Phase 00**. All Phase 00 prototypes, inspections, and automated tests executed inside isolated disposable temporary directories.

The following operations are identified as necessary or recommended for full Phase 01 deployment and require explicit user approval prior to execution:

---

## 1. Shared Antigravity CLI Binary Relocation

- **Current Location**: `/root/.local/bin/agy` (inaccessible to non-root users because `/root` is `0700`).
- **Proposed Change**: Copy or symlink the binary to `/usr/local/bin/agy` owned by `root:root` with mode `0755`.
- **Command**:
  ```bash
  cp -p /root/.local/bin/agy /usr/local/bin/agy
  chmod 0755 /usr/local/bin/agy
  ```
- **Safety Impact**: Fully safe and non-destructive. Preserves root's original binary and settings, while making the CLI accessible to all execution contexts.

---

## 2. Global `ags` Wrapper Link

- **Proposed Change**: Install or symlink `ags` into `/usr/local/bin/ags` so that running `ags` works from any terminal.
- **Command**:
  ```bash
  ln -s /root/projects/agyswitch/src/ags/cli.py /usr/local/bin/ags
  chmod +x /usr/local/bin/ags
  ```
- **Safety Impact**: Minimal. Allows running `ags` globally.

---

## 3. Base Directory Creation

- **Proposed Path**: `/var/lib/agyswitch`
- **Ownership**: `root:root`
- **Mode**: `0755` (with subdirectories `profiles/` at `0700`)
- **Command**:
  ```bash
  mkdir -p /var/lib/agyswitch/profiles
  chmod 0755 /var/lib/agyswitch
  chmod 0700 /var/lib/agyswitch/profiles
  ```

---

## 4. Unprivileged System User Policy (If Strict UID Separation Is Enabled)

If the user chooses strict unprivileged Linux user isolation rather than isolated-HOME isolation:
- **System Users**: Created with `useradd --system --no-create-home --home-dir /var/lib/agyswitch/profiles/<id> --shell /usr/sbin/nologin ags_<id>`
- **Approval Check**: This requires explicit consent before creating system users on the host.

---

## 5. Shared Workspace Directory (If Unprivileged User Execution Is Used)

- **Proposed Path**: `/workspaces` (outside `/root`)
- **Permissions**: Group `ags-workspaces`, SGID `2775`, default ACLs.
- **Approval Check**: Required if projects need to be accessed by non-root users.
