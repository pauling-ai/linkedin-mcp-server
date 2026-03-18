"""
LinkedIn person profile scraping tools.

Uses innerText extraction for resilient profile data capture
with configurable section selection.
"""

import asyncio
import logging
from typing import Any

from fastmcp import Context, FastMCP
from fastmcp.dependencies import Depends

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.dependencies import get_extractor
from linkedin_mcp_server.error_handler import raise_tool_error
from linkedin_mcp_server.scraping import LinkedInExtractor, parse_person_sections

logger = logging.getLogger(__name__)


def register_person_tools(mcp: FastMCP) -> None:
    """Register all person-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Person Profile",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "scraping"},
    )
    async def get_person_profile(
        linkedin_username: str,
        ctx: Context,
        sections: str | None = None,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get a specific person's LinkedIn profile.

        Args:
            linkedin_username: LinkedIn username (e.g., "stickerdaniel", "williamhgates")
            ctx: FastMCP context for progress reporting
            sections: Comma-separated list of extra sections to scrape.
                The main profile page is always included.
                Available sections: experience, education, interests, honors, languages, contact_info, posts
                Examples: "experience,education", "contact_info", "honors,languages", "posts"
                Default (None) scrapes only the main profile page.

        Returns:
            Dict with url, sections (name -> raw text), and optional references.
            Sections may be absent if extraction yielded no content for that page.
            Includes unknown_sections list when unrecognised names are passed.
            The LLM should parse the raw text in each section.
        """
        try:
            requested, unknown = parse_person_sections(sections)

            logger.info(
                "Scraping profile: %s (sections=%s)",
                linkedin_username,
                sections,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting person profile scrape"
            )

            result = await extractor.scrape_person(linkedin_username, requested)

            if unknown:
                result["unknown_sections"] = unknown

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return result

        except Exception as e:
            raise_tool_error(e, "get_person_profile")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Search People",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "search"},
    )
    async def search_people(
        keywords: str,
        ctx: Context,
        location: str | None = None,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Search for people on LinkedIn.

        Args:
            keywords: Search keywords (e.g., "software engineer", "recruiter at Google")
            ctx: FastMCP context for progress reporting
            location: Optional location filter (e.g., "New York", "Remote")

        Returns:
            Dict with url, sections (name -> raw text), and optional references.
            The LLM should parse the raw text to extract individual people and their profiles.
        """
        try:
            logger.info(
                "Searching people: keywords='%s', location='%s'",
                keywords,
                location,
            )

            await ctx.report_progress(
                progress=0, total=100, message="Starting people search"
            )

            result = await extractor.search_people(keywords, location)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            return result

        except Exception as e:
            raise_tool_error(e, "search_people")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Send Message",
        annotations={"openWorldHint": True},
        tags={"person", "messaging"},
    )
    async def send_message(
        linkedin_username: str,
        message: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Send a LinkedIn message to a 1st-degree connection.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")
            message: The message text to send.

        Returns:
            Dict with status, recipient, and message_preview.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Getting browser")
            logger.info("send_message: getting browser for %s", linkedin_username)
            browser = await get_or_create_browser()
            page = browser.page
            logger.info("send_message: browser acquired, current url=%s", page.url)

            await ctx.report_progress(progress=20, total=100, message="Navigating to profile")
            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            logger.info("send_message: navigating to %s", profile_url)
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)
            logger.info("send_message: landed on %s, title=%r", page.url, await page.title())

            await ctx.report_progress(progress=40, total=100, message="Looking for Message button")
            # Use artdeco-button--primary to find the profile's own Message button.
            # get_by_role("button", name="Message", exact=True) only finds secondary buttons
            # in "People also viewed" sections, not the profile card's primary button
            # (which has aria-label="Message [FirstName]").
            # nth(0) is the invisible sticky header; nth(1) is the visible profile card button.
            message_btn = page.locator("button.artdeco-button--primary").filter(has_text="Message").nth(1)
            btn_count = await message_btn.count()
            logger.info("send_message: primary Message button count=%d", btn_count)
            if not btn_count:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
                logger.warning(
                    "send_message: no Message button found. page url=%s body_snippet=%r",
                    page.url,
                    " ".join(body_text.split())[:300],
                )
                return {
                    "status": "error",
                    "error": "Message button not found. User may not be a 1st-degree connection.",
                    "profile_url": profile_url,
                    "current_url": page.url,
                }

            await message_btn.click()
            logger.info("send_message: clicked Message button")
            await asyncio.sleep(2.5)
            logger.info("send_message: after click, url=%s", page.url)

            await ctx.report_progress(progress=60, total=100, message="Typing message")
            # For 1st-degree connections, clicking Message opens a messaging overlay bubble.
            compose = page.locator(".msg-overlay-conversation-bubble .msg-form__contenteditable").first
            try:
                await compose.wait_for(state="visible", timeout=8000)
                logger.info("send_message: compose box found in overlay bubble")
            except Exception as e1:
                logger.warning("send_message: overlay compose not found (%s), trying full-page .msg-form__contenteditable", e1)
                compose = page.locator(".msg-form__contenteditable").first
                try:
                    await compose.wait_for(state="visible", timeout=8000)
                    logger.info("send_message: compose box found via .msg-form__contenteditable")
                except Exception as e2:
                    logger.warning("send_message: .msg-form__contenteditable not found (%s), trying div[contenteditable]", e2)
                    compose = page.locator("div[contenteditable='true']").first
                    await compose.wait_for(state="visible", timeout=5000)
                    logger.info("send_message: compose box found via div[contenteditable='true']")

            await compose.click()
            await page.keyboard.press("Control+a")
            await page.keyboard.type(message, delay=30)
            await asyncio.sleep(0.5)
            logger.info("send_message: message typed")

            await ctx.report_progress(progress=80, total=100, message="Sending")
            # Scope send button search to overlay bubble first, then fall back to full page
            send_btn = page.locator(".msg-overlay-conversation-bubble button.msg-form__send-button").first
            send_btn_count = await send_btn.count()
            logger.info("send_message: overlay send button count=%d", send_btn_count)
            if not send_btn_count:
                send_btn = page.locator("button.msg-form__send-button").first
                send_btn_count = await send_btn.count()
                logger.info("send_message: page send button count=%d", send_btn_count)
            if not send_btn_count:
                send_btn = page.get_by_role("button", name="Send", exact=True).first
                send_btn_count = await send_btn.count()
                logger.info("send_message: 'Send' role button count=%d", send_btn_count)
            await send_btn.click()
            logger.info("send_message: send button clicked")
            await asyncio.sleep(1.5)

            await ctx.report_progress(progress=100, total=100, message="Complete")
            logger.info("send_message: success, message sent to %s", linkedin_username)
            return {
                "status": "success",
                "recipient": linkedin_username,
                "profile_url": profile_url,
                "message_preview": message[:120] + ("…" if len(message) > 120 else ""),
            }

        except Exception as e:
            logger.exception("send_message: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "send_message")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Send Connection Request",
        annotations={"openWorldHint": True},
        tags={"person", "connections"},
    )
    async def send_connection_request(
        linkedin_username: str,
        ctx: Context,
        message: str | None = None,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Send a LinkedIn connection request to a person.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")
            message: Optional note to include with the request (max ~300 chars).
                     If omitted, sends without a note.

        Returns:
            Dict with status, recipient, and optionally message_preview.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to profile")
            browser = await get_or_create_browser()
            page = browser.page

            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            logger.info("send_connection_request: navigating to %s", profile_url)
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=30, total=100, message="Looking for Connect button")

            # Connect button is primary on most profiles; nth(1) skips the hidden sticky header
            connect_btn = page.locator("button.artdeco-button--primary").filter(has_text="Connect").nth(1)
            btn_count = await connect_btn.count()

            if not btn_count:
                # Some profiles (e.g. Follow as primary) bury Connect inside a "More" dropdown
                more_btn = (
                    page.locator("button").filter(has_text="More").nth(1)
                )
                if await more_btn.count():
                    await more_btn.click()
                    await asyncio.sleep(1.0)
                    connect_btn = page.get_by_role("menuitem", name="Connect", exact=True).first
                    btn_count = await connect_btn.count()

            if not btn_count:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
                logger.warning(
                    "send_connection_request: no Connect button on %s body_snippet=%r",
                    profile_url,
                    " ".join(body_text.split())[:300],
                )
                return {
                    "status": "error",
                    "error": "Connect button not found. User may already be a connection, have a pending request, or not allow connection requests.",
                    "profile_url": profile_url,
                }

            await connect_btn.click()
            logger.info("send_connection_request: clicked Connect button")
            await asyncio.sleep(1.5)

            await ctx.report_progress(progress=60, total=100, message="Handling connection modal")

            if message:
                # Click "Add a note" to open the note textarea
                add_note_btn = page.get_by_role("button", name="Add a note", exact=True).first
                if await add_note_btn.count():
                    await add_note_btn.click()
                    await asyncio.sleep(1.0)

                    note_box = page.locator("textarea[name='message']").first
                    await note_box.wait_for(state="visible", timeout=5000)
                    await note_box.click()
                    await page.keyboard.type(message[:300], delay=20)
                    await asyncio.sleep(0.5)
                    logger.info("send_connection_request: note typed")
                else:
                    logger.warning("send_connection_request: 'Add a note' button not found, sending without note")

                await ctx.report_progress(progress=85, total=100, message="Sending")
                send_btn = page.get_by_role("button", name="Send", exact=True).first
            else:
                await ctx.report_progress(progress=85, total=100, message="Sending without note")
                send_btn = page.get_by_role("button", name="Send without a note", exact=True).first
                if not await send_btn.count():
                    send_btn = page.get_by_role("button", name="Send", exact=True).first

            await send_btn.click()
            await asyncio.sleep(1.5)
            logger.info("send_connection_request: sent to %s", linkedin_username)

            await ctx.report_progress(progress=100, total=100, message="Complete")
            result: dict[str, Any] = {
                "status": "success",
                "recipient": linkedin_username,
                "profile_url": profile_url,
            }
            if message:
                result["message_preview"] = message[:120] + ("…" if len(message) > 120 else "")
            return result

        except Exception as e:
            logger.exception("send_connection_request: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "send_connection_request")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Follow Person",
        annotations={"openWorldHint": True},
        tags={"person", "connections"},
    )
    async def follow_person(
        linkedin_username: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Follow a LinkedIn person's profile.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")

        Returns:
            Dict with status and profile_url.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to profile")
            browser = await get_or_create_browser()
            page = browser.page

            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            logger.info("follow_person: navigating to %s", profile_url)
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=40, total=100, message="Looking for Follow button")

            # On creator/influencer profiles Follow is the primary CTA; nth(1) skips the sticky header
            follow_btn = page.locator("button.artdeco-button--primary").filter(has_text="Follow").nth(1)
            btn_count = await follow_btn.count()

            if not btn_count:
                # On regular profiles Follow is inside the "More" dropdown
                more_btn = page.locator("button").filter(has_text="More").nth(1)
                if await more_btn.count():
                    await more_btn.click()
                    await asyncio.sleep(1.0)
                    follow_btn = page.get_by_role("menuitem", name="Follow", exact=True).first
                    btn_count = await follow_btn.count()

            if not btn_count:
                body_text = await page.evaluate("() => document.body?.innerText || ''")
                logger.warning(
                    "follow_person: no Follow button on %s body_snippet=%r",
                    profile_url,
                    " ".join(body_text.split())[:300],
                )
                return {
                    "status": "error",
                    "error": "Follow button not found. You may already follow this person.",
                    "profile_url": profile_url,
                }

            await follow_btn.click()
            logger.info("follow_person: clicked Follow button for %s", linkedin_username)
            await asyncio.sleep(1.0)

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return {
                "status": "success",
                "recipient": linkedin_username,
                "profile_url": profile_url,
            }

        except Exception as e:
            logger.exception("follow_person: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "follow_person")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Check Follow Person",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "connections"},
    )
    async def check_follow(
        linkedin_username: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Check whether we are already following a LinkedIn person.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")

        Returns:
            Dict with following (bool) and profile_url.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to profile")
            browser = await get_or_create_browser()
            page = browser.page

            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=60, total=100, message="Checking follow status")

            # Creator profiles: primary button is "Follow"/"Following"
            following_btn = page.locator("button.artdeco-button--primary").filter(has_text="Following").nth(1)
            if await following_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"following": True, "profile_url": profile_url}

            follow_btn = page.locator("button.artdeco-button--primary").filter(has_text="Follow").nth(1)
            if await follow_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"following": False, "profile_url": profile_url}

            # Regular profiles: Follow/Unfollow lives inside the "More" dropdown
            more_btn = page.locator("button").filter(has_text="More").nth(1)
            if await more_btn.count():
                await more_btn.click()
                await asyncio.sleep(1.0)
                unfollow_item = page.get_by_role("menuitem", name="Unfollow", exact=True).first
                if await unfollow_item.count():
                    # Close the dropdown before returning
                    await page.keyboard.press("Escape")
                    await ctx.report_progress(progress=100, total=100, message="Complete")
                    return {"following": True, "profile_url": profile_url}
                follow_item = page.get_by_role("menuitem", name="Follow", exact=True).first
                if await follow_item.count():
                    await page.keyboard.press("Escape")
                    await ctx.report_progress(progress=100, total=100, message="Complete")
                    return {"following": False, "profile_url": profile_url}
                await page.keyboard.press("Escape")

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return {"following": None, "profile_url": profile_url, "note": "Could not determine follow status"}

        except Exception as e:
            logger.exception("check_follow: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "check_follow")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Check Connection",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"person", "connections"},
    )
    async def check_connection(
        linkedin_username: str,
        ctx: Context,
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Check whether we are connected to a LinkedIn person.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")

        Returns:
            Dict with connected (bool), status ("connected" | "pending" | "not_connected"),
            and profile_url.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to profile")
            browser = await get_or_create_browser()
            page = browser.page

            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=60, total=100, message="Checking connection status")

            # 1st-degree: Message button is the primary CTA
            message_btn = page.locator("button.artdeco-button--primary").filter(has_text="Message").nth(1)
            if await message_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"connected": True, "status": "connected", "profile_url": profile_url}

            # Pending request: primary button reads "Pending"
            pending_btn = page.locator("button").filter(has_text="Pending").nth(1)
            if await pending_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"connected": False, "status": "pending", "profile_url": profile_url}

            # Connect button present (primary or inside More dropdown)
            connect_btn = page.locator("button.artdeco-button--primary").filter(has_text="Connect").nth(1)
            if await connect_btn.count():
                await ctx.report_progress(progress=100, total=100, message="Complete")
                return {"connected": False, "status": "not_connected", "profile_url": profile_url}

            more_btn = page.locator("button").filter(has_text="More").nth(1)
            if await more_btn.count():
                await more_btn.click()
                await asyncio.sleep(1.0)
                connect_item = page.get_by_role("menuitem", name="Connect", exact=True).first
                if await connect_item.count():
                    await page.keyboard.press("Escape")
                    await ctx.report_progress(progress=100, total=100, message="Complete")
                    return {"connected": False, "status": "not_connected", "profile_url": profile_url}
                await page.keyboard.press("Escape")

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return {"connected": None, "status": "unknown", "profile_url": profile_url, "note": "Could not determine connection status"}

        except Exception as e:
            logger.exception("check_connection: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "check_connection")  # NoReturn
