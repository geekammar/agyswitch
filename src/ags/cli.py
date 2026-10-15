"""Command Line Interface for AGY Switch (ags)."""

import os
import sys
import shutil
import argparse
import subprocess
from typing import List, Optional
from . import __version__
from .core import (
    ProfileRegistry,
    InvalidAliasError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    RegistryError
)
from .isolation import IsolationRunner
from .menu import TerminalMenu


DEFAULT_BASE_DIR = os.environ.get("AGS_HOME", os.path.expanduser("~/.agyswitch"))


def get_registry(base_dir: Optional[str] = None) -> ProfileRegistry:
    target_dir = base_dir or DEFAULT_BASE_DIR
    return ProfileRegistry(base_dir=target_dir)


def cmd_version(args, registry: ProfileRegistry):
    print(f"AGY Switch (ags) v{__version__}")
    return 0


def cmd_list(args, registry: ProfileRegistry):
    profiles = registry.list_profiles()
    if not profiles:
        print("No profiles configured yet. Add one using: ags add <alias>")
        return 0

    cols = shutil.get_terminal_size(fallback=(100, 24)).columns
    compact = getattr(args, "compact", False) or cols < 80

    if compact:
        print("Available Profiles:")
        print("-" * min(cols, 60))
        for p in profiles:
            summary = registry.get_auth_summary(p)
            account = summary["account"] or "(none)"
            status_display = summary["status"]
            last_used = p.last_used_at[:16].replace("T", " ") if p.last_used_at else "Never"
            latest_conv = registry.get_latest_conversation(p)
            print(f"• {p.alias}")
            print(f"    Account:   {account}")
            print(f"    Status:    {status_display}")
            if latest_conv:
                print(f"    Latest:    \"{latest_conv['title']}\"")
            if summary.get("eligibility_warning"):
                print(f"    Notice:    {summary['eligibility_warning']}")
            print(f"    Last Used: {last_used}")
            print()
        return 0

    print(f"{'ALIAS':<16} {'PROFILE ID':<20} {'ACCOUNT':<28} {'AUTH STATUS':<26} {'LAST USED':<18}")
    print("-" * 110)
    warnings = []
    for p in profiles:
        summary = registry.get_auth_summary(p)
        account = summary["account"] or "(none)"
        status_display = summary["status"]
        if summary["eligibility_warning"]:
            warnings.append((p.alias, summary["eligibility_warning"]))
        last_used = p.last_used_at[:16].replace("T", " ") if p.last_used_at else "Never"
        print(f"{p.alias:<16} {p.id:<20} {account:<28} {status_display:<26} {last_used:<18}")

    if warnings:
        print("\nAccount Notices:")
        for alias, warn in warnings:
            print(f"  [!] {alias}: {warn}")
    return 0


def cmd_add(args, registry: ProfileRegistry):
    try:
        profile = registry.add_profile(args.alias)
        summary = registry.get_auth_summary(profile)
        print(f"Profile '{profile.alias}' successfully added.")
        print(f"  Profile ID: {profile.id}")
        print(f"  Home Path:  {profile.home_dir}")
        print(f"  Status:     {summary['status']}")
        print(f"\nTo authenticate this profile, run:\n  ags run {profile.alias}")
        return 0
    except (InvalidAliasError, ProfileAlreadyExistsError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_rename(args, registry: ProfileRegistry):
    try:
        profile = registry.rename_profile(args.old_alias, args.new_alias)
        print(f"Profile renamed: '{args.old_alias}' -> '{profile.alias}'")
        print(f"  Profile ID: {profile.id} (unchanged)")
        print(f"  Home Path:  {profile.home_dir} (unchanged)")
        print("All credentials, history, and conversations remain intact.")
        return 0
    except (ProfileNotFoundError, InvalidAliasError, ProfileAlreadyExistsError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_remove(args, registry: ProfileRegistry):
    try:
        profile = registry.get_by_alias(args.alias)
        if not profile:
            print(f"Error: Profile '{args.alias}' not found.", file=sys.stderr)
            return 1

        active_pids = registry.get_active_sessions(profile)
        if active_pids and not args.force:
            print(
                f"Error: Profile '{args.alias}' has active running session(s) (PID: {', '.join(map(str, active_pids))}).",
                file=sys.stderr
            )
            print("Please close active sessions before removing, or use -f/--force to proceed.", file=sys.stderr)
            return 1

        if not args.force:
            print(f"WARNING: Deleting profile '{profile.alias}' will permanently remove all isolated")
            print(f"         authentication tokens, configuration, and conversation history.")
            print(f"         Target directory: {profile.home_dir}")
            print(f"         This action cannot be undone.")
            confirm = input(f"Are you sure you want to permanently remove '{profile.alias}'? [y/N]: ").strip().lower()
            if confirm not in ("y", "yes"):
                print("Operation cancelled.")
                return 0

        profile = registry.remove_profile(args.alias, purge_files=not args.keep_data, force=args.force)
        print(f"Profile '{profile.alias}' (ID: {profile.id}) successfully removed.")
        return 0
    except (ProfileNotFoundError, InvalidAliasError, RegistryError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def cmd_run(args, registry: ProfileRegistry):
    profile = registry.get_by_alias(args.alias)
    if not profile:
        print(f"Error: Profile '{args.alias}' not found.", file=sys.stderr)
        return 1

    # Check for active running sessions (safeguard against concurrent database access)
    active_pids = registry.get_active_sessions(profile)
    if active_pids and not getattr(args, "allow_concurrent", False):
        pid_list = ", ".join(map(str, active_pids))
        print(
            f"Warning: Profile '{profile.alias}' currently has active session(s) (PID: {pid_list}).\n"
            "         Running concurrent sessions on the same profile risks database lock contention\n"
            "         and conversation corruption in conversation_summaries.db.",
            file=sys.stderr
        )
        if sys.stdin.isatty():
            try:
                confirm = input("Do you want to proceed with concurrent session anyway? [y/N]: ").strip().lower()
                if confirm not in ("y", "yes"):
                    print("Aborted concurrent session launch.")
                    return 1
            except (EOFError, KeyboardInterrupt):
                print("\nCancelled.")
                return 1
        else:
            print("Error: Blocked concurrent execution. Use -f / --allow-concurrent to override.", file=sys.stderr)
            return 1

    # Check for known Google backend eligibility warning
    warning = registry.check_eligibility_warning(profile)
    if warning:
        print(f"Notice: {warning}", file=sys.stderr)

    registry.touch_last_used(profile.alias)
    runner = IsolationRunner(agy_binary=args.binary)

    # Collect extra arguments
    extra_args = []
    if args.continue_session:
        extra_args.append("-c")

    if getattr(args, "agy_args", None):
        # Filter out stray bare '--' delimiters if present
        for arg in args.agy_args:
            if arg == "--":
                continue
            if arg in ("-c", "--continue") and "-c" in extra_args:
                continue
            extra_args.append(arg)

    try:
        return runner.run_interactive(
            profile=profile,
            extra_args=extra_args,
            as_unprivileged_user=getattr(args, "unprivileged", False)
        )
    except Exception as e:
        print(f"Failed to run AGY session: {e}", file=sys.stderr)
        return 1


def cmd_menu(args, registry: ProfileRegistry):
    runner = IsolationRunner(agy_binary=args.binary)
    menu = TerminalMenu(registry, runner)
    menu.display()
    return 0


def cmd_update(args, registry: ProfileRegistry):
    repo_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    git_dir = os.path.join(repo_dir, ".git")
    if not os.path.isdir(git_dir):
        print(f"AGY Switch is installed at: {repo_dir}")
        print("No .git repository found in installation directory. Cannot run git update.")
        print("To update, please re-clone or run the installer script.")
        return 1

    print(f"Updating AGY Switch from Git repository ({repo_dir})...")
    print(f"Your profile data and authentication tokens in '{args.base_dir}' will NOT be affected.\n")
    try:
        res = subprocess.run(["git", "pull", "--ff-only"], cwd=repo_dir, capture_output=True, text=True)
        print(res.stdout.strip())
        if res.returncode != 0:
            if res.stderr:
                print(res.stderr.strip(), file=sys.stderr)
            return res.returncode
        print("\nUpdate complete. All profiles, credentials, and conversation histories are preserved.")
        return 0
    except Exception as e:
        print(f"Failed to execute git update: {e}", file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ags",
        description="AGY Switch - Multi-account manager for Google Antigravity CLI"
    )
    parser.add_argument("-v", "--version", action="version", version=f"AGY Switch (ags) v{__version__}")
    parser.add_argument("--base-dir", default=DEFAULT_BASE_DIR, help="Base directory for AGY Switch profiles")
    parser.add_argument("--binary", default=None, help="Path to agy executable")

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # add
    p_add = subparsers.add_parser("add", help="Add a new profile")
    p_add.add_argument("alias", help="Profile alias (e.g. personal, work)")

    # list
    p_list = subparsers.add_parser("list", aliases=["ls"], help="List configured profiles")
    p_list.add_argument("--compact", action="store_true", help="Display in compact format (auto on narrow screens)")

    # rename
    p_rename = subparsers.add_parser("rename", aliases=["mv"], help="Rename a profile alias")
    p_rename.add_argument("old_alias", help="Current alias")
    p_rename.add_argument("new_alias", help="New alias")

    # remove
    p_remove = subparsers.add_parser("remove", aliases=["rm"], help="Remove a profile")
    p_remove.add_argument("alias", help="Alias to remove")
    p_remove.add_argument("-f", "--force", action="store_true", help="Do not prompt for confirmation")
    p_remove.add_argument("--keep-data", action="store_true", help="Preserve profile home directory on disk")

    # run
    p_run = subparsers.add_parser("run", help="Launch an AGY session for a profile")
    p_run.add_argument("-c", "--continue", dest="continue_session", action="store_true",
                       help="Continue the most recent conversation")
    p_run.add_argument("-f", "--force", "--allow-concurrent", dest="allow_concurrent", action="store_true",
                       help="Allow running concurrent session even if profile is already active")
    p_run.add_argument("--unprivileged", action="store_true", help="Execute as dedicated unprivileged user")
    p_run.add_argument("alias", help="Profile alias to run")

    # menu
    subparsers.add_parser("menu", help="Launch interactive numbered terminal menu")

    # version
    subparsers.add_parser("version", help="Show AGY Switch version")

    # update
    subparsers.add_parser("update", help="Update AGY Switch application code")

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # Default to menu if no command provided
    if not argv:
        argv = ["menu"]

    parser = build_parser()
    args, unknown = parser.parse_known_args(argv)

    # If run subcommand, collect any unknown arguments into agy_args
    if args.command == "run":
        args.agy_args = unknown
    elif unknown:
        # For non-run commands, unknown flags are an error
        parser.error(f"unrecognized arguments: {' '.join(unknown)}")

    registry = get_registry(args.base_dir)

    handlers = {
        "list": cmd_list,
        "ls": cmd_list,
        "add": cmd_add,
        "rename": cmd_rename,
        "mv": cmd_rename,
        "remove": cmd_remove,
        "rm": cmd_remove,
        "run": cmd_run,
        "menu": cmd_menu,
        "version": cmd_version,
        "update": cmd_update,
    }

    handler = handlers.get(args.command)
    if not handler:
        parser.print_help()
        return 1

    return handler(args, registry)


if __name__ == "__main__":
    sys.exit(main())
