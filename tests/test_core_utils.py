"""Tests for core utility functions (scrolling, modals)."""

from linkedin_mcp_server.config.schema import AppConfig
from linkedin_mcp_server.core import utils


def test_get_linkedin_call_delay_seconds_uses_configured_range(monkeypatch):
    config = AppConfig()
    config.browser.linkedin_call_delay_ms = 1500
    config.browser.linkedin_call_delay_jitter_ms = 500

    monkeypatch.setattr(utils, "get_config", lambda: config)
    seen_range = {}

    def fake_uniform(minimum, maximum):
        seen_range["minimum"] = minimum
        seen_range["maximum"] = maximum
        return 1.25

    monkeypatch.setattr(utils.random, "uniform", fake_uniform)

    assert utils.get_linkedin_call_delay_seconds() == 1.25
    assert seen_range == {"minimum": 1.0, "maximum": 2.0}


def test_get_linkedin_call_delay_seconds_clamps_minimum_to_zero(monkeypatch):
    config = AppConfig()
    config.browser.linkedin_call_delay_ms = 500
    config.browser.linkedin_call_delay_jitter_ms = 1000

    monkeypatch.setattr(utils, "get_config", lambda: config)
    seen_range = {}

    def fake_uniform(minimum, maximum):
        seen_range["minimum"] = minimum
        seen_range["maximum"] = maximum
        return 0.25

    monkeypatch.setattr(utils.random, "uniform", fake_uniform)

    assert utils.get_linkedin_call_delay_seconds() == 0.25
    assert seen_range == {"minimum": 0.0, "maximum": 1.5}
