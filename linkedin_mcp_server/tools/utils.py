"""Shared utilities for LinkedIn MCP tool functions."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Maximum characters per section when detail="basic".
# LinkedIn pages front-load the most important content (name, headline, location,
# about), so truncating here captures essentials while dropping the long tail.
# Adjust this constant to tune the basic-mode output size globally.
BASIC_SECTION_MAX_CHARS = 2000

# Maximum characters for the plain-text preview returned in file output mode.
PREVIEW_MAX_CHARS = 200


def apply_detail_filter(result: dict[str, Any], detail: str) -> dict[str, Any]:
    """Truncate section text for 'basic' detail mode.

    basic: each section's raw innerText is capped at BASIC_SECTION_MAX_CHARS.
           All other keys (url, references, job_ids, post_urns, …) are kept as-is.
    full:  result is returned unchanged — current behaviour.
    """
    if detail != "basic" or "sections" not in result:
        return result
    return {
        **result,
        "sections": {
            name: text[:BASIC_SECTION_MAX_CHARS]
            for name, text in result["sections"].items()
        },
    }


# ---------------------------------------------------------------------------
# File-output mode
# ---------------------------------------------------------------------------
# Many MCP callers (LLMs) pay a significant cost — in tokens, latency, and
# context-window pressure — for every byte of tool output they receive.
# Scraping tools often return thousands of characters of raw page text that
# the caller may not need to process inline.  Common workflows like "save
# this profile", "collect search results", or "get likers and write them to
# a spreadsheet" only need the data *stored*, not *understood* token by
# token.
#
# ``format_tool_output`` offers an escape hatch: when ``output="file"``, the
# full result is written as JSON to a file in the current working directory
# (the caller's project directory — NOT the MCP server's install location)
# and only a lightweight summary is returned to the LLM.  The summary
# carries:
#   • file   – absolute path so the caller can read it on demand
#   • preview – first ~200 chars of the main text (enough to confirm the
#               right page was scraped, answer simple yes/no questions, etc.)
#   • small metadata keys that are already cheap (url, count, job_ids, …)
#
# This lets the caller decide *whether* to read the full payload rather than
# forcing it to always consume it.
# ---------------------------------------------------------------------------


def format_tool_output(
    result: dict[str, Any],
    tool_name: str,
    output: str,
) -> dict[str, Any]:
    """Route tool output to inline return or file-based return.

    Parameters
    ----------
    result:
        The full result dict produced by the tool.
    tool_name:
        Used in the output filename (e.g. ``"get_person_profile"``).
    output:
        ``"inline"`` → return *result* unchanged (current behaviour).
        ``"file"``   → write *result* as JSON to ``<cwd>/<tool>_<ts>.json``
                        and return a small summary dict instead.
    """
    if output == "inline":
        return result

    # ── write full result to a JSON file ──────────────────────────────
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    filename = f"{tool_name}_{timestamp}.json"
    filepath = Path.cwd() / filename
    filepath.write_text(
        json.dumps(result, indent=2, default=str, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("format_tool_output: wrote %s (%d bytes)", filepath, filepath.stat().st_size)

    # ── build lightweight summary ─────────────────────────────────────
    summary: dict[str, Any] = {
        "output": "file",
        "file": str(filepath),
        "preview": _generate_preview(result),
    }

    # Carry through small metadata keys that are useful without reading
    # the file.  These are already tiny relative to sections/text.
    for key in (
        "url",
        "count",
        "job_ids",
        "post_urns",
        "unknown_sections",
        "cached",
        "cached_at",
        "cache_age_seconds",
        "cache_path",
    ):
        if key in result:
            summary[key] = result[key]

    return summary


def _generate_preview(result: dict[str, Any]) -> str:
    """Extract a plain-text preview from a tool result.

    Strategy: grab the first chunk of the most prominent text field.
    No NLP, no smart extraction — just truncation.
    """
    # Section-based results (profiles, searches, company pages, jobs)
    if "sections" in result:
        for text in result["sections"].values():
            if text:
                return text[:PREVIEW_MAX_CHARS]

    # Single post result (get_last_post)
    if "post" in result and isinstance(result["post"], dict):
        text = result["post"].get("text", "")
        if text:
            return text[:PREVIEW_MAX_CHARS]

    # Likers list (get_post_likers)
    if "likers" in result:
        likers = result["likers"]
        count = result.get("count", len(likers))
        names = [lr.get("name", "?") for lr in likers[:5]]
        more = f" and {count - 5} more" if count > 5 else ""
        return f"{count} reactions: {', '.join(names)}{more}"

    # Conversations list (get_inbox)
    if "conversations" in result:
        convos = result["conversations"]
        names = [c.get("name", "?") for c in convos[:5]]
        count = len(convos)
        more = f" and {count - 5} more" if count > 5 else ""
        return f"{count} conversations: {', '.join(names)}{more}"

    # Messages list (get_conversation)
    if "messages" in result:
        msgs = result["messages"]
        if msgs:
            last = msgs[-1]
            sender = last.get("sender", "?")
            text = last.get("text", "")[:150]
            return f"{len(msgs)} messages. Latest from {sender}: {text}"

    # Raw messages fallback (get_conversation structured extraction failed)
    if "messages_raw" in result:
        raw = result["messages_raw"]
        if raw:
            return raw[:PREVIEW_MAX_CHARS]

    return ""
