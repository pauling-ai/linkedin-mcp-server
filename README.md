# LinkedIn MCP Server (Fork)

Personal fork of [stickerdaniel/linkedin-mcp-server](https://github.com/stickerdaniel/linkedin-mcp-server) with additional tools for messaging and post engagement.

## Added Tools

| Tool | Description |
|------|-------------|
| `send_message` | Send a LinkedIn message to a 1st-degree connection |
| `send_connection_request` | Send a connection request, with or without a note |
| `follow_company` | Follow a LinkedIn company page |
| `get_inbox` | Read recent inbox conversations (supports `unread_only`) |
| `get_conversation` | Read the full message thread with a specific person |
| `get_post_likers` | Get the list of people who reacted to a LinkedIn post |
| `get_last_post` | Get the most recent organic post from a person's profile |

## Detail Mode

All page-scraping tools (`get_person_profile`, `search_people`, `get_company_profile`, `get_company_posts`, `get_job_details`, `search_jobs`) accept a `detail` parameter:

- `"basic"` (default) — truncates each section's raw text to `BASIC_SECTION_MAX_CHARS` (2000 chars). LinkedIn front-loads the most important content (name, headline, location, about), so this captures essentials while staying well within LLM context limits. References, job IDs, and post URNs are always kept.
- `"full"` — returns the complete raw page text, current behaviour.

If basic mode doesn't return enough information, call the tool again with `detail="full"`.

The truncation limit is a single constant in `linkedin_mcp_server/tools/utils.py`:

```python
BASIC_SECTION_MAX_CHARS = 2000
```

## All Tools

### People
| Tool | Description |
|------|-------------|
| `get_person_profile` | Get profile info with optional sections: `experience`, `education`, `interests`, `honors`, `languages`, `contact_info`, `posts`. Supports `detail` param. |
| `search_people` | Search for people by keywords and optional location. Supports `detail` param. |
| `get_last_post` | Get the most recent organic post from a person (visits profile first, then Posts activity tab; returns text, timestamp, URL, and URN) |
| `send_connection_request` | Send a connection request, with or without a note (~300 char limit); handles profiles where Connect is in the More dropdown |
| `send_message` | Send a message to a 1st-degree connection (also used to reply to existing threads) |
| `follow_person` | Follow a person's profile |
| `check_follow` | Check whether you are following a person |
| `check_connection` | Check whether you are connected to a person |

### Companies
| Tool | Description |
|------|-------------|
| `get_company_profile` | Get company info with optional sections: `posts`, `jobs`. Supports `detail` param. |
| `get_company_posts` | Get recent posts from a company's feed; returns post URNs for further use. Supports `detail` param. |
| `follow_company` | Follow a company page |
| `check_follow_company` | Check whether you are following a company |

### Jobs
| Tool | Description |
|------|-------------|
| `search_jobs` | Search for jobs by keywords and optional location. Supports `detail` param. |
| `get_job_details` | Get full details of a specific job posting. Supports `detail` param. |

### Messaging
| Tool | Description |
|------|-------------|
| `get_inbox` | List recent inbox conversations with name, preview, timestamp, and unread flag; pass `unread_only=true` to filter |
| `get_conversation` | Read the full message thread with a person by their LinkedIn username |

### Posts
| Tool | Description |
|------|-------------|
| `get_post_likers` | Get the list of people who reacted to a post (by feed URL or post URN) |
| `get_last_post` | Get the most recent organic post from a person (no likes, no reshares) |

### Session
| Tool | Description |
|------|-------------|
| `close_session` | Close the browser session and clean up resources |

## Setup

**Prerequisites:** Python 3.12+ and [uv](https://docs.astral.sh/uv/) installed

```bash
# 1. Clone the repo
git clone https://github.com/pauling-ai/linkedin-mcp-server
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

**`send_message` / `get_conversation` not finding the Message button:** The target user must be a 1st-degree connection. The tool returns an error with diagnostic info if the button isn't found.

**`send_connection_request` not finding the Connect button:** The user may already be a connection, have a pending request, or not allow connection requests. If Connect is hidden behind a More dropdown, the tool handles this automatically.

## Notes

- Browser profile stored at `~/.linkedin-mcp/profile/`
- Tool calls are serialized — concurrent requests queue rather than run in parallel
- Use in accordance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement)

## License

Apache 2.0 — see [LICENSE](LICENSE)
