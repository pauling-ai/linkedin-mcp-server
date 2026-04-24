"""Small file cache for LinkedIn tool results."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from linkedin_mcp_server.config import get_config


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    return utc_now().replace(microsecond=0).isoformat()


def parse_cached_at(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def resolve_cache_root() -> Path:
    """Return the cache root, defaulting beside the configured auth profile."""
    browser = get_config().browser
    if browser.linkedin_cache_dir:
        return Path(browser.linkedin_cache_dir).expanduser()

    user_data_dir = Path(browser.user_data_dir).expanduser()
    if user_data_dir.name == "profile":
        return user_data_dir.parent / "cache"
    return user_data_dir / "cache"


def profile_cache_dir() -> Path:
    return resolve_cache_root() / "profiles"


def slugify_cache_part(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", value.strip().lower()).strip("-")
    return cleaned or "unknown"


def profile_cache_path(linkedin_username: str, requested_sections: set[str]) -> Path:
    username = slugify_cache_part(linkedin_username)
    section_key = "-".join(sorted(requested_sections)) or "main_profile"
    return profile_cache_dir() / f"{username}__{slugify_cache_part(section_key)}.json"


def is_profile_cacheable(requested_sections: set[str]) -> bool:
    """Return whether this profile section set is safe to cache."""
    return "posts" not in requested_sections


def read_cached_profile(
    linkedin_username: str,
    requested_sections: set[str],
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Return cached raw profile result and metadata if fresh enough."""
    browser = get_config().browser
    if browser.linkedin_cache_disabled or not is_profile_cacheable(requested_sections):
        return None

    path = profile_cache_path(linkedin_username, requested_sections)
    if not path.exists():
        return None

    payload = json.loads(path.read_text(encoding="utf-8"))
    cached_at_raw = payload.get("cached_at")
    result = payload.get("result")
    if not isinstance(cached_at_raw, str) or not isinstance(result, dict):
        return None

    cached_at = parse_cached_at(cached_at_raw)
    age_seconds = (utc_now() - cached_at).total_seconds()
    ttl_seconds = browser.profile_cache_ttl_hours * 3600
    if age_seconds > ttl_seconds:
        return None

    metadata = {
        "cached": True,
        "cached_at": cached_at_raw,
        "cache_age_seconds": int(age_seconds),
        "cache_path": str(path),
    }
    return result, metadata


def write_cached_profile(
    linkedin_username: str,
    requested_sections: set[str],
    result: dict[str, Any],
) -> Path | None:
    """Write raw profile result to the cache and return the cache path."""
    if get_config().browser.linkedin_cache_disabled or not is_profile_cacheable(
        requested_sections
    ):
        return None

    path = profile_cache_path(linkedin_username, requested_sections)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "cached_at": utc_now_iso(),
        "tool": "get_person_profile",
        "linkedin_username": linkedin_username,
        "requested_sections": sorted(requested_sections),
        "result": result,
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path
