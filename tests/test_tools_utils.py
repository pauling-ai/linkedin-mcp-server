"""Unit tests for linkedin_mcp_server/tools/utils.py."""

import json

import pytest

from linkedin_mcp_server.tools.utils import (
    BASIC_SECTION_MAX_CHARS,
    PREVIEW_MAX_CHARS,
    apply_detail_filter,
    format_tool_output,
    _generate_preview,
)


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


class TestGeneratePreview:
    def test_sections_result(self):
        result = {"sections": {"main_profile": "Alice Smith\nSoftware Engineer at Acme"}}
        assert _generate_preview(result) == "Alice Smith\nSoftware Engineer at Acme"

    def test_sections_truncated(self):
        result = {"sections": {"main_profile": "x" * 500}}
        assert len(_generate_preview(result)) == PREVIEW_MAX_CHARS

    def test_sections_skips_empty(self):
        result = {"sections": {"main_profile": "", "experience": "Has experience"}}
        assert _generate_preview(result) == "Has experience"

    def test_post_result(self):
        result = {"post": {"text": "Excited to share my new role!", "posted_at": "2d"}}
        assert _generate_preview(result) == "Excited to share my new role!"

    def test_likers_result(self):
        result = {
            "likers": [{"name": "Alice"}, {"name": "Bob"}],
            "count": 2,
        }
        assert _generate_preview(result) == "2 reactions: Alice, Bob"

    def test_likers_with_overflow(self):
        likers = [{"name": f"Person{i}"} for i in range(8)]
        result = {"likers": likers, "count": 8}
        preview = _generate_preview(result)
        assert "and 3 more" in preview

    def test_conversations_result(self):
        result = {"conversations": [{"name": "Alice"}, {"name": "Bob"}]}
        assert _generate_preview(result) == "2 conversations: Alice, Bob"

    def test_messages_result(self):
        result = {
            "messages": [
                {"sender": "Alice", "text": "Hey!"},
                {"sender": "me", "text": "Hi there"},
            ]
        }
        preview = _generate_preview(result)
        assert "2 messages" in preview
        assert "me" in preview

    def test_messages_raw_fallback(self):
        result = {"messages_raw": "Some raw text from the thread"}
        assert _generate_preview(result) == "Some raw text from the thread"

    def test_empty_result(self):
        assert _generate_preview({}) == ""


class TestFormatToolOutput:
    def test_inline_returns_unchanged(self):
        result = {"url": "https://example.com", "sections": {"main": "text"}}
        out = format_tool_output(result, "test_tool", "inline")
        assert out is result

    def test_file_writes_json(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = {
            "url": "https://www.linkedin.com/in/foo/",
            "sections": {"main_profile": "Alice Smith\nEngineer"},
        }
        out = format_tool_output(result, "test_tool", "file")

        assert out["output"] == "file"
        assert out["url"] == "https://www.linkedin.com/in/foo/"
        assert "Alice" in out["preview"]

        written = json.loads(open(out["file"]).read())
        assert written == result

    def test_file_carries_metadata_keys(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        result = {
            "url": "https://www.linkedin.com/jobs/search/",
            "sections": {"search_results": "jobs here"},
            "job_ids": ["123", "456"],
            "post_urns": ["urn:li:activity:111"],
        }
        out = format_tool_output(result, "search_jobs", "file")

        assert out["job_ids"] == ["123", "456"]
        assert out["post_urns"] == ["urn:li:activity:111"]
        # Full sections should NOT be in the summary
        assert "sections" not in out
