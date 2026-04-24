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
| `get_company_posts` | Get recent posts from a company's feed; returns post URNs plus lightweight `posts[]` metadata including `posted_at`. Supports `detail` param. |
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
      "args": ["--project-auth", "--delay-between-linkedin-calls", "1.5", "--delay-jitter", "0.5"],
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
      "args": ["--directory", "/path/to/linkedin-mcp-server", "run", "-m", "linkedin_mcp_server", "--project-auth", "--delay-between-linkedin-calls", "1.5", "--delay-jitter", "0.5"],
      "env": {
        "LOG_LEVEL": "INFO"
      }
    }
  }
}
```

The `uv` approach is the simplest — just update the `--directory` path and you're done.

Use `--slow-mo` only when debugging or when you want to watch browser actions happen more slowly. For LinkedIn-facing pacing between tool calls, prefer `--delay-between-linkedin-calls` / `--delay-jitter`. The smaller `--human-delay-min-ms` / `--human-delay-max-ms` settings still control waits inside individual browser workflows.

If you want a separate LinkedIn account per repo on the same machine, start the server with `--project-auth`. That stores the auth state under the current project in `.linkedin-mcp-server/` instead of the shared `~/.linkedin-mcp/` location.

## CLI Options

- `--login` - Open browser to log in and save persistent profile
- `--logout` - Clear stored LinkedIn browser profile
- `--status` - Check if current session is valid and exit
- `--no-headless` - Show browser window (useful for debugging)
- `--project-auth` - Store auth under the current project at `.linkedin-mcp-server/`
- `--slow-mo MS` - Debugging aid: slows all browser actions uniformly in ms (default: 0)
- `--human-delay-min-ms MS` - Minimum randomized delay between LinkedIn actions (default: 500)
- `--human-delay-max-ms MS` - Maximum randomized delay between LinkedIn actions (default: 2000)
- `--delay-between-linkedin-calls SECONDS` - Baseline delay before each LinkedIn MCP tool call (default: 1.5)
- `--delay-jitter SECONDS` - Random jitter added/subtracted from tool-call delay (default: 0.5)
- `--linkedin-cache-dir PATH` - Override cache root (default: beside auth profile)
- `--disable-linkedin-cache` - Disable LinkedIn tool result caching
- `--profile-cache-ttl-hours HOURS` - TTL for cached person profiles (default: 720 / 30 days)
- `--log-level {DEBUG,INFO,WARNING,ERROR}` - Logging level (default: WARNING)
- `--timeout MS` - Browser timeout for page operations in ms (default: 5000)
- `--transport {stdio,streamable-http}` - Transport mode (default: stdio)

## Troubleshooting

**Session expired:** Run `uv run -m linkedin_mcp_server --login` again.

**Login issues:** LinkedIn may require confirmation in the mobile app, or show a captcha — the `--login` browser window lets you handle these manually.

**Scraping issues:** Use `--no-headless` to watch the browser and `--log-level DEBUG` for detailed logs.

**Timeout issues:** Increase with `--timeout 10000` or env var `TIMEOUT=10000`.

**Tool-call pacing:** Tune with `--delay-between-linkedin-calls` / `--delay-jitter` or env vars `LINKEDIN_CALL_DELAY_MS` / `LINKEDIN_CALL_DELAY_JITTER_MS`. Defaults are `1.5 ± 0.5` seconds, so each LinkedIn MCP tool call starts after roughly 1-2 seconds.

**In-tool pacing:** Tune with `--human-delay-min-ms` / `--human-delay-max-ms` or env vars `HUMAN_DELAY_MIN_MS` / `HUMAN_DELAY_MAX_MS`. These are smaller pauses inside a tool workflow, e.g. after navigation or clicks.

**Profile caching:** `get_person_profile` caches raw profile scrape results for 720 hours by default. The cache is shared across sessions beside the auth profile: `~/.linkedin-mcp/cache/profiles/` by default, or `.linkedin-mcp-server/cache/profiles/` when using `--project-auth`. Use `force_refresh=true` on the tool call to bypass cache for one profile. Requests that include the `posts` section are not cached, so competitor post discovery stays fresh. Use `--profile-cache-ttl-hours`, `--linkedin-cache-dir`, or `--disable-linkedin-cache` to tune globally. Env vars: `LINKEDIN_PROFILE_CACHE_TTL_HOURS`, `LINKEDIN_CACHE_DIR`, `LINKEDIN_CACHE_DISABLED`.

**`slow_mo` vs pacing delays:** `--slow-mo` / `SLOW_MO` is mainly for debugging because it slows nearly every browser action. Prefer the tool-call and in-tool pacing settings for normal runs.

**Per-project LinkedIn accounts:** Use `--project-auth` or env var `PROJECT_AUTH=true`. The login flow will then create:

- `.linkedin-mcp-server/profile/` for the persistent browser profile
- `.linkedin-mcp-server/cookies.json`
- `.linkedin-mcp-server/source-state.json`
- `.linkedin-mcp-server/runtime-profiles/` for derived runtime sessions

**`send_message` / `get_conversation` not finding the Message button:** The target user must be a 1st-degree connection. The tool returns an error with diagnostic info if the button isn't found.

**`send_connection_request` not finding the Connect button:** The user may already be a connection, have a pending request, or not allow connection requests. If Connect is hidden behind a More dropdown, the tool handles this automatically.

## Notes

- Browser profile stored at `~/.linkedin-mcp/profile/`
- Tool calls are serialized — concurrent requests queue rather than run in parallel
- Use in accordance with [LinkedIn's Terms of Service](https://www.linkedin.com/legal/user-agreement)

## License

Apache 2.0 — see [LICENSE](LICENSE)
