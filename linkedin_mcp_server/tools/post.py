"""
LinkedIn post tools.

Provides tools for interacting with LinkedIn posts regardless of
whether they originate from a company or a personal profile.
"""

import logging
from typing import Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor
from linkedin_mcp_server.tools.utils import format_tool_output

logger = logging.getLogger(__name__)


def register_post_tools(mcp: FastMCP) -> None:
    """Register all post-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Post Likers",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"post", "scraping"},
    )
    async def get_post_likers(
        post_url: str,
        ctx: Context,
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get the list of people who reacted to a LinkedIn post.

        Works for both company posts and personal profile posts.

        Args:
            post_url: Full LinkedIn post URL (e.g., "https://www.linkedin.com/feed/update/urn:li:activity:XXXXX/")
            ctx: FastMCP context for progress reporting
            output: Controls how the scraped data is delivered back to the caller.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: reaction count and first few liker names
                    - url: the post URL
                    - count: total number of reactions

                    Use "file" when the caller needs to collect or export the
                    liker list without processing every name inline.  Posts
                    with many reactions can produce large payloads.  The caller
                    can read the file later if deeper analysis is needed.

        Returns:
            When output="inline":
                Dict with url, likers (list of {name, username, url}), and count.
            When output="file":
                Dict with output="file", file (absolute path), preview (count
                and first few names), url, and count.  The full liker list is
                in the JSON file at the given path.
        """
        try:
            logger.info("Scraping post likers: %s", post_url)

            await ctx.report_progress(
                progress=0, total=100, message="Opening post reactions modal"
            )

            result = await extractor.scrape_post_likers(post_url)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return format_tool_output(result, "get_post_likers", output)

        except Exception as e:
            raise_tool_error(e, "get_post_likers")  # NoReturn
