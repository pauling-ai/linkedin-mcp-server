"""
LinkedIn messaging tools.

Read inbox conversations and individual message threads.
"""

import asyncio
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


def register_messaging_tools(mcp: FastMCP) -> None:
    """Register all messaging-related tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Inbox",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"messaging"},
    )
    async def get_inbox(
        ctx: Context,
        unread_only: bool = False,
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get recent LinkedIn inbox conversations.

        Args:
            ctx: FastMCP context for progress reporting
            unread_only: If True, return only unread conversations.
            output: Controls how the scraped data is delivered back to the caller.
                **CRITICAL TOKEN EFFICIENCY:** Use output="file" whenever possible to save the full result to a local JSON file and return a lightweight summary. This significantly reduces token consumption and prevents context window limits. Only use "inline" when the LLM must perform immediate, small-scale analysis on the exact text.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: conversation count and first few contact names

                    Use "file" when exporting the inbox or processing many
                    conversations without needing to parse each one inline.
                    The caller can read the file later if deeper analysis is
                    needed.

        Returns:
            When output="inline":
                Dict with conversations list. Each conversation has:
                - name: display name of the other person
                - username: LinkedIn username (if extractable from thread URL)
                - preview: last message snippet
                - timestamp: relative time string (e.g. "2h", "Mar 15")
                - unread: bool
                - thread_url: relative URL to the thread (e.g. "/messaging/thread/2-abc123/")
            When output="file":
                Dict with output="file", file (absolute path), and preview
                (conversation count and first few names).  The full conversation
                list is in the JSON file at the given path.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Opening inbox")
            browser = await get_or_create_browser()
            page = browser.page

            await page.goto(
                "https://www.linkedin.com/messaging/",
                wait_until="domcontentloaded",
            )
            await asyncio.sleep(3.0)

            await ctx.report_progress(progress=50, total=100, message="Extracting conversations")

            conversations = await page.evaluate("""() => {
                const results = [];
                const seen = new Set();

                // LinkedIn uses several class name patterns across versions
                const items = [
                    ...document.querySelectorAll('.msg-conversation-listitem'),
                    ...document.querySelectorAll('[data-view-name="message-list-item"]'),
                ];

                for (const item of items) {
                    const link = item.querySelector('a[href*="/messaging/thread/"]')
                        || (item.matches('a[href*="/messaging/thread/"]') ? item : null);
                    const href = link?.getAttribute('href') || '';
                    if (!href || seen.has(href)) continue;
                    seen.add(href);

                    // Name: first line of participant names element
                    const nameEl = item.querySelector(
                        '.msg-conversation-listitem__participant-names, [class*="participant-names"]'
                    );
                    const name = (nameEl?.innerText || '').split('\\n')[0].trim();

                    // Message preview
                    const previewEl = item.querySelector(
                        '.msg-conversation-listitem__message-snippet, [class*="message-snippet"]'
                    );
                    const preview = (previewEl?.innerText || '').trim();

                    // Timestamp
                    const timeEl = item.querySelector('time');
                    const timestamp = timeEl?.getAttribute('datetime')
                        || timeEl?.innerText?.trim() || '';

                    // Unread: bold name or explicit unread class/badge
                    const isUnread =
                        item.classList.contains('msg-conversation-listitem--is-unread')
                        || !!item.querySelector('.msg-conversation-listitem__unread-count')
                        || !!item.querySelector('[class*="unread-count"]');

                    results.push({ name, preview, timestamp, unread: isUnread, thread_url: href });
                }
                return results;
            }""")

            # Try to extract LinkedIn username from the thread member URL embedded
            # in each conversation item's participant link
            enriched = []
            for conv in conversations:
                username = await page.evaluate(
                    """(threadHref) => {
                        const link = document.querySelector(
                            `a[href="${threadHref}"] [href*="/in/"], a[href="${threadHref}"] ~ * a[href*="/in/"]`
                        );
                        if (!link) return null;
                        const m = link.getAttribute('href').match(/\\/in\\/([^/?#]+)/);
                        return m ? m[1] : null;
                    }""",
                    conv["thread_url"],
                )
                if username:
                    conv["username"] = username
                enriched.append(conv)

            if unread_only:
                enriched = [c for c in enriched if c.get("unread")]

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return format_tool_output(
                {"conversations": enriched}, "get_inbox", output
            )

        except Exception as e:
            raise_tool_error(e, "get_inbox")  # NoReturn

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Conversation",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"messaging"},
    )
    async def get_conversation(
        linkedin_username: str,
        ctx: Context,
        output: Literal["inline", "file"] = "inline",
        extractor: LinkedInExtractor = Depends(get_extractor),
    ) -> dict[str, Any]:
        """
        Get the message thread with a specific LinkedIn connection.

        Navigates to the person's profile, opens the messaging overlay,
        and extracts the conversation history.

        Args:
            linkedin_username: LinkedIn username (e.g., "jtordable", "williamhgates")
            output: Controls how the scraped data is delivered back to the caller.
                **CRITICAL TOKEN EFFICIENCY:** Use output="file" whenever possible to save the full result to a local JSON file and return a lightweight summary. This significantly reduces token consumption and prevents context window limits. Only use "inline" when the LLM must perform immediate, small-scale analysis on the exact text.
                "inline" (default): the full result dict is returned directly in
                    the MCP response.
                "file": the full result is saved as a JSON file in the current
                    working directory (the caller's project directory), and only
                    a lightweight summary is returned.  The summary contains:
                    - file: absolute path to the JSON file
                    - preview: message count and the latest message snippet

                    Use "file" when exporting a conversation or when the caller
                    only needs to store the thread without parsing every message
                    inline.  The caller can read the file later if deeper
                    analysis is needed.

        Returns:
            When output="inline":
                Dict with linkedin_username, profile_url, and messages list.
                Each message has: sender ("me" or display name), text, and timestamp.
            When output="file":
                Dict with output="file", file (absolute path), and preview
                (message count and latest message snippet).  The full message
                list is in the JSON file at the given path.
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating to profile")
            browser = await get_or_create_browser()
            page = browser.page

            profile_url = f"https://www.linkedin.com/in/{linkedin_username}/"
            await page.goto(profile_url, wait_until="domcontentloaded")
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=30, total=100, message="Opening message thread")

            # Click the primary Message button (same approach as send_message)
            message_btn = (
                page.locator("button.artdeco-button--primary")
                .filter(has_text="Message")
                .nth(1)
            )
            if not await message_btn.count():
                return {
                    "status": "error",
                    "error": "Message button not found. User may not be a 1st-degree connection.",
                    "profile_url": profile_url,
                }

            await message_btn.click()
            await asyncio.sleep(2.5)

            await ctx.report_progress(progress=60, total=100, message="Reading messages")

            # The overlay or full-page messaging view should now be open
            messages = await page.evaluate("""() => {
                const results = [];

                // Try overlay bubble first, then full-page messaging
                const containers = [
                    document.querySelector('.msg-overlay-conversation-bubble .msg-s-message-list'),
                    document.querySelector('.msg-s-message-list'),
                ];
                const list = containers.find(Boolean);
                if (!list) return results;

                let currentSender = null;
                let currentTime = null;

                for (const node of list.children) {
                    // Message group header carries sender name + timestamp
                    const nameEl = node.querySelector('.msg-s-message-group__name');
                    const timeEl = node.querySelector('time');
                    if (nameEl) currentSender = nameEl.innerText.trim();
                    if (timeEl) {
                        currentTime = timeEl.getAttribute('datetime')
                            || timeEl.innerText?.trim() || null;
                    }

                    // Each message body inside this group
                    const bodies = node.querySelectorAll('.msg-s-event-listitem__body');
                    for (const body of bodies) {
                        const text = body.innerText?.trim();
                        if (!text) continue;
                        results.push({
                            sender: currentSender || 'me',
                            text,
                            timestamp: currentTime || '',
                        });
                    }
                }
                return results;
            }""")

            # If no messages found via structured extraction, fall back to innerText
            if not messages:
                raw = await page.evaluate("""() => {
                    const el = document.querySelector(
                        '.msg-overlay-conversation-bubble .msg-s-message-list, .msg-s-message-list'
                    );
                    return el?.innerText?.trim() || '';
                }""")
                logger.warning(
                    "get_conversation: structured extraction empty for %s, raw length=%d",
                    linkedin_username,
                    len(raw),
                )
                return format_tool_output(
                    {
                        "linkedin_username": linkedin_username,
                        "profile_url": profile_url,
                        "messages_raw": raw,
                    },
                    "get_conversation",
                    output,
                )

            await ctx.report_progress(progress=100, total=100, message="Complete")
            return format_tool_output(
                {
                    "linkedin_username": linkedin_username,
                    "profile_url": profile_url,
                    "messages": messages,
                },
                "get_conversation",
                output,
            )

        except Exception as e:
            logger.exception("get_conversation: unhandled exception for %s", linkedin_username)
            raise_tool_error(e, "get_conversation")  # NoReturn
