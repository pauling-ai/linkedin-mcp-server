"""
LinkedIn job scraping tools with search and detail extraction.

Uses innerText extraction for resilient job data capture.
"""

import logging
from typing import Annotated, Any, Literal

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends
from pydantic import Field

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor
from linkedin_mcp_server.tools.utils import apply_detail_filter, format_tool_output

logger = logging.getLogger(__name__)


def register_job_tools(mcp: FastMCP) -> None:
    """Register all job-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Job Details",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "scraping"},
    )
    async def get_job_details(
        job_id: str,
        ctx: Context,
        detail: Literal["basic", "full"] = "basic",
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get job details for a specific job posting on LinkedIn.

        Args:
            job_id: LinkedIn job ID (e.g., "4252026496", "3856789012")
            ctx: FastMCP context for progress reporting
            detail: Controls how much text is returned.
                "basic" (default): truncates section text to BASIC_SECTION_MAX_CHARS —
                    enough for title, company, location, and job summary.
                "full": returns the complete raw page text including full description.
                If basic mode doesn't contain the information you need, call this
                tool again with detail="full" to get the complete page text.
            output: Controls how the scraped data is delivered back to the caller.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: first ~200 characters of the job posting text
                    - url: the LinkedIn job URL

                    Use "file" when collecting job details to save or when
                    processing many job postings in sequence.  The caller can
                    read the file later if deeper analysis is needed.

        Returns:
            When output="inline":
                Dict with url, sections (name -> raw text), and optional references.
                The LLM should parse the raw text to extract job details.
            When output="file":
                Dict with output="file", file (absolute path), preview (first
                ~200 chars of the job text), and url.  The full result is in
                the JSON file at the given path.
        """
        try:
            logger.info("Scraping job: %s (detail=%s)", job_id, detail)

            await ctx.report_progress(
                progress=0, total=100, message="Starting job scrape"
            )

            result = await extractor.scrape_job(job_id)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return format_tool_output(
                apply_detail_filter(result, detail), "get_job_details", output
            )

        except Exception as e:
            raise_tool_error(e, "get_job_details")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Search Jobs",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"job", "search"},
    )
    async def search_jobs(
        keywords: str,
        ctx: Context,
        location: str | None = None,
        max_pages: Annotated[int, Field(ge=1, le=10)] = 3,
        date_posted: str | None = None,
        job_type: str | None = None,
        experience_level: str | None = None,
        work_type: str | None = None,
        easy_apply: bool = False,
        sort_by: str | None = None,
        detail: Literal["basic", "full"] = "basic",
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Search for jobs on LinkedIn.

        Returns job_ids that can be passed to get_job_details for full info.

        Args:
            keywords: Search keywords (e.g., "software engineer", "data scientist")
            ctx: FastMCP context for progress reporting
            location: Optional location filter (e.g., "San Francisco", "Remote")
            max_pages: Maximum number of result pages to load (1-10, default 3)
            date_posted: Filter by posting date (past_hour, past_24_hours, past_week, past_month)
            job_type: Filter by job type, comma-separated (full_time, part_time, contract, temporary, volunteer, internship, other)
            experience_level: Filter by experience level, comma-separated (internship, entry, associate, mid_senior, director, executive)
            work_type: Filter by work type, comma-separated (on_site, remote, hybrid)
            easy_apply: Only show Easy Apply jobs (default false)
            sort_by: Sort results (date, relevance)
            detail: Controls how much text is returned.
                "basic" (default): truncates section text to BASIC_SECTION_MAX_CHARS.
                    job_ids and references are always kept.
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
                    - preview: first ~200 characters of the search results text
                    - url: the LinkedIn search URL
                    - job_ids: list of job ID strings (always included)

                    Use "file" when collecting job search results to save or
                    when running many searches in sequence.  The caller can
                    read the file later if deeper analysis is needed.

        Returns:
            When output="inline":
                Dict with url, sections (name -> raw text), job_ids (list of
                numeric job ID strings usable with get_job_details), and
                optional references.
            When output="file":
                Dict with output="file", file (absolute path), preview (first
                ~200 chars of the results), url, and job_ids.  The full result
                is in the JSON file at the given path.
        """
        try:
            logger.info(
                "Searching jobs: keywords='%s', location='%s', max_pages=%d, detail=%s",
                keywords,
                location,
                max_pages,
                detail,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting job search"
            )

            result = await extractor.search_jobs(
                keywords,
                location=location,
                max_pages=max_pages,
                date_posted=date_posted,
                job_type=job_type,
                experience_level=experience_level,
                work_type=work_type,
                easy_apply=easy_apply,
                sort_by=sort_by,
            )

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return format_tool_output(
                apply_detail_filter(result, detail), "search_jobs", output
            )

        except Exception as e:
            raise_tool_error(e, "search_jobs")  # NoReturn
