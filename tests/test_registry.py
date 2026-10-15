"""Automated tests for AGY Switch profile registry and isolation rules.

Verifies:
1. Support for >100 named profiles without arbitrary hardcoded limits.
2. Unique alias enforcement.
3. Safe alias validation (blocking path traversal, shell injection, whitespace, reserved words).
4. Stable profile IDs after rename.
5. Zero credentials or secret tokens stored in registry JSON.
6. No unintended filesystem access / strict base directory confinement (mode 0700).
7. Robust error handling for missing profiles and invalid operations.
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

# Ensure src is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from ags.core import (
    ProfileRegistry,
    Profile,
    validate_alias,
    InvalidAliasError,
    ProfileAlreadyExistsError,
    ProfileNotFoundError,
    RegistryError
)


class TestProfileRegistry(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="ags_test_registry_")
        self.registry = ProfileRegistry(base_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_100_plus_named_profiles_simulation(self):
        """Verify registry supports arbitrary number of accounts (>100) without hardcoded limit."""
        target_count = 120
        created_profiles = []

        for i in range(1, target_count + 1):
            alias = f"client-account-{i:03d}"
            prof = self.registry.add_profile(alias)
            created_profiles.append(prof)

        # Check in-memory count
        all_profiles = self.registry.list_profiles()
        self.assertEqual(len(all_profiles), target_count)

        # Verify all aliases and IDs are unique
        aliases = [p.alias for p in all_profiles]
        ids = [p.id for p in all_profiles]
        self.assertEqual(len(set(aliases)), target_count)
        self.assertEqual(len(set(ids)), target_count)

        # Reload registry from disk to verify persistence of all 120 profiles
        fresh_registry = ProfileRegistry(base_dir=self.test_dir)
        reloaded_profiles = fresh_registry.list_profiles()
        self.assertEqual(len(reloaded_profiles), target_count)

        # Check retrieval of first and last profiles
        p_first = fresh_registry.get_by_alias("client-account-001")
        self.assertIsNotNone(p_first)
        self.assertEqual(p_first.id, created_profiles[0].id)

        p_last = fresh_registry.get_by_alias("client-account-120")
        self.assertIsNotNone(p_last)
        self.assertEqual(p_last.id, created_profiles[-1].id)

    def test_unique_aliases_enforcement(self):
        """Verify duplicate aliases are rejected, including case variations."""
        self.registry.add_profile("personal")
        self.assertIsNotNone(self.registry.get_by_alias("personal"))

        # Exact duplicate
        with self.assertRaises(ProfileAlreadyExistsError):
            self.registry.add_profile("personal")

        # Case-insensitive duplicate
        with self.assertRaises(ProfileAlreadyExistsError):
            self.registry.add_profile("PERSONAL")

        # Whitespace trimmed duplicate
        with self.assertRaises(ProfileAlreadyExistsError):
            self.registry.add_profile("  personal  ")

    def test_safe_alias_validation(self):
        """Verify strict alias sanitization against injection, path traversal, and reserved words."""
        valid_aliases = [
            "personal", "work", "client-a", "project_1", "dev-99", "team-alpha"
        ]
        for alias in valid_aliases:
            normalized = validate_alias(alias)
            self.assertEqual(normalized, alias.lower())

        invalid_cases = [
            # Path traversal
            "../bad",
            "../../etc/passwd",
            "foo/bar",
            "foo\\bar",
            # Shell metacharacters & command injection
            "test;rm -rf",
            "a$b",
            "test|pipe",
            "foo&bar",
            "foo`whoami`",
            "foo'bar",
            'foo"bar',
            # Spaces
            "my work",
            "personal account",
            # Starting with non-alphanumeric
            "-work",
            "_dev",
            ".hidden",
            # Reserved keywords
            "add",
            "list",
            "rename",
            "remove",
            "run",
            "help",
            "menu",
            "root",
            "default",
            # Length bounds
            "",
            "   ",
            "a" * 33  # Exceeds 32 chars
        ]

        for bad_alias in invalid_cases:
            with self.subTest(bad_alias=bad_alias):
                with self.assertRaises(InvalidAliasError):
                    validate_alias(bad_alias)

    def test_stable_ids_after_rename(self):
        """Verify profile ID, home directory, and credentials remain 100% stable across renames."""
        prof = self.registry.add_profile("work")
        original_id = prof.id
        original_home = prof.home_dir
        original_user = prof.linux_user

        # Create mock file in profile home to simulate stored token/history
        mock_token_path = os.path.join(original_home, "mock_token.txt")
        with open(mock_token_path, "w") as f:
            f.write("mock-session-data")

        # Rename profile
        updated_prof = self.registry.rename_profile("work", "company")

        # Verify old alias is gone
        self.assertIsNone(self.registry.get_by_alias("work"))

        # Verify new alias resolves to the exact same profile ID and paths
        self.assertEqual(updated_prof.alias, "company")
        self.assertEqual(updated_prof.id, original_id)
        self.assertEqual(updated_prof.home_dir, original_home)
        self.assertEqual(updated_prof.linux_user, original_user)

        # Verify filesystem contents remained intact
        self.assertTrue(os.path.isfile(mock_token_path))
        with open(mock_token_path, "r") as f:
            self.assertEqual(f.read(), "mock-session-data")

        # Reload registry and verify consistency
        reloaded = ProfileRegistry(base_dir=self.test_dir)
        reloaded_prof = reloaded.get_by_alias("company")
        self.assertIsNotNone(reloaded_prof)
        self.assertEqual(reloaded_prof.id, original_id)

    def test_no_credentials_stored_in_registry_json(self):
        """Verify registry JSON strictly stores metadata only and no secrets/tokens."""
        # Add multiple profiles
        for name in ["personal", "work", "client-a", "client-b"]:
            self.registry.add_profile(name)

        # Inspect raw JSON file
        with open(self.registry.registry_file, "r", encoding="utf-8") as f:
            raw_text = f.read()
            data = json.loads(raw_text)

        # Check text does not contain credential keywords
        forbidden_substrings = [
            "token", "secret", "password", "oauth", "credential", "bearer", "refresh_token"
        ]
        for word in forbidden_substrings:
            self.assertNotIn(f'"{word}"', raw_text.lower())

        # Verify schema
        self.assertEqual(data["version"], 1)
        self.assertIn("profiles", data)
        allowed_profile_keys = {"id", "alias", "home_dir", "linux_user", "created_at", "last_used_at"}
        for p in data["profiles"].values():
            self.assertTrue(set(p.keys()).issubset(allowed_profile_keys))

    def test_no_unintended_filesystem_access(self):
        """Verify profile home directories are strictly confined to profiles/ and have 0700 permissions."""
        prof = self.registry.add_profile("sandboxed")
        
        # Verify home_dir is within base_dir/profiles
        expected_parent = os.path.realpath(os.path.join(self.test_dir, "profiles"))
        actual_path = os.path.realpath(prof.home_dir)
        self.assertTrue(actual_path.startswith(expected_parent))

        # Verify permissions are 0700
        mode = oct(os.stat(actual_path).st_mode)[-3:]
        self.assertEqual(mode, "700")

    def test_proper_handling_of_missing_profiles_and_invalid_operations(self):
        """Verify errors are gracefully raised for missing profiles and invalid operations."""
        # Non-existent rename
        with self.assertRaises(ProfileNotFoundError):
            self.registry.rename_profile("nonexistent", "newname")

        # Non-existent remove
        with self.assertRaises(ProfileNotFoundError):
            self.registry.remove_profile("nonexistent")

        # Rename to already existing alias
        self.registry.add_profile("first")
        self.registry.add_profile("second")
        with self.assertRaises(ProfileAlreadyExistsError):
            self.registry.rename_profile("first", "second")

        # Corrupted JSON handling
        with open(self.registry.registry_file, "w") as f:
            f.write("{ invalid json")

        with self.assertRaises(RegistryError):
            ProfileRegistry(base_dir=self.test_dir)


if __name__ == "__main__":
    unittest.main()
