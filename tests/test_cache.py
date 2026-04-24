import json
from datetime import timedelta

from linkedin_mcp_server.cache import (
    profile_cache_path,
    read_cached_profile,
    resolve_cache_root,
    utc_now,
    write_cached_profile,
)
from linkedin_mcp_server.config.schema import AppConfig


def test_resolve_cache_root_defaults_beside_auth_profile(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.user_data_dir = str(tmp_path / "profile")
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    assert resolve_cache_root() == tmp_path / "cache"


def test_resolve_cache_root_uses_override(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "custom-cache")
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    assert resolve_cache_root() == tmp_path / "custom-cache"


def test_profile_cache_path_includes_username_and_sections(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    path = profile_cache_path("Test User/", {"main_profile", "experience"})

    assert path == tmp_path / "cache" / "profiles" / "test-user__experience-main_profile.json"


def test_cached_profile_round_trip(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "cache")
    config.browser.profile_cache_ttl_hours = 24
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    result = {"url": "https://www.linkedin.com/in/test/", "sections": {"main_profile": "Test"}}
    path = write_cached_profile("test", {"main_profile"}, result)

    cached = read_cached_profile("test", {"main_profile"})

    assert path is not None
    assert path.exists()
    assert cached is not None
    cached_result, metadata = cached
    assert cached_result == result
    assert metadata["cached"] is True
    assert metadata["cache_path"] == str(path)


def test_cached_profile_returns_none_when_expired(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "cache")
    config.browser.profile_cache_ttl_hours = 1
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    path = write_cached_profile("test", {"main_profile"}, {"sections": {"main_profile": "Test"}})
    assert path is not None
    payload = json.loads(path.read_text())
    payload["cached_at"] = (utc_now() - timedelta(hours=2)).isoformat()
    path.write_text(json.dumps(payload))

    assert read_cached_profile("test", {"main_profile"}) is None


def test_cache_disabled_skips_read_and_write(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "cache")
    config.browser.linkedin_cache_disabled = True
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    assert write_cached_profile("test", {"main_profile"}, {"sections": {}}) is None
    assert read_cached_profile("test", {"main_profile"}) is None


def test_profile_posts_section_is_not_cached(monkeypatch, tmp_path):
    config = AppConfig()
    config.browser.linkedin_cache_dir = str(tmp_path / "cache")
    monkeypatch.setattr("linkedin_mcp_server.cache.get_config", lambda: config)

    assert write_cached_profile("test", {"main_profile", "posts"}, {"sections": {}}) is None
    assert read_cached_profile("test", {"main_profile", "posts"}) is None
