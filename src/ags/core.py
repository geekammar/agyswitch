"""Core registry, profile management, and validation for AGY Switch (ags)."""

import os
import re
import json
import uuid
import tempfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Dict, List, Optional


RESERVED_ALIASES = {
    "add", "list", "ls", "rename", "mv", "remove", "rm", "delete",
    "run", "start", "exec", "menu", "help", "default", "root",
    "system", "all", "none", "config", "settings", "status"
}

ALIAS_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")


class RegistryError(Exception):
    """Base error for registry operations."""
    pass


class InvalidAliasError(RegistryError):
    """Raised when an alias does not conform to security or naming standards."""
    pass


class ProfileNotFoundError(RegistryError):
    """Raised when a specified profile does not exist."""
    pass


class ProfileAlreadyExistsError(RegistryError):
    """Raised when an alias or profile ID is already registered."""
    pass


@dataclass
class Profile:
    """Represents a Google Antigravity account profile."""
    id: str
    alias: str
    home_dir: str
    linux_user: Optional[str]
    created_at: str
    last_used_at: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Profile":
        # Disallow sensitive or secret keys
        forbidden_keys = {"token", "secret", "password", "oauth", "credential", "refresh_token"}
        found_forbidden = forbidden_keys.intersection(k.lower() for k in data.keys())
        if found_forbidden:
            raise RegistryError(f"Security violation: forbidden keys found in profile data: {found_forbidden}")
        return cls(
            id=data["id"],
            alias=data["alias"],
            home_dir=data["home_dir"],
            linux_user=data.get("linux_user"),
            created_at=data["created_at"],
            last_used_at=data.get("last_used_at")
        )


def validate_alias(alias: str) -> str:
    """
    Validate and normalize an alias string.
    - Must be 1 to 32 characters long
    - Alphanumeric plus hyphens and underscores
    - Must start with an alphanumeric character
    - Cannot contain path traversal, whitespace, or shell metacharacters
    - Cannot be a reserved command word
    """
    if not isinstance(alias, str):
        raise InvalidAliasError("Alias must be a string.")
    
    normalized = alias.strip().lower()
    if not normalized:
        raise InvalidAliasError("Alias cannot be empty or blank.")
    
    if len(normalized) > 32:
        raise InvalidAliasError(f"Alias '{alias}' exceeds maximum length of 32 characters.")
    
    if not ALIAS_PATTERN.match(normalized):
        raise InvalidAliasError(
            f"Alias '{alias}' contains invalid characters. Must start with a-z, 0-9 and contain only "
            f"lowercase alphanumeric characters, underscores, and hyphens."
        )
    
    if normalized in RESERVED_ALIASES:
        raise InvalidAliasError(f"Alias '{alias}' is a reserved command name.")
    
    return normalized


def generate_profile_id() -> str:
    """Generate a unique, stable 12-character hex profile ID."""
    return f"prof_{uuid.uuid4().hex[:12]}"


class ProfileRegistry:
    """
    Manages loading, updating, and storing profile metadata in a secure JSON file.
    Does NOT store any credentials, OAuth tokens, or secrets.
    """

    def __init__(self, base_dir: str):
        self.base_dir = os.path.abspath(base_dir)
        self.profiles_dir = os.path.join(self.base_dir, "profiles")
        self.registry_file = os.path.join(self.base_dir, "registry.json")
        self.profiles: Dict[str, Profile] = {}  # Keyed by stable profile ID
        self._ensure_base_dirs()
        self.load()

    def _ensure_base_dirs(self):
        os.makedirs(self.profiles_dir, mode=0o700, exist_ok=True)

    def load(self):
        """Load registry from JSON file if it exists."""
        self.profiles.clear()
        if not os.path.exists(self.registry_file):
            return

        with open(self.registry_file, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError as e:
                raise RegistryError(f"Corrupted registry file {self.registry_file}: {e}")

        version = data.get("version", 1)
        if version != 1:
            raise RegistryError(f"Unsupported registry version: {version}")

        profiles_raw = data.get("profiles", {})
        for prof_id, p_data in profiles_raw.items():
            profile = Profile.from_dict(p_data)
            self.profiles[profile.id] = profile

    def save(self):
        """
        Atomically save the registry to disk.
        Uses a temporary file in the same directory, followed by atomic replace.
        """
        payload = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "profile_count": len(self.profiles),
            "profiles": {p.id: p.to_dict() for p in self.profiles.values()}
        }

        # Write to temporary file first
        temp_dir = self.base_dir
        with tempfile.NamedTemporaryFile("w", dir=temp_dir, delete=False, encoding="utf-8") as tf:
            json.dump(payload, tf, indent=2)
            tf.flush()
            os.fsync(tf.fileno())
            temp_path = tf.name

        os.chmod(temp_path, 0o600)
        os.replace(temp_path, self.registry_file)

    def get_by_alias(self, alias: str) -> Optional[Profile]:
        """Find a profile by alias (case-normalized)."""
        norm_alias = alias.strip().lower()
        for p in self.profiles.values():
            if p.alias == norm_alias:
                return p
        return None

    def get_by_id(self, profile_id: str) -> Optional[Profile]:
        """Find a profile by its stable ID."""
        return self.profiles.get(profile_id)

    def list_profiles(self) -> List[Profile]:
        """Return all profiles sorted by alias."""
        return sorted(self.profiles.values(), key=lambda p: p.alias)

    def add_profile(self, alias: str, linux_user_prefix: str = "ags_") -> Profile:
        """
        Add a new profile with a validated alias and stable internal ID.
        Ensures alias uniqueness and creates the profile's dedicated home directory.
        """
        norm_alias = validate_alias(alias)
        if self.get_by_alias(norm_alias):
            raise ProfileAlreadyExistsError(f"A profile with alias '{norm_alias}' already exists.")

        profile_id = generate_profile_id()
        # Ensure no ID collision (extremely unlikely with uuid4 hex, but safe check)
        while profile_id in self.profiles:
            profile_id = generate_profile_id()

        home_dir = os.path.join(self.profiles_dir, profile_id)
        os.makedirs(home_dir, mode=0o700, exist_ok=True)

        now_str = datetime.now(timezone.utc).isoformat()
        linux_user = f"{linux_user_prefix}{profile_id}"

        profile = Profile(
            id=profile_id,
            alias=norm_alias,
            home_dir=home_dir,
            linux_user=linux_user,
            created_at=now_str,
            last_used_at=None
        )

        self.profiles[profile_id] = profile
        self.save()
        return profile

    def rename_profile(self, old_alias: str, new_alias: str) -> Profile:
        """
        Rename an existing profile's alias.
        CRITICAL: Does NOT alter the profile's stable ID, home directory, linux user,
        conversations, or credentials.
        """
        norm_old = validate_alias(old_alias)
        norm_new = validate_alias(new_alias)

        if norm_old == norm_new:
            profile = self.get_by_alias(norm_old)
            if not profile:
                raise ProfileNotFoundError(f"Profile '{old_alias}' not found.")
            return profile

        existing_target = self.get_by_alias(norm_new)
        if existing_target:
            raise ProfileAlreadyExistsError(f"Cannot rename: target alias '{norm_new}' already exists.")

        profile = self.get_by_alias(norm_old)
        if not profile:
            raise ProfileNotFoundError(f"Profile '{old_alias}' not found.")

        # Update alias in-place on stable profile object
        profile.alias = norm_new
        self.save()
        return profile

    def remove_profile(self, alias: str, purge_files: bool = True) -> Profile:
        """
        Remove a profile from the registry.
        If purge_files is True, deletes the profile's dedicated home directory.
        """
        norm_alias = validate_alias(alias)
        profile = self.get_by_alias(norm_alias)
        if not profile:
            raise ProfileNotFoundError(f"Profile '{alias}' not found.")

        del self.profiles[profile.id]
        self.save()

        if purge_files and os.path.exists(profile.home_dir):
            import shutil
            shutil.rmtree(profile.home_dir, ignore_errors=True)

        return profile

    def touch_last_used(self, alias: str) -> Optional[Profile]:
        """Update last_used_at timestamp for a profile."""
        profile = self.get_by_alias(alias)
        if profile:
            profile.last_used_at = datetime.now(timezone.utc).isoformat()
            self.save()
        return profile
