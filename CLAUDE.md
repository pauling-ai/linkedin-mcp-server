# LinkedIn MCP Server

Fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) maintained by [pauling-ai](https://github.com/pauling-ai).

## What's custom

- `tools/post.py` — `get_post_likers`: scrapes reactions modal to extract who liked a post
- `tools/person.py` — `send_message`: browser automation to send a message to a 1st-degree connection
- `scraping/extractor.py` — `scrape_post_likers` method supporting the above

## Key facts

- Browser automation via Patchright (stealth Playwright fork)
- All tool calls are serialized — shared browser session, no parallelism
- Auth profile stored at `~/.linkedin-mcp/profile/`, login with `--login`
- Run with `uv run -m linkedin_mcp_server --slow-mo 500`
