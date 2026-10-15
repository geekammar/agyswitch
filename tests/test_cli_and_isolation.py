"""Tests for CLI parsing and Isolation Runner."""

import os
import sys
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ags.core import ProfileRegistry
from ags.isolation import IsolationRunner, check_workspace_traversal
from ags.cli import build_parser, main


class TestCliAndIsolation(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ags_test_cli_")
        self.registry = ProfileRegistry(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_cli_parser_commands(self):
        """Test argument parsing for all MVP CLI commands."""
        parser = build_parser()

        # add
        args = parser.parse_args(["add", "work"])
        self.assertEqual(args.command, "add")
        self.assertEqual(args.alias, "work")

        # list
        args = parser.parse_args(["list"])
        self.assertEqual(args.command, "list")

        # rename
        args = parser.parse_args(["rename", "work", "company"])
        self.assertEqual(args.command, "rename")
        self.assertEqual(args.old_alias, "work")
        self.assertEqual(args.new_alias, "company")

        # run with -c
        args, _ = parser.parse_known_args(["run", "-c", "work"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.alias, "work")
        self.assertTrue(args.continue_session)

        # run with passthrough agy args
        args, unknown = parser.parse_known_args(["run", "work", "--model", "gemini-3.1-pro"])
        self.assertEqual(args.command, "run")
        self.assertEqual(args.alias, "work")
        self.assertEqual(unknown, ["--model", "gemini-3.1-pro"])

        # remove
        args = parser.parse_args(["remove", "work", "-f"])
        self.assertEqual(args.command, "remove")
        self.assertEqual(args.alias, "work")
        self.assertTrue(args.force)

    def test_isolation_command_construction(self):
        """Verify command building configures HOME and D-Bus session correctly."""
        prof = self.registry.add_profile("developer")
        
        # Point to dummy agy path
        runner = IsolationRunner(agy_binary="/bin/true", use_dbus_session=True)
        cmd, env = runner.build_command(prof, extra_args=["-c"])

        # Check HOME is profile home
        self.assertEqual(env["HOME"], prof.home_dir)

        # Check command structure
        if runner.use_dbus_session:
            self.assertEqual(cmd[:2], ["dbus-run-session", "--"])
            self.assertEqual(cmd[2:], ["/bin/true", "-c"])
        else:
            self.assertEqual(cmd, ["/bin/true", "-c"])

    def test_workspace_traversal_restriction_check(self):
        """Verify check_workspace_traversal prevents unprivileged users from accessing /root."""
        # Unprivileged user trying to access /root
        allowed, reason = check_workspace_traversal("/root/projects/agyswitch", target_user="ags_prof_123")
        self.assertFalse(allowed)
        self.assertIn("mode 0700", reason)

        # Root user or non-root path
        allowed, reason = check_workspace_traversal(self.test_dir, target_user="ags_prof_123")
        self.assertTrue(allowed)
        self.assertIsNone(reason)


if __name__ == "__main__":
    unittest.main()
