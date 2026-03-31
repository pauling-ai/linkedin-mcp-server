"""Unit tests for linkedin_mcp_server/tools/utils.py."""

import pytest

from linkedin_mcp_server.tools.utils import BASIC_SECTION_MAX_CHARS, apply_detail_filter


class TestApplyDetailFilter:
    def test_full_mode_returns_result_unchanged(self):
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": "x" * 5000},
            "references": {"main_profile": [{"kind": "person", "url": "/in/bar/"}]},
        }
        out = apply_detail_filter(result, "full")
        assert out is result  # same object, untouched

    def test_basic_mode_truncates_section_text(self):
        long_text = "a" * (BASIC_SECTION_MAX_CHARS + 500)
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": long_text},
        }
        out = apply_detail_filter(result, "basic")
        assert len(out["sections"]["main_profile"]) == BASIC_SECTION_MAX_CHARS

    def test_basic_mode_keeps_short_text_intact(self):
        short_text = "Name\nHeadline\nLocation"
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": short_text},
        }
        out = apply_detail_filter(result, "basic")
        assert out["sections"]["main_profile"] == short_text

    def test_basic_mode_truncates_multiple_sections(self):
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {
                "main_profile": "p" * 3000,
                "experience": "e" * 4000,
                "education": "s" * 100,
            },
        }
        out = apply_detail_filter(result, "basic")
        assert len(out["sections"]["main_profile"]) == BASIC_SECTION_MAX_CHARS
        assert len(out["sections"]["experience"]) == BASIC_SECTION_MAX_CHARS
        assert out["sections"]["education"] == "s" * 100  # already short

    def test_basic_mode_keeps_references(self):
        refs = [{"kind": "person", "url": "/in/bar/", "text": "Bar"}]
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": "x" * 5000},
            "references": {"main_profile": refs},
        }
        out = apply_detail_filter(result, "basic")
        assert out["references"] == {"main_profile": refs}

    def test_basic_mode_keeps_job_ids(self):
        result = {
            "url": "https://www.linkedin.com/jobs/search/",
            "sections": {"search_results": "j" * 5000},
            "job_ids": ["123", "456"],
        }
        out = apply_detail_filter(result, "basic")
        assert out["job_ids"] == ["123", "456"]

    def test_basic_mode_keeps_post_urns(self):
        result = {
            "url": "https://www.linkedin.com/company/foo/posts/",
            "sections": {"posts": "p" * 5000},
            "post_urns": ["urn:li:activity:111", "urn:li:activity:222"],
        }
        out = apply_detail_filter(result, "basic")
        assert out["post_urns"] == ["urn:li:activity:111", "urn:li:activity:222"]

    def test_basic_mode_keeps_url(self):
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": "x" * 5000},
        }
        out = apply_detail_filter(result, "basic")
        assert out["url"] == "https://www.linkedin.com/in/foo/"

    def test_basic_mode_no_sections_key_is_noop(self):
        result = {"url": "https://www.linkedin.com/in/foo/", "status": "ok"}
        out = apply_detail_filter(result, "basic")
        assert out == result

    def test_basic_mode_does_not_mutate_original(self):
        original_text = "x" * 5000
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": original_text},
        }
        apply_detail_filter(result, "basic")
        # original dict is unchanged
        assert result["sections"]["main_profile"] == original_text

    def test_unknown_detail_value_returns_unchanged(self):
        """Any value other than 'basic' behaves like 'full'."""
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": "x" * 5000},
        }
        out = apply_detail_filter(result, "verbose")
        assert out is result
