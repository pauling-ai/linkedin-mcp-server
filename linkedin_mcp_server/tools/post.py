"""
LinkedIn post tools.

Provides tools for interacting with LinkedIn posts regardless of
whether they originate from a company or a personal profile.
"""

import logging
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor

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
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get the list of people who reacted to a LinkedIn post.

        Works for both company posts and personal profile posts.

        Args:
            post_url: Full LinkedIn post URL (e.g., "https://www.linkedin.com/feed/update/urn:li:activity:XXXXX/")
            ctx: FastMCP context for progress reporting

        Returns:
            Dict with url, likers (list of {name, username, url}), and count.
        """
        try:
            logger.info("Scraping post likers: %s", post_url)

            await ctx.report_progress(
                progress=0, total=100, message="Opening post reactions modal"
            )

            result = await extractor.scrape_post_likers(post_url)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return result

        except Exception as e:
            raise_tool_error(e, "get_post_likers")  # NoReturn
