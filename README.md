# LinkedIn MCP Server (Fork)

Personal fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) with additional tools for messaging and post engagement.

## Added Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send a LinkedIn message to a 1st-degree connection |
| `get_post_likers` | Get the list of people who reacted to a LinkedIn post |

## All Tools

| Tool | Description |
|------|-------------|
| `get_person_profile` | Get profile info with optional section selection (experience, education, interests, honors, languages, contact_info, posts) |
| `get_company_profile` | Extract company information with optional section selection (posts, jobs) |
| `get_company_posts` | Get recent posts from a company's LinkedIn feed |
| `search_people` | Search for people by keywords and location |
| `search_jobs` | Search for jobs with keywords and location filters |
| `get_job_details` | Get detailed information about a specific job posting |
| `get_post_likers` | Get the list of people who reacted to a LinkedIn post |
| `send_message` | Send a LinkedIn message to a 1st-degree connection |
| `close_session` | Close browser session and clean up resources |

## Setup

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/) installed

```bash
# 1. Clone the repo
git clone https://github.com/jtordable/linkedin-mcp-server
cd linkedin-mcp-server

# 2. Install dependencies
uv sync

# 3. Install Patchright browser
uv run patchright install chromium

# 4. Log in (first time only)
uv run -m linkedin_mcp_server --login
```

This opens a browser for you to log in manually (5 minute timeout for 2FA, captcha, etc.). The browser profile is saved to `~/.linkedin-mcp/profile/` and persists across sessions.

## Installing into another project

To use this server from another Python project or Claude Code workspace, install it in editable mode pointing at your local clone:

```bash
# With uv (recommended)
uv pip install -e /path/to/linkedin-mcp-server

# Or with pip
pip install -e /path/to/linkedin-mcp-server
```

Editable mode means changes to the repo are immediately reflected — no reinstall needed.

Then point your MCP config at the installed binary:

```bash
# Find the installed binary path
which linkedin-scraper-mcp
```

## Claude Code / MCP Configuration

After installing (either in a project venv or globally), add to your `.mcp.json`:

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "/path/to/venv/bin/linkedin-scraper-mcp",
      "args": ["--slow-mo", "500"],
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

Or run directly from the repo with `uv` (no install needed):

```json
{
  "mcpServers": {
    "linkedin": {
      "command": "uv",
      "args": ["--directory", "/path/to/linkedin-mcp-server", "run", "-m", "linkedin_mcp_server", "--slow-mo", "500"],
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

The `uv` approach is the simplest — just update the `--directory` path and you're done.

## CLI Options

- `--login` - Open browser to log in and save persistent profile
- `--logout` - Clear stored LinkedIn browser profile
- `--status` - Check if current session is valid and exit
- `--no-headless` - Show browser window (useful for debugging)
- `--slow-mo MS` - Delay between browser actions in ms (default: 0)
- `--log-level {DEBUG,INFO,WARNING,ERROR}` - Logging level (default: WARNING)
- `--timeout MS` - Browser timeout for page operations in ms (default: 5000)
- `--transport {stdio,streamable-http}` - Transport mode (default: stdio)

## Troubleshooting

**Session expired:** Run `uv run -m linkedin_mcp_server --login` again.

**Login issues:** LinkedIn may require confirmation in the mobile app, or show a captcha — the `--login` browser window lets you handle these manually.

**Scraping issues:** Use `--no-headless` to watch the browser and `--log-level DEBUG` for detailed logs.

**Timeout issues:** Increase with `--timeout 10000` or env var `TIMEOUT=10000`.

**`send_message` not finding the Message button:** The target user must be a 1st-degree connection. The tool will return an error with diagnostic info if the button isn't found.

## Notes

- Browser profile stored at `~/.linkedin-mcp/profile/`
- Tool calls are serialized — concurrent requests queue rather than run in parallel
- Use in accordance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement)

## License

Apache 2.0 — see [LICENSE](LICENSE)
