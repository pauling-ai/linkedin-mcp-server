"""
Debug tools for inspecting raw page content and browser state.
"""

import asyncio
import logging
from typing import Any

from fastmcp import Context, FastMCP

from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
from linkedin_mcp_server.error_handler import raise_tool_error

logger = logging.getLogger(__name__)

_EXTRACT_BUTTONS_JS = """
() => Array.from(document.querySelectorAll('button')).map(b => ({
    text: b.innerText.trim(),
    class: b.className,
    aria_label: b.getAttribute('aria-label'),
    disabled: b.disabled,
    outer_html: b.outerHTML.slice(0, 400),
}))
"""

_EXTRACT_MENU_ITEMS_JS = """
() => Array.from(document.querySelectorAll('[role="menuitem"], [role="option"], li[data-control-name]')).map(el => ({
    text: el.innerText.trim(),
    class: el.className,
    aria_label: el.getAttribute('aria-label'),
    role: el.getAttribute('role'),
    outer_html: el.outerHTML.slice(0, 400),
}))
"""


def register_debug_tools(mcp: FastMCP) -> None:
    """Register debug tools with the MCP server."""

    @mcp.tool(
        timeout=TOOL_TIMEOUT_SECONDS,
        title="Get Raw Page",
        annotations={"readOnlyHint": True, "openWorldHint": True},
        tags={"debug"},
    )
    async def get_raw_page(
        url: str,
        ctx: Context,
    ) -> dict[str, Any]:
        """
        Navigate to a URL and return raw page content for debugging.

        Useful for inspecting what buttons, text, and structure LinkedIn
        actually renders — e.g. to debug why a Follow/Connect button isn't found.

        If a "More" button is present, automatically clicks it and captures the
        resulting dropdown menu items before closing the dropdown, so you can
        see what actions are available without having to do it manually.

        Args:
            url: Full URL to load (e.g. "https://www.linkedin.com/in/williamhgates/")

        Returns:
            Dict with:
              - url, title: page metadata
              - text: raw document.body.innerText (no noise stripping)
              - buttons: all buttons with text, class, aria_label, disabled, outer_html
              - more_menu_items: dropdown items found after clicking "More" (if present),
                each with text, class, aria_label, role, outer_html
        """
        try:
            from linkedin_mcp_server.drivers.browser import get_or_create_browser

            await ctx.report_progress(progress=0, total=100, message="Navigating")
            browser = await get_or_create_browser()
            page = browser.page

            await page.goto(url, wait_until="domcontentloaded")
            await asyncio.sleep(2.0)

            await ctx.report_progress(progress=40, total=100, message="Extracting page content")

            title = await page.title()
            text = await page.evaluate("() => document.body.innerText")
            buttons = await page.evaluate(_EXTRACT_BUTTONS_JS)

            # Try to open the "More" dropdown and capture its menu items.
            # nth(1) skips the hidden sticky-header copy, same as the action tools.
            more_menu_items: list[dict] = []
            more_btn = page.locator("button").filter(has_text="More").nth(1)
            if await more_btn.count():
                await ctx.report_progress(progress=70, total=100, message="Opening More dropdown")
                await more_btn.click()
                await asyncio.sleep(1.0)
                more_menu_items = await page.evaluate(_EXTRACT_MENU_ITEMS_JS)
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)

            await ctx.report_progress(progress=100, total=100, message="Complete")

            result: dict[str, Any] = {
                "url": page.url,
                "title": title,
                "text": text,
                "buttons": buttons,
            }
            if more_menu_items:
                result["more_menu_items"] = more_menu_items
            return result

        except Exception as e:
            logger.exception("get_raw_page: unhandled exception for %s", url)
            raise_tool_error(e, "get_raw_page")  # NoReturn
