"""Utility functions for scraping operations."""

import asyncio
import logging
import random

from patchright.async_api import Page, TimeoutError as PlaywrightTimeoutError

from linkedin_mcp_server.config import get_config

logger = logging.getLogger(__name__)


def get_human_delay_seconds() -> float:
    """Return a randomized human-like delay based on browser config."""
    browser = get_config().browser
    minimum = browser.human_delay_min_ms / 1000
    maximum = browser.human_delay_max_ms / 1000
    return random.uniform(minimum, maximum)


def get_linkedin_call_delay_seconds() -> float:
    """Return randomized pacing delay before a LinkedIn MCP tool call."""
    browser = get_config().browser
    baseline = browser.linkedin_call_delay_ms / 1000
    jitter = browser.linkedin_call_delay_jitter_ms / 1000
    minimum = max(0.0, baseline - jitter)
    maximum = baseline + jitter
    return random.uniform(minimum, maximum)


async def sleep_human_delay() -> float:
    """Sleep for a randomized human-like delay and return the chosen duration."""
    delay = get_human_delay_seconds()
    await asyncio.sleep(delay)
    return delay


async def sleep_linkedin_call_delay() -> float:
    """Sleep before a LinkedIn MCP tool call and return the chosen duration."""
    delay = get_linkedin_call_delay_seconds()
    if delay > 0:
        await asyncio.sleep(delay)
    return delay


async def scroll_to_bottom(
    page: Page, pause_time: float = 1.0, max_scrolls: int = 10
) -> None:
    """Scroll to the bottom of the page to trigger lazy loading.

    Args:
        page: Patchright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
    """
    for i in range(max_scrolls):
        previous_height = await page.evaluate("document.body.scrollHeight")
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(pause_time)

        new_height = await page.evaluate("document.body.scrollHeight")
        if new_height == previous_height:
            logger.debug("Reached bottom after %d scrolls", i + 1)
            break


async def scroll_job_sidebar(
    page: Page, pause_time: float = 1.0, max_scrolls: int = 10
) -> None:
    """Scroll the job search sidebar to load all job cards.

    LinkedIn renders job search results in a scrollable sidebar container,
    not the main page body. This function finds that container by locating
    a job card link and walking up to its scrollable ancestor, then scrolls
    it iteratively until no new content loads.

    Args:
        page: Patchright page object
        pause_time: Time to pause between scrolls (seconds)
        max_scrolls: Maximum number of scroll attempts
    """
    # Wait for at least one job card link to render before scrolling
    try:
        await page.wait_for_selector('a[href*="/jobs/view/"]', timeout=5000)
    except PlaywrightTimeoutError:
        logger.debug("No job card links found, skipping sidebar scroll")
        return

    scrolled = await page.evaluate(
        """async ({pauseTime, maxScrolls}) => {
            const link = document.querySelector('a[href*="/jobs/view/"]');
            if (!link) return -2;

            let container = link.parentElement;
            while (container && container !== document.body) {
                const style = window.getComputedStyle(container);
                const overflowY = style.overflowY;
                if ((overflowY === 'auto' || overflowY === 'scroll')
                    && container.scrollHeight > container.clientHeight) {
                    break;
                }
                container = container.parentElement;
            }

            if (!container || container === document.body) {
                return -1;
            }

            let scrollCount = 0;
            for (let i = 0; i < maxScrolls; i++) {
                const prevHeight = container.scrollHeight;
                container.scrollTop = container.scrollHeight;
                await new Promise(r => setTimeout(r, pauseTime * 1000));
                if (container.scrollHeight === prevHeight) break;
                scrollCount++;
            }
            return scrollCount;
        }""",
        {"pauseTime": pause_time, "maxScrolls": max_scrolls},
    )
    if scrolled == -2:
        logger.debug("Job card link disappeared before evaluate, skipping scroll")
    elif scrolled == -1:
        logger.debug("No scrollable container found for job sidebar")
    elif scrolled:
        logger.debug("Scrolled job sidebar %d times", scrolled)
    else:
        logger.debug("Job sidebar container found but no new content loaded")


async def handle_modal_close(page: Page) -> bool:
    """Close any popup modals that might be blocking content.

    Returns:
        True if a modal was closed, False otherwise
    """
    try:
        close_button = page.locator(
            'button[aria-label="Dismiss"], '
            'button[aria-label="Close"], '
            "button.artdeco-modal__dismiss"
        ).first

        if await close_button.is_visible(timeout=1000):
            await close_button.click()
            await asyncio.sleep(0.5)
            logger.debug("Closed modal")
            return True
    except PlaywrightTimeoutError:
        pass
    except Exception as e:
        logger.debug("Error closing modal: %s", e)

    return False
