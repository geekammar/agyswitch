"""Simple numbered terminal menu for AGY Switch.
Optimized for mobile SSH (Termius, JuiceSSH) and desktop terminals alike.
Avoids fragile curses libraries to ensure reliable rendering over high-latency connections.
"""

import sys
from typing import Optional
from .core import ProfileRegistry, Profile, InvalidAliasError, ProfileAlreadyExistsError, ProfileNotFoundError
from .isolation import IsolationRunner


class TerminalMenu:
    """Renders a robust numbered menu for profile selection and management."""

    def __init__(self, registry: ProfileRegistry, runner: IsolationRunner):
        self.registry = registry
        self.runner = runner

    def display(self):
        """Main loop for the interactive terminal menu."""
        while True:
            profiles = self.registry.list_profiles()
            print("\n" + "=" * 50)
            print("         AGY Switch (ags) - Account Manager")
            print("=" * 50)

            if not profiles:
                print(" No profiles configured yet.\n")
            else:
                print(" Available Profiles:")
                for idx, p in enumerate(profiles, start=1):
                    last_used = p.last_used_at[:16].replace("T", " ") if p.last_used_at else "Never"
                    status = self.registry.get_auth_status(p)
                    print(f"  [{idx:2d}] {p.alias:<16} (ID: {p.id}, Status: {status}, Last used: {last_used})")
                print()

            print(" Actions:")
            if profiles:
                print("  [1..N] Launch profile by number")
                print("  [c]    Launch profile with --continue (-c)")
            print("  [a]    Add a new profile")
            if profiles:
                print("  [m]    Rename an existing profile")
                print("  [d]    Delete / remove a profile")
            print("  [q]    Quit menu")
            print("-" * 50)

            try:
                choice = input("Enter choice > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if choice in ("q", "quit", "exit"):
                print("Goodbye.")
                break
            elif choice in ("a", "add"):
                self._action_add()
            elif choice in ("m", "rename"):
                self._action_rename(profiles)
            elif choice in ("d", "del", "delete", "remove"):
                self._action_remove(profiles)
            elif choice in ("c", "continue"):
                self._action_launch_continue(profiles)
            elif choice.isdigit():
                num = int(choice)
                if 1 <= num <= len(profiles):
                    target = profiles[num - 1]
                    self._launch_profile(target, extra_args=[])
                else:
                    print(f"Invalid selection: {choice}. Enter a number between 1 and {len(profiles)}.")
            else:
                print(f"Unknown option '{choice}'. Please select from the menu.")

    def _action_add(self):
        try:
            alias = input("Enter alias for new profile (e.g. personal, work): ").strip()
            if not alias:
                print("Operation cancelled.")
                return
            prof = self.registry.add_profile(alias)
            print(f"Successfully added profile '{prof.alias}' (ID: {prof.id}).")
            
            # Ask if user wants to log in now
            auth_now = input("Run authentication for this profile now? [y/N]: ").strip().lower()
            if auth_now in ("y", "yes"):
                self._launch_profile(prof, extra_args=[])
        except (InvalidAliasError, ProfileAlreadyExistsError) as e:
            print(f"Error: {e}")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")

    def _action_rename(self, profiles):
        if not profiles:
            return
        try:
            old_alias = input("Enter alias or number of profile to rename: ").strip()
            if old_alias.isdigit():
                idx = int(old_alias)
                if 1 <= idx <= len(profiles):
                    old_alias = profiles[idx - 1].alias
                else:
                    print("Invalid profile number.")
                    return
            
            new_alias = input(f"Enter new alias for '{old_alias}': ").strip()
            if not new_alias:
                print("Operation cancelled.")
                return
            
            updated = self.registry.rename_profile(old_alias, new_alias)
            print(f"Successfully renamed profile to '{updated.alias}'. All credentials and history preserved.")
        except (ProfileNotFoundError, InvalidAliasError, ProfileAlreadyExistsError) as e:
            print(f"Error: {e}")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")

    def _action_remove(self, profiles):
        if not profiles:
            return
        try:
            target = input("Enter alias or number of profile to delete: ").strip()
            if target.isdigit():
                idx = int(target)
                if 1 <= idx <= len(profiles):
                    target = profiles[idx - 1].alias
                else:
                    print("Invalid profile number.")
                    return
            
            confirm = input(f"Are you sure you want to remove profile '{target}'? [y/N]: ").strip().lower()
            if confirm in ("y", "yes"):
                removed = self.registry.remove_profile(target)
                print(f"Profile '{removed.alias}' removed.")
            else:
                print("Deletion cancelled.")
        except (ProfileNotFoundError, InvalidAliasError) as e:
            print(f"Error: {e}")
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")

    def _action_launch_continue(self, profiles):
        if not profiles:
            return
        try:
            target = input("Enter profile number or alias to continue (-c): ").strip()
            if target.isdigit():
                idx = int(target)
                if 1 <= idx <= len(profiles):
                    prof = profiles[idx - 1]
                else:
                    print("Invalid profile number.")
                    return
            else:
                prof = self.registry.get_by_alias(target)
                if not prof:
                    print(f"Profile '{target}' not found.")
                    return

            self._launch_profile(prof, extra_args=["-c"])
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")

    def _launch_profile(self, profile: Profile, extra_args: list):
        print(f"\nLaunching profile '{profile.alias}'...")
        self.registry.touch_last_used(profile.alias)
        try:
            ret = self.runner.run_interactive(profile, extra_args=extra_args)
            print(f"\nProfile session '{profile.alias}' ended (exit code: {ret}).")
        except Exception as e:
            print(f"Failed to launch profile session: {e}")
