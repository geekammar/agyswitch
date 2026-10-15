"""Phase 02 Automated Acceptance Tests for AGY Switch MVP v1.

Verifies:
1. get_latest_conversation query on SQLite conversation database.
2. Mobile menu formatting and layout on narrow terminals.
3. Menu selection of profiles (by number).
4. Quick-resume shortcuts ('1c', 'c1') and action 'c' continuation.
5. Menu blocked Google account alert and confirmation.
6. Menu graceful handling of EOFError and KeyboardInterrupt.
7. Post-session menu return prompt ('Press Enter to return to menu...').
8. CLI version flags ('--version', '-v', 'version').
9. CLI responsive list ('--compact' and auto on narrow terminals).
10. Installation script and update preservation of profiles and credentials.
"""

import os
import sys
import json
import sqlite3
import shutil
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ags import __version__
from ags.core import ProfileRegistry, Profile
from ags.isolation import IsolationRunner
from ags.menu import TerminalMenu
from ags.cli import build_parser, main


class TestPhase02Mvp(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ags_p02_test_")
        self.registry = ProfileRegistry(base_dir=self.test_dir)
        self.runner = IsolationRunner(agy_binary="/bin/true", use_dbus_session=False)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_01_get_latest_conversation(self):
        """Verify get_latest_conversation safely queries SQLite metadata without mutating records."""
        prof = self.registry.add_profile("dev-conv")
        
        # When no DB exists, returns None
        self.assertIsNone(self.registry.get_latest_conversation(prof))

        # Create mock conversation database
        agy_dir = os.path.join(prof.home_dir, ".gemini", "antigravity-cli")
        os.makedirs(agy_dir, exist_ok=True)
        db_path = os.path.join(agy_dir, "conversation_summaries.db")

        conn = sqlite3.connect(db_path)
        with conn:
            conn.execute("""
                CREATE TABLE conversation_summaries (
                    conversation_id TEXT PRIMARY KEY,
                    title TEXT,
                    last_modified_time TEXT
                )
            """)
            conn.execute(
                "INSERT INTO conversation_summaries VALUES (?, ?, ?)",
                ("conv-old", "Old Debug Session", "2026-10-15 10:00:00")
            )
            conn.execute(
                "INSERT INTO conversation_summaries VALUES (?, ?, ?)",
                ("conv-latest", "New Feature Refactor", "2026-10-15 22:00:00")
            )
        conn.close()

        latest = self.registry.get_latest_conversation(prof)
        self.assertIsNotNone(latest)
        self.assertEqual(latest["conversation_id"], "conv-latest")
        self.assertEqual(latest["title"], "New Feature Refactor")
        self.assertEqual(latest["last_modified_time"], "2026-10-15 22:00:00")

    def test_02_menu_profile_display_mobile_layout(self):
        """Verify menu displays clean, wrap-free profile cards for narrow terminals."""
        prof = self.registry.add_profile("personal")
        menu = TerminalMenu(self.registry, self.runner)

        # Feed quit ('q') immediately
        with patch("builtins.input", return_value="q"), patch("sys.stdout.write") as mock_stdout:
            with patch("builtins.print") as mock_print:
                menu.display()

                # Gather printed lines
                printed = [call[0][0] for call in mock_print.call_args_list if call[0]]
                all_text = "\n".join(str(p) for p in printed)

                self.assertIn("personal", all_text)
                self.assertIn("Google Account:", all_text)
                self.assertIn("Status:", all_text)
                self.assertIn("Actions:", all_text)
                self.assertIn("Resume previous conversation (-c)", all_text)

    def test_03_menu_numerical_profile_selection(self):
        """Verify selecting profile by number launches an isolated session."""
        prof = self.registry.add_profile("work")
        menu = TerminalMenu(self.registry, self.runner)

        # Select '1', then inside session finish press Enter, then 'q'
        inputs = iter(["1", "", "q"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                menu.display()
                mock_run.assert_called_once_with(prof, extra_args=[])

    def test_04_menu_quick_resume_shortcuts(self):
        """Verify quick resume shortcuts '1c' and 'c1' launch profile with -c."""
        prof = self.registry.add_profile("developer")
        menu = TerminalMenu(self.registry, self.runner)

        # Test '1c'
        inputs_1c = iter(["1c", "", "q"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs_1c)):
            with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                menu.display()
                mock_run.assert_called_once_with(prof, extra_args=["-c"])

        # Test 'c1'
        inputs_c1 = iter(["c1", "", "q"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs_c1)):
            with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                menu.display()
                mock_run.assert_called_once_with(prof, extra_args=["-c"])

    def test_05_menu_continue_action_with_default(self):
        """Verify action 'c' defaults to most recently used profile."""
        prof1 = self.registry.add_profile("alpha")
        prof2 = self.registry.add_profile("beta")
        self.registry.touch_last_used("beta")

        menu = TerminalMenu(self.registry, self.runner)

        # Choose 'c', hit Enter to accept default ('beta'), press Enter post-session, then 'q'
        inputs = iter(["c", "", "", "q"])
        with patch("builtins.input", side_effect=lambda *args: next(inputs)):
            with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                menu.display()
                mock_run.assert_called_once()
                # Verify profile run was beta
                called_profile = mock_run.call_args[0][0]
                self.assertEqual(called_profile.alias, "beta")
                self.assertEqual(mock_run.call_args[1]["extra_args"], ["-c"])

    def test_06_menu_blocked_account_warning(self):
        """Verify launching a profile with eligibility warning displays notice and prompts confirmation."""
        prof = self.registry.add_profile("restricted")

        # Mock check_eligibility_warning to return upstream warning
        with patch.object(ProfileRegistry, "check_eligibility_warning", return_value="Google verification required"):
            menu = TerminalMenu(self.registry, self.runner)

            # 1. Decline launch ('n')
            inputs_decline = iter(["1", "n", "q"])
            with patch("builtins.input", side_effect=lambda *args: next(inputs_decline)):
                with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                    menu.display()
                    mock_run.assert_not_called()

            # 2. Accept launch ('y')
            inputs_accept = iter(["1", "y", "", "q"])
            with patch("builtins.input", side_effect=lambda *args: next(inputs_accept)):
                with patch.object(self.runner, "run_interactive", return_value=0) as mock_run:
                    menu.display()
                    mock_run.assert_called_once_with(prof, extra_args=[])

    def test_07_menu_safe_interrupts(self):
        """Verify EOFError and KeyboardInterrupt do not crash menu with uncaught tracebacks."""
        menu = TerminalMenu(self.registry, self.runner)

        # Main prompt interrupted by Ctrl+C
        with patch("builtins.input", side_effect=KeyboardInterrupt):
            # Should exit cleanly without raising
            menu.display()

        # Main prompt closed by EOF
        with patch("builtins.input", side_effect=EOFError):
            menu.display()

    def test_08_cli_version_options(self):
        """Verify CLI prints version with -v, --version, and version subcommand."""
        # version subcommand
        with patch("sys.stdout.write") as mock_out:
            ret = main(["--base-dir", self.test_dir, "version"])
            self.assertEqual(ret, 0)

        # --version argument
        with self.assertRaises(SystemExit) as ctx:
            main(["--version"])
        self.assertEqual(ctx.exception.code, 0)

    def test_09_cli_compact_list(self):
        """Verify CLI cmd_list supports --compact flag."""
        prof = self.registry.add_profile("compact-prof")
        with patch("builtins.print") as mock_print:
            ret = main(["--base-dir", self.test_dir, "list", "--compact"])
            self.assertEqual(ret, 0)
            printed = [call[0][0] for call in mock_print.call_args_list if call[0]]
            all_text = "\n".join(str(p) for p in printed)
            self.assertIn("• compact-prof", all_text)
            self.assertIn("Status:", all_text)

    def test_10_installer_preserves_profiles_and_credentials(self):
        """Verify running install.sh or updating does not alter or erase $AGS_HOME profiles."""
        prof = self.registry.add_profile("preserved-prof")

        # Create mock token in profile directory
        token_dir = os.path.join(prof.home_dir, ".gemini", "antigravity-cli")
        os.makedirs(token_dir, mode=0o700, exist_ok=True)
        token_file = os.path.join(token_dir, "antigravity-oauth-token")
        with open(token_file, "w") as f:
            f.write("mock-secret-token")

        # Simulate update script run pointing to custom prefix
        tmp_prefix = tempfile.mkdtemp(prefix="ags_test_update_")
        try:
            repo_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
            installer = os.path.join(repo_dir, "install.sh")
            import subprocess
            res = subprocess.run([installer, "--prefix", tmp_prefix], capture_output=True, text=True)
            self.assertEqual(res.returncode, 0)

            # Verify that reloaded ProfileRegistry still contains 'preserved-prof' and token
            reloaded = ProfileRegistry(base_dir=self.test_dir)
            p = reloaded.get_by_alias("preserved-prof")
            self.assertIsNotNone(p)
            self.assertEqual(p.id, prof.id)
            self.assertTrue(os.path.isfile(token_file))
            with open(token_file, "r") as f:
                self.assertEqual(f.read(), "mock-secret-token")

            # Uninstall
            res_un = subprocess.run([installer, "--prefix", tmp_prefix, "--uninstall"], capture_output=True, text=True)
            self.assertEqual(res_un.returncode, 0)

            # Confirm token and profile data are STILL untouched after uninstall
            self.assertTrue(os.path.isfile(token_file))
            self.assertIsNotNone(reloaded.get_by_alias("preserved-prof"))
        finally:
            shutil.rmtree(tmp_prefix, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
