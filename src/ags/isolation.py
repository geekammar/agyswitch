"""Isolation engine for AGY Switch.

Handles:
- Per-profile HOME directory isolation
- D-Bus session isolation via dbus-run-session
- Unprivileged user execution (via runuser/sudo if enabled)
- Workspace accessibility verification
"""

import os
import shutil
import subprocess
from typing import List, Optional, Tuple
from .core import Profile


DEFAULT_AGY_PATHS = [
    os.path.expanduser("~/.local/bin/agy"),
    "/root/.local/bin/agy",
    "/usr/local/bin/agy",
    "/usr/bin/agy"
]


def find_agy_binary(override_path: Optional[str] = None) -> Optional[str]:
    """Locate the shared Antigravity CLI binary."""
    if override_path and os.path.isfile(override_path) and os.access(override_path, os.X_OK):
        return override_path

    env_agy = os.environ.get("AGY_BIN")
    if env_agy and os.path.isfile(env_agy) and os.access(env_agy, os.X_OK):
        return env_agy

    # Check which agy
    which_path = shutil.which("agy")
    if which_path and os.access(which_path, os.X_OK):
        return which_path

    for candidate in DEFAULT_AGY_PATHS:
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate

    return None


def is_dbus_run_session_available() -> bool:
    """Check if dbus-run-session is present on the system."""
    return shutil.which("dbus-run-session") is not None


def check_workspace_traversal(workspace_path: str, target_user: Optional[str] = None) -> Tuple[bool, Optional[str]]:
    """
    Verify whether the target user can traverse and access the workspace path.
    Specifically checks if path is inside a restricted directory (e.g. /root with 0700).
    """
    abs_path = os.path.abspath(workspace_path)
    if not os.path.exists(abs_path):
        return False, f"Workspace path does not exist: {abs_path}"

    # If target_user is unprivileged and path starts with /root
    if target_user and target_user != "root":
        if abs_path == "/root" or abs_path.startswith("/root/"):
            return False, (
                f"Workspace '{abs_path}' is inside '/root' (mode 0700). "
                f"Unprivileged user '{target_user}' cannot traverse into this directory. "
                "Move project to a shared workspace location (e.g. /srv/workspaces or /home/shared) "
                "or adjust workspace permissions."
            )

    return True, None


class IsolationRunner:
    """Constructs and executes isolated AGY commands for a profile."""

    def __init__(self, agy_binary: Optional[str] = None, use_dbus_session: bool = True):
        self.agy_binary = find_agy_binary(agy_binary)
        self.use_dbus_session = use_dbus_session and is_dbus_run_session_available()

    def build_command(
        self,
        profile: Profile,
        extra_args: Optional[List[str]] = None,
        workspace: Optional[str] = None,
        as_unprivileged_user: bool = False
    ) -> Tuple[List[str], dict]:
        """
        Build the command list and environment dictionary for running agy isolated.
        """
        if not self.agy_binary:
            raise FileNotFoundError("Antigravity CLI ('agy') binary could not be found.")

        extra_args = extra_args or []
        env = os.environ.copy()

        # Set profile HOME and XDG variables
        env["HOME"] = profile.home_dir
        env["XDG_CONFIG_HOME"] = os.path.join(profile.home_dir, ".config")
        env["XDG_DATA_HOME"] = os.path.join(profile.home_dir, ".local", "share")
        env["XDG_CACHE_HOME"] = os.path.join(profile.home_dir, ".cache")
        env["XDG_STATE_HOME"] = os.path.join(profile.home_dir, ".local", "state")

        for d in [env["XDG_CONFIG_HOME"], env["XDG_DATA_HOME"], env["XDG_CACHE_HOME"], env["XDG_STATE_HOME"]]:
            os.makedirs(d, mode=0o700, exist_ok=True)

        # Clear inherited session bus so a fresh isolated bus is generated
        env.pop("DBUS_SESSION_BUS_ADDRESS", None)

        # Base execution command
        agy_cmd = [self.agy_binary] + extra_args

        # Wrap in isolated D-Bus session if available
        if self.use_dbus_session:
            exec_cmd = ["dbus-run-session", "--"] + agy_cmd
        else:
            exec_cmd = agy_cmd

        # If running as unprivileged user via system mechanisms
        if as_unprivileged_user and profile.linux_user and os.getuid() == 0:
            # Check workspace accessibility
            target_ws = workspace or os.getcwd()
            accessible, reason = check_workspace_traversal(target_ws, profile.linux_user)
            if not accessible:
                raise PermissionError(reason)

            # Build runuser invocation
            exec_cmd = ["runuser", "-u", profile.linux_user, "--"] + exec_cmd

        return exec_cmd, env

    def run_interactive(
        self,
        profile: Profile,
        extra_args: Optional[List[str]] = None,
        workspace: Optional[str] = None,
        as_unprivileged_user: bool = False
    ) -> int:
        """
        Run AGY interactively with standard I/O attached directly to the user's terminal.
        """
        cwd = workspace or os.getcwd()
        cmd, env = self.build_command(
            profile=profile,
            extra_args=extra_args,
            workspace=cwd,
            as_unprivileged_user=as_unprivileged_user
        )

        return subprocess.call(cmd, env=env, cwd=cwd)
