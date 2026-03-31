"""Shared utilities for LinkedIn MCP tool functions."""

from typing import Any

# Maximum characters per section when detail="basic".
# LinkedIn pages front-load the most important content (name, headline, location,
# about), so truncating here captures essentials while dropping the long tail.
# Adjust this constant to tune the basic-mode output size globally.
BASIC_SECTION_MAX_CHARS = 2000


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
