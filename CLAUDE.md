# LinkedIn MCP Server

Fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) maintained by [pauling-ai](https://github.com/pauling-ai).

## What's custom

- `tools/post.py` — `get_post_likers`: scrapes reactions modal to extract who liked a post
- `tools/person.py` — `send_message`: browser automation to send a message to a 1st-degree connection
- `tools/person.py` — `get_last_post`: fetches the most recent organic post (visits profile first, then `/recent-activity/posts/`); URN fallback for permalink when no anchor tag is rendered
- `tools/utils.py` — `apply_detail_filter` + `BASIC_SECTION_MAX_CHARS`: shared detail-mode helper used by all page-scraping tools
- `scraping/extractor.py` — `scrape_post_likers` and `scrape_last_post` methods

## Key facts

- Browser automation via Patchright (stealth Playwright fork)
- All tool calls are serialized — shared browser session, no parallelism
- Auth profile stored at `~/.linkedin-mcp/profile/`, login with `--login`
- Run with `uv run -m linkedin_mcp_server --slow-mo 500`
- All page-scraping tools default to `detail="basic"` (2000 chars/section). Change `BASIC_SECTION_MAX_CHARS` in `tools/utils.py` to tune globally.
