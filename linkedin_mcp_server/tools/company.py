"""
LinkedIn company profile scraping tools.

Uses innerText extraction for resilient company data capture
with configurable section selection.
"""

import asyncio
import logging
from typing import Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor, parse_company_sections
from linkedin_mcp_server.scraping.link_metadata import Reference
from linkedin_mcp_server.tools.utils import apply_detail_filter, format_tool_output

logger = logging.getLogger(__name__)


def register_company_tools(mcp: FastMCP) -> None:
    """Register all company-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Company Profile",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"company", "scraping"},
    )
    async def get_company_profile(
        company_name: str,
        ctx: Context,
        sections: str | None = None,
        detail: Literal["basic", "full"] = "basic",
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get a specific company's LinkedIn profile.

        Args:
            company_name: LinkedIn company name (e.g., "docker", "anthropic", "microsoft")
            ctx: FastMCP context for progress reporting
            sections: Comma-separated list of extra sections to scrape.
                The about page is always included.
                Available sections: posts, jobs
                Examples: "posts", "posts,jobs"
                Default (None) scrapes only the about page.
            detail: Controls how much text is returned per section.
                "basic" (default): truncates each section to BASIC_SECTION_MAX_CHARS.
                "full": returns the complete raw page text for every section.
                If basic mode doesn't contain the information you need, call this
                tool again with detail="full" to get the complete page text.
            output: Controls how the scraped data is delivered back to the caller.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: first ~200 characters of the main section text
                    - url: the LinkedIn company URL
                    - (plus any small metadata like unknown_sections)

                    Use "file" when the calling LLM does not need to parse the
                    full content inline — e.g. collecting company data to save,
                    building a report from many pages, or deferring analysis.
                    The caller can read the file later if deeper analysis is
                    needed.

        Returns:
            When output="inline":
                Dict with url, sections (name -> raw text), and optional references.
                Includes unknown_sections list when unrecognised names are passed.
                The LLM should parse the raw text in each section.
            When output="file":
                Dict with output="file", file (absolute path), preview (first
                ~200 chars of the main section), url, and any small metadata.
                The full result is in the JSON file at the given path.
        """
        try:
            requested, unknown = parse_company_sections(sections)

            logger.info(
                "Scraping company: %s (sections=%s, detail=%s)",
                company_name,
                sections,
                detail,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting company profile scrape"
            )

            result = await extractor.scrape_company(company_name, requested)
            result = apply_detail_filter(result, detail)

            if unknown:
                result["unknown_sections"] = unknown

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return format_tool_output(result, "get_company_profile", output)

        except Exception as e:
            raise_tool_error(e, "get_company_profile")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Company Posts",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"company", "scraping"},
    )
    async def get_company_posts(
        company_name: str,
        ctx: Context,
        detail: Literal["basic", "full"] = "basic",
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get recent posts from a company's LinkedIn feed.

        Args:
            company_name: LinkedIn company name (e.g., "docker", "anthropic", "microsoft")
            ctx: FastMCP context for progress reporting
            detail: Controls how much text is returned.
                "basic" (default): truncates section text to BASIC_SECTION_MAX_CHARS.
                    post_urns and references are always kept.
                "full": returns the complete raw page text.
                If basic mode doesn't contain the information you need, call this
                tool again with detail="full" to get the complete page text.
            output: Controls how the scraped data is delivered back to the caller.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: first ~200 characters of the posts section text
                    - url: the LinkedIn company posts URL
                    - post_urns: list of post URNs (always included if present)

                    Use "file" when collecting company posts to save or when
                    processing many companies in sequence.  The caller can read
                    the file later if deeper analysis is needed.

        Returns:
            When output="inline":
                Dict with url, sections (name -> raw text), and optional
                references.  The LLM should parse the raw text to extract
                individual posts.
            When output="file":
                Dict with output="file", file (absolute path), preview (first
                ~200 chars of the posts text), url, and post_urns.  The full
                result is in the JSON file at the given path.
        """
        try:
            logger.info("Scraping company posts: %s (detail=%s)", company_name, detail)

            await ctx.report_progress(
                progress=0, total=100, message="Starting company posts scrape"
            )

            url = f"https://www.linkedin.com/company/{company_name}/posts/"
            extracted = await extractor.extract_page(url, section_name="posts")
            post_urns = await extractor.extract_post_urns()

            sections: dict[str, str] = {}
            references: dict[str, list[Reference]] = {}
            section_errors: dict[str, dict[str, Any]] = {}
            if extracted.text:
                sections["posts"] = extracted.text
                if extracted.references:
                    references["posts"] = extracted.references
            elif extracted.error:
                section_errors["posts"] = extracted.error

            await ctx.report_progress(progress=100, total=100, message="Complete")

            result: dict[str, Any] = {
                "url": url,
                "sections": sections,
            }
            if post_urns:
                result["post_urns"] = post_urns
            if references:
                result["references"] = references
            if section_errors:
                result["section_errors"] = section_errors

            return format_tool_output(
                apply_detail_filter(result, detail), "get_company_posts", output
            )

        except Exception as e:
            raise_tool_error(e, "get_company_posts")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Follow Company",
        annotations={"openWorldHint": True},
        tags={"company", "action"},
    )
    async def follow_company(
        company_name: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Follow a LinkedIn company page.

        Args:
            company_name: LinkedIn company name (e.g., "docker", "anthropic", "microsoft")

        Returns:
            Dict with status and company_url.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to company page")
            browser = await get_or_create_browser()
            page = browser.page

            company_url = f"https://www.linkedin.com/company/{company_name}/"
            await page.goto(company_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

            await ctx.report_progress(progress=50, total=100, message="Looking for Follow button")
            follow_btn = page.locator("button").filter(has_text="Follow").first
            btn_count = await follow_btn.count()
            if not btn_count:
                return {
                    "status": "error",
                    "error": "Follow button not found. Company may not exist or you may already follow it.",
                    "company_url": company_url,
                }

            await follow_btn.click()
            await asyncio.sleep(1.0)

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return {
                "status": "success",
                "company_url": company_url,
            }

        except Exception as e:
            raise_tool_error(e, "follow_company")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Check Follow Company",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"company", "action"},
    )
    async def check_follow_company(
        company_name: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Check whether we are already following a LinkedIn company page.

        Args:
            company_name: LinkedIn company name (e.g., "docker", "anthropic", "microsoft")

        Returns:
            Dict with following (bool) and company_url.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to company page")
            browser = await get_or_create_browser()
            page = browser.page

            company_url = f"https://www.linkedin.com/company/{company_name}/"
            await page.goto(company_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

            await ctx.report_progress(progress=60, total=100, message="Checking follow status")

            # "Following" button means we already follow; "Follow" means we don't
            following_btn = page.locator("button").filter(has_text="Following").first
            if await following_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"following": True, "company_url": company_url}

            follow_btn = page.locator("button").filter(has_text="Follow").first
            if await follow_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"following": False, "company_url": company_url}

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return {"following": None, "company_url": company_url, "note": "Could not determine follow status"}

        except Exception as e:
            raise_tool_error(e, "check_follow_company")  # NoReturn
