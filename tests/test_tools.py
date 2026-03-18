from typing import Any, Callable, Coroutine
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

from linkedin_mcp_server.scraping.extractor import ExtractedSection


async def get_tool_fn(
    mcp: FastMCP, name: str
) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
    """Extract tool function from FastMCP by name using public API."""
    tool = await mcp.get_tool(name)
    if tool is None:
        raise ValueError(f"Tool '{name}' not found")
    return tool.fn  # type: ignore[attr-defined]


def _make_mock_extractor(scrape_result: dict) -> MagicMock:
    """Create a mock LinkedInExtractor that returns the given result."""
    mock = MagicMock()
    mock.scrape_person = AsyncMock(return_value=scrape_result)
    mock.scrape_company = AsyncMock(return_value=scrape_result)
    mock.scrape_job = AsyncMock(return_value=scrape_result)
    mock.search_jobs = AsyncMock(return_value=scrape_result)
    mock.search_people = AsyncMock(return_value=scrape_result)
    mock.extract_page = AsyncMock(
        return_value=ExtractedSection(text="some text", references=[])
    )
    return mock


class TestPersonTool:
    async def test_get_person_profile_success(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/in/test-user/",
            "sections": {"main_profile": "John Doe\nSoftware Engineer"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn("test-user", mock_context, extractor=mock_extractor)
        assert result["url"] == "https://www.linkedin.com/in/test-user/"
        assert "main_profile" in result["sections"]
        assert "pages_visited" not in result
        assert "sections_requested" not in result

    async def test_get_person_profile_with_sections(self, mock_context):
        """Verify sections parameter is passed through."""
        expected = {
            "url": "https://www.linkedin.com/in/test-user/",
            "sections": {
                "main_profile": "John Doe",
                "experience": "Work history",
                "contact_info": "Email: test@test.com",
            },
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn(
            "test-user",
            mock_context,
            sections="experience,contact_info",
            extractor=mock_extractor,
        )
        assert "main_profile" in result["sections"]
        assert "experience" in result["sections"]
        assert "contact_info" in result["sections"]
        # Verify scrape_person was called exactly once with a set[str]
        mock_extractor.scrape_person.assert_awaited_once()
        call_args = mock_extractor.scrape_person.call_args
        assert isinstance(call_args[0][1], set)
        assert "experience" in call_args[0][1]
        assert "contact_info" in call_args[0][1]

    async def test_get_person_profile_unknown_section(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/in/test-user/",
            "sections": {"main_profile": "John Doe"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        result = await tool_fn(
            "test-user",
            mock_context,
            sections="bogus_section",
            extractor=mock_extractor,
        )
        assert result["unknown_sections"] == ["bogus_section"]

    async def test_get_person_profile_error(self, mock_context):
        from fastmcp.exceptions import ToolError

        from linkedin_mcp_server.exceptions import SessionExpiredError

        mock_extractor = MagicMock()
        mock_extractor.scrape_person = AsyncMock(side_effect=SessionExpiredError())

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_person_profile")
        with pytest.raises(ToolError, match="Session expired"):
            await tool_fn("test-user", mock_context, extractor=mock_extractor)

    async def test_get_person_profile_auth_error(self, monkeypatch):
        """Auth failures in the DI layer produce proper ToolError responses."""
        from fastmcp.exceptions import ToolError

        from linkedin_mcp_server.core.exceptions import AuthenticationError

        mock_browser = MagicMock()
        mock_browser.page = MagicMock()
        monkeypatch.setattr(
            "linkedin_mcp_server.dependencies.get_or_create_browser",
            AsyncMock(return_value=mock_browser),
        )
        monkeypatch.setattr(
            "linkedin_mcp_server.dependencies.ensure_authenticated",
            AsyncMock(side_effect=AuthenticationError("Session expired or invalid.")),
        )

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        with pytest.raises(ToolError, match="Authentication failed"):
            await mcp.call_tool("get_person_profile", {"linkedin_username": "test"})

    async def test_search_people(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/search/results/people/?keywords=AI+engineer&location=New+York",
            "sections": {"search_results": "Jane Doe\nAI Engineer at Acme\nNew York"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "search_people")
        result = await tool_fn(
            "AI engineer", mock_context, location="New York", extractor=mock_extractor
        )
        assert "search_results" in result["sections"]
        assert "pages_visited" not in result
        mock_extractor.search_people.assert_awaited_once_with("AI engineer", "New York")


class TestCompanyTools:
    async def test_get_company_profile(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/company/testcorp/",
            "sections": {"about": "TestCorp\nWe build things"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_profile")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert "about" in result["sections"]
        assert "pages_visited" not in result

    async def test_get_company_profile_unknown_section(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/company/testcorp/",
            "sections": {"about": "TestCorp\nWe build things"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_profile")
        result = await tool_fn(
            "testcorp", mock_context, sections="bogus", extractor=mock_extractor
        )
        assert result["unknown_sections"] == ["bogus"]

    async def test_get_company_posts(self, mock_context):
        mock_extractor = MagicMock()
        mock_extractor.extract_page = AsyncMock(
            return_value=ExtractedSection(text="Post 1\nPost 2", references=[])
        )
        mock_extractor.extract_post_urns = AsyncMock(return_value=[])

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_posts")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert "posts" in result["sections"]
        assert result["sections"]["posts"] == "Post 1\nPost 2"
        assert "pages_visited" not in result
        assert "sections_requested" not in result

    async def test_get_company_posts_returns_post_urns(self, mock_context):
        mock_extractor = MagicMock()
        mock_extractor.extract_page = AsyncMock(
            return_value=ExtractedSection(text="Post 1\nPost 2", references=[])
        )
        mock_extractor.extract_post_urns = AsyncMock(
            return_value=[
                "urn:li:activity:7439961861053157377",
                "urn:li:activity:1111111111111111111",
            ]
        )

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_posts")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert result["post_urns"] == [
            "urn:li:activity:7439961861053157377",
            "urn:li:activity:1111111111111111111",
        ]

    async def test_get_company_posts_omits_empty_text(self, mock_context):
        mock_extractor = MagicMock()
        mock_extractor.extract_page = AsyncMock(
            return_value=ExtractedSection(text="", references=[])
        )
        mock_extractor.extract_post_urns = AsyncMock(return_value=[])

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_posts")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert result["sections"] == {}

    async def test_get_company_posts_returns_section_errors(self, mock_context):
        mock_extractor = MagicMock()
        mock_extractor.extract_page = AsyncMock(
            return_value=ExtractedSection(
                text="",
                references=[],
                error={"issue_template_path": "/tmp/company-posts-issue.md"},
            )
        )
        mock_extractor.extract_post_urns = AsyncMock(return_value=[])

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_posts")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert result["sections"] == {}
        assert result["section_errors"]["posts"]["issue_template_path"] == (
            "/tmp/company-posts-issue.md"
        )

    async def test_get_company_posts_omits_orphaned_references(self, mock_context):
        mock_extractor = MagicMock()
        mock_extractor.extract_page = AsyncMock(
            return_value=ExtractedSection(
                text="",
                references=[
                    {
                        "kind": "company",
                        "url": "/company/testcorp/",
                        "text": "TestCorp",
                    }
                ],
            )
        )
        mock_extractor.extract_post_urns = AsyncMock(return_value=[])

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_company_posts")
        result = await tool_fn("testcorp", mock_context, extractor=mock_extractor)
        assert result["sections"] == {}
        assert "references" not in result


class TestFollowCompany:
    def _make_page_mock(self, btn_count: int):
        mock_btn = MagicMock()
        mock_btn.count = AsyncMock(return_value=btn_count)
        mock_btn.click = AsyncMock()

        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        # chain: locator("button").filter(has_text="Follow").first → mock_btn
        mock_page.locator.return_value.filter.return_value.first = mock_btn
        return mock_page, mock_btn

    async def test_follow_company_success(self, mock_context):
        mock_page, mock_btn = self._make_page_mock(btn_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "follow_company")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.company.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("anthropic", mock_context, extractor=mock_extractor)

        assert result["status"] == "success"
        assert "anthropic" in result["company_url"]
        mock_btn.click.assert_awaited_once()

    async def test_follow_company_button_not_found(self, mock_context):
        mock_page, _ = self._make_page_mock(btn_count=0)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "follow_company")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.company.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("anthropic", mock_context, extractor=mock_extractor)

        assert result["status"] == "error"
        assert "Follow button not found" in result["error"]


class TestSendConnectionRequest:
    def _make_page_mock(
        self,
        connect_btn_count=1,
        more_btn_count=0,
        menuitem_connect_count=0,
        add_note_count=1,
        send_btn_count=1,
    ):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="")
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.type = AsyncMock()

        def make_btn(count):
            b = MagicMock()
            b.count = AsyncMock(return_value=count)
            b.click = AsyncMock()
            b.wait_for = AsyncMock()
            return b

        def wrap(btn):
            loc = MagicMock()
            loc.first = btn
            return loc

        connect_btn = make_btn(connect_btn_count)
        more_btn = make_btn(more_btn_count)
        menuitem_connect = make_btn(menuitem_connect_count)
        add_note_btn = make_btn(add_note_count)
        send_btn = make_btn(send_btn_count)
        note_box = make_btn(1)
        no_btn = make_btn(0)

        # Distinguish locator calls by selector string
        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button.artdeco-button--primary":
                # .filter(...).nth(1) → connect_btn
                loc.filter.return_value.nth.return_value = connect_btn
            elif selector == "button":
                # .filter(has_text="More").nth(1) → more_btn
                loc.filter.return_value.nth.return_value = more_btn
                # .filter(has_text="Follow").first → no_btn (follow_company uses this)
                loc.filter.return_value.first = no_btn
            elif selector == "textarea[name='message']":
                loc.first = note_box
            else:
                loc.first = no_btn
                loc.filter.return_value.nth.return_value = no_btn
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        mock_page.get_by_role = MagicMock(side_effect=lambda role, **kw: {
            "Add a note": wrap(add_note_btn),
            "Send": wrap(send_btn),
            "Send without a note": wrap(send_btn),
            "Connect": wrap(menuitem_connect),
        }.get(kw.get("name"), wrap(no_btn)))

        return mock_page, connect_btn, more_btn, menuitem_connect, add_note_btn, send_btn, note_box

    async def test_send_without_note(self, mock_context):
        mock_page, connect_btn, _, _, _, send_btn, _ = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "send_connection_request")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "success"
        assert result["recipient"] == "testuser"
        assert "message_preview" not in result
        connect_btn.click.assert_awaited_once()
        send_btn.click.assert_awaited_once()

    async def test_send_with_note(self, mock_context):
        mock_page, connect_btn, _, _, add_note_btn, send_btn, note_box = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "send_connection_request")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn(
                "testuser", mock_context, message="Hi, let's connect!", extractor=mock_extractor
            )

        assert result["status"] == "success"
        assert result["message_preview"] == "Hi, let's connect!"
        connect_btn.click.assert_awaited_once()
        add_note_btn.click.assert_awaited_once()
        send_btn.click.assert_awaited_once()

    async def test_connect_button_not_found(self, mock_context):
        mock_page, *_ = self._make_page_mock(connect_btn_count=0)
        # "More" dropdown also absent — _make_page_mock already sets up no_btn for "More"
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "send_connection_request")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "error"
        assert "Connect button not found" in result["error"]

    async def test_connect_via_more_dropdown(self, mock_context):
        mock_page, _, more_btn, menuitem_connect, _, send_btn, _ = self._make_page_mock(
            connect_btn_count=0,
            more_btn_count=1,
            menuitem_connect_count=1,
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "send_connection_request")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "success"
        assert result["recipient"] == "testuser"
        more_btn.click.assert_awaited_once()
        menuitem_connect.click.assert_awaited_once()
        send_btn.click.assert_awaited_once()


class TestFollowPerson:
    def _make_page_mock(
        self,
        primary_follow_count=1,
        more_btn_count=0,
        menuitem_follow_count=0,
    ):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.evaluate = AsyncMock(return_value="")

        def make_btn(count):
            b = MagicMock()
            b.count = AsyncMock(return_value=count)
            b.click = AsyncMock()
            return b

        def wrap(btn):
            loc = MagicMock()
            loc.first = btn
            return loc

        primary_follow_btn = make_btn(primary_follow_count)
        more_btn = make_btn(more_btn_count)
        menu_follow_btn = make_btn(menuitem_follow_count)
        no_btn = make_btn(0)

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button.artdeco-button--primary":
                loc.filter.return_value.nth.return_value = primary_follow_btn
            elif selector == "button":
                loc.filter.return_value.nth.return_value = more_btn
            else:
                loc.filter.return_value.nth.return_value = no_btn
                loc.first = no_btn
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)
        mock_page.get_by_role = MagicMock(
            side_effect=lambda role, **kw: wrap(menu_follow_btn) if kw.get("name") == "Follow" else wrap(no_btn)
        )
        return mock_page, primary_follow_btn, more_btn, menu_follow_btn

    async def test_follow_person_primary_button(self, mock_context):
        mock_page, primary_follow_btn, _, _ = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "follow_person")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "success"
        assert result["recipient"] == "testuser"
        assert "testuser" in result["profile_url"]
        primary_follow_btn.click.assert_awaited_once()

    async def test_follow_person_via_more_dropdown(self, mock_context):
        mock_page, _, more_btn, menu_follow_btn = self._make_page_mock(
            primary_follow_count=0,
            more_btn_count=1,
            menuitem_follow_count=1,
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "follow_person")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "success"
        more_btn.click.assert_awaited_once()
        menu_follow_btn.click.assert_awaited_once()

    async def test_follow_person_button_not_found(self, mock_context):
        mock_page, _, _, _ = self._make_page_mock(primary_follow_count=0, more_btn_count=0)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "follow_person")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["status"] == "error"
        assert "Follow button not found" in result["error"]


class TestJobTools:
    async def test_get_job_details(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/jobs/view/12345/",
            "sections": {"job_posting": "Software Engineer\nGreat opportunity"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "get_job_details")
        result = await tool_fn("12345", mock_context, extractor=mock_extractor)
        assert "job_posting" in result["sections"]
        assert "pages_visited" not in result

    async def test_search_jobs(self, mock_context):
        expected = {
            "url": "https://www.linkedin.com/jobs/search/?keywords=python",
            "sections": {"search_results": "Job 1\nJob 2"},
        }
        mock_extractor = _make_mock_extractor(expected)

        from linkedin_mcp_server.tools.job import register_job_tools

        mcp = FastMCP("test")
        register_job_tools(mcp)

        tool_fn = await get_tool_fn(mcp, "search_jobs")
        result = await tool_fn(
            "python", mock_context, location="Remote", extractor=mock_extractor
        )
        assert "search_results" in result["sections"]
        assert "pages_visited" not in result


class TestGetInbox:
    def _make_page_mock(self, conversations=None):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        if conversations is None:
            conversations = [
                {
                    "name": "Jane Smith",
                    "preview": "Yes, I'd love to connect!",
                    "timestamp": "2h",
                    "unread": True,
                    "thread_url": "/messaging/thread/2-abc123/",
                },
                {
                    "name": "Bob Jones",
                    "preview": "Thanks for reaching out",
                    "timestamp": "1d",
                    "unread": False,
                    "thread_url": "/messaging/thread/2-def456/",
                },
            ]
        # First evaluate call returns conversations, subsequent ones return None (username lookup)
        call_count = 0

        async def evaluate_side_effect(script, *args):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return conversations
            return None  # username enrichment returns None

        mock_page.evaluate = AsyncMock(side_effect=evaluate_side_effect)
        return mock_page

    async def test_get_inbox_returns_conversations(self, mock_context):
        mock_page = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.messaging import register_messaging_tools

        mcp = FastMCP("test")
        register_messaging_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_inbox")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.messaging.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn(mock_context, extractor=mock_extractor)

        assert "conversations" in result
        assert len(result["conversations"]) == 2
        assert result["conversations"][0]["name"] == "Jane Smith"
        assert result["conversations"][0]["unread"] is True

    async def test_get_inbox_unread_only(self, mock_context):
        mock_page = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.messaging import register_messaging_tools

        mcp = FastMCP("test")
        register_messaging_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_inbox")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.messaging.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn(mock_context, unread_only=True, extractor=mock_extractor)

        assert len(result["conversations"]) == 1
        assert result["conversations"][0]["name"] == "Jane Smith"


class TestGetConversation:
    def _make_page_mock(self, message_btn_count=1, messages=None):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()

        msg_btn = MagicMock()
        msg_btn.count = AsyncMock(return_value=message_btn_count)
        msg_btn.click = AsyncMock()

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button.artdeco-button--primary":
                loc.filter.return_value.nth.return_value = msg_btn
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)

        if messages is None:
            messages = [
                {"sender": "me", "text": "Hi Jane, ...", "timestamp": "Mar 15"},
                {"sender": "Jane Smith", "text": "Yes, interested!", "timestamp": "Mar 16"},
            ]
        mock_page.evaluate = AsyncMock(return_value=messages)
        return mock_page, msg_btn

    async def test_get_conversation_returns_messages(self, mock_context):
        mock_page, _ = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.messaging import register_messaging_tools

        mcp = FastMCP("test")
        register_messaging_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_conversation")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.messaging.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("janesmith", mock_context, extractor=mock_extractor)

        assert result["linkedin_username"] == "janesmith"
        assert len(result["messages"]) == 2
        assert result["messages"][1]["sender"] == "Jane Smith"

    async def test_get_conversation_no_message_button(self, mock_context):
        mock_page, _ = self._make_page_mock(message_btn_count=0)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.messaging import register_messaging_tools

        mcp = FastMCP("test")
        register_messaging_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_conversation")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.messaging.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("janesmith", mock_context, extractor=mock_extractor)

        assert result["status"] == "error"
        assert "1st-degree" in result["error"]

    async def test_get_conversation_falls_back_to_raw_text(self, mock_context):
        mock_page, _ = self._make_page_mock(messages=[])  # empty structured result
        # Second evaluate call (fallback) returns raw text
        raw_text = "Jane Smith\nYes, interested!\nMar 16"
        mock_page.evaluate = AsyncMock(side_effect=[[], raw_text])
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.messaging import register_messaging_tools

        mcp = FastMCP("test")
        register_messaging_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_conversation")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.messaging.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("janesmith", mock_context, extractor=mock_extractor)

        assert "messages_raw" in result
        assert result["messages_raw"] == raw_text


class TestCheckFollow:
    def _make_page_mock(
        self,
        primary_following_count=0,
        primary_follow_count=0,
        more_btn_count=0,
        menuitem_unfollow_count=0,
        menuitem_follow_count=0,
    ):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.press = AsyncMock()

        def make_btn(count):
            b = MagicMock()
            b.count = AsyncMock(return_value=count)
            b.click = AsyncMock()
            return b

        def wrap(btn):
            loc = MagicMock()
            loc.first = btn
            return loc

        following_btn = make_btn(primary_following_count)
        follow_btn = make_btn(primary_follow_count)
        more_btn = make_btn(more_btn_count)
        unfollow_item = make_btn(menuitem_unfollow_count)
        follow_item = make_btn(menuitem_follow_count)
        no_btn = make_btn(0)

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button.artdeco-button--primary":
                def primary_filter(**kw):
                    inner = MagicMock()
                    text = str(kw.get("has_text", ""))
                    inner.nth.return_value = following_btn if "Following" in text else follow_btn
                    return inner
                loc.filter = MagicMock(side_effect=primary_filter)
            elif selector == "button":
                loc.filter.return_value.nth.return_value = more_btn
            else:
                # aria-label selectors — return count=0 by default so tests fall through
                loc.nth.return_value = no_btn
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)
        mock_page.get_by_role = MagicMock(
            side_effect=lambda role, **kw: {
                "Unfollow": wrap(unfollow_item),
                "Follow": wrap(follow_item),
            }.get(kw.get("name"), wrap(no_btn))
        )
        return mock_page, following_btn, follow_btn, more_btn, unfollow_item, follow_item

    async def test_following_primary_button(self, mock_context):
        mock_page, following_btn, _, _, _, _ = self._make_page_mock(primary_following_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is True
        assert "testuser" in result["profile_url"]

    async def test_not_following_primary_button(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock(primary_follow_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is False

    async def test_following_via_more_dropdown_unfollow(self, mock_context):
        mock_page, _, _, more_btn, unfollow_item, _ = self._make_page_mock(
            more_btn_count=1, menuitem_unfollow_count=1
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is True
        more_btn.click.assert_awaited_once()
        mock_page.keyboard.press.assert_awaited_once_with("Escape")

    async def test_not_following_via_more_dropdown_follow(self, mock_context):
        mock_page, _, _, more_btn, _, follow_item = self._make_page_mock(
            more_btn_count=1, menuitem_follow_count=1
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is False
        more_btn.click.assert_awaited_once()

    async def test_following_via_aria_label(self, mock_context):
        """Icon-only button: aria-label='Following' with no visible text."""
        mock_page, _, _, _, _, _ = self._make_page_mock()  # has_text counts all 0

        # Inject aria-label locator responses
        following_aria = MagicMock()
        following_aria.count = AsyncMock(return_value=1)
        follow_aria = MagicMock()
        follow_aria.count = AsyncMock(return_value=0)

        original_locator = mock_page.locator.side_effect

        def locator_with_aria(selector):
            if selector == "button[aria-label^='Following']":
                loc = MagicMock()
                loc.nth.return_value = following_aria
                return loc
            if selector == "button[aria-label^='Follow ']":
                loc = MagicMock()
                loc.nth.return_value = follow_aria
                return loc
            return original_locator(selector)

        mock_page.locator.side_effect = locator_with_aria
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is True

    async def test_not_following_via_aria_label(self, mock_context):
        """Icon-only button: aria-label='Follow David Van Der Spoel' with no visible text."""
        mock_page, _, _, _, _, _ = self._make_page_mock()  # has_text counts all 0

        following_aria = MagicMock()
        following_aria.count = AsyncMock(return_value=0)
        follow_aria = MagicMock()
        follow_aria.count = AsyncMock(return_value=1)

        original_locator = mock_page.locator.side_effect

        def locator_with_aria(selector):
            if selector == "button[aria-label^='Following']":
                loc = MagicMock()
                loc.nth.return_value = following_aria
                return loc
            if selector == "button[aria-label^='Follow ']":
                loc = MagicMock()
                loc.nth.return_value = follow_aria
                return loc
            return original_locator(selector)

        mock_page.locator.side_effect = locator_with_aria
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is False

    async def test_unknown_follow_status(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock()  # all count=0
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["following"] is None
        assert "note" in result


class TestCheckConnection:
    def _make_page_mock(
        self,
        message_btn_count=0,
        pending_btn_count=0,
        connect_btn_count=0,
        more_btn_count=0,
        menuitem_connect_count=0,
    ):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.press = AsyncMock()

        def make_btn(count):
            b = MagicMock()
            b.count = AsyncMock(return_value=count)
            b.click = AsyncMock()
            return b

        def wrap(btn):
            loc = MagicMock()
            loc.first = btn
            return loc

        message_btn = make_btn(message_btn_count)
        pending_btn = make_btn(pending_btn_count)
        connect_btn = make_btn(connect_btn_count)
        more_btn = make_btn(more_btn_count)
        connect_item = make_btn(menuitem_connect_count)
        no_btn = make_btn(0)

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button.artdeco-button--primary":
                def primary_filter(**kw):
                    inner = MagicMock()
                    text = str(kw.get("has_text", ""))
                    inner.nth.return_value = message_btn if "Message" in text else connect_btn
                    return inner
                loc.filter = MagicMock(side_effect=primary_filter)
            elif selector == "button":
                def btn_filter(**kw):
                    inner = MagicMock()
                    text = str(kw.get("has_text", ""))
                    inner.nth.return_value = pending_btn if "Pending" in text else more_btn
                    return inner
                loc.filter = MagicMock(side_effect=btn_filter)
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)
        mock_page.get_by_role = MagicMock(
            side_effect=lambda role, **kw: wrap(connect_item) if kw.get("name") == "Connect" else wrap(no_btn)
        )
        return mock_page, message_btn, pending_btn, connect_btn, more_btn, connect_item

    async def test_connected(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock(message_btn_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_connection")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["connected"] is True
        assert result["status"] == "connected"
        assert "testuser" in result["profile_url"]

    async def test_pending(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock(pending_btn_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_connection")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["connected"] is False
        assert result["status"] == "pending"

    async def test_not_connected_primary_button(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock(connect_btn_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_connection")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["connected"] is False
        assert result["status"] == "not_connected"

    async def test_not_connected_via_more_dropdown(self, mock_context):
        mock_page, _, _, _, more_btn, connect_item = self._make_page_mock(
            more_btn_count=1, menuitem_connect_count=1
        )
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_connection")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["connected"] is False
        assert result["status"] == "not_connected"
        more_btn.click.assert_awaited_once()
        mock_page.keyboard.press.assert_awaited_once_with("Escape")

    async def test_unknown_connection_status(self, mock_context):
        mock_page, _, _, _, _, _ = self._make_page_mock()  # all count=0
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.person import register_person_tools

        mcp = FastMCP("test")
        register_person_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_connection")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.person.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("testuser", mock_context, extractor=mock_extractor)

        assert result["connected"] is None
        assert result["status"] == "unknown"
        assert "note" in result


class TestCheckFollowCompany:
    def _make_page_mock(self, following_count=0, follow_count=0):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()

        def make_btn(count):
            b = MagicMock()
            b.count = AsyncMock(return_value=count)
            return b

        following_btn = make_btn(following_count)
        follow_btn = make_btn(follow_count)
        no_btn = make_btn(0)

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button":
                def btn_filter(**kw):
                    inner = MagicMock()
                    text = str(kw.get("has_text", ""))
                    inner.first = following_btn if "Following" in text else follow_btn
                    return inner
                loc.filter = MagicMock(side_effect=btn_filter)
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)
        return mock_page, following_btn, follow_btn

    async def test_following_company(self, mock_context):
        mock_page, _, _ = self._make_page_mock(following_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow_company")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.company.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("anthropic", mock_context, extractor=mock_extractor)

        assert result["following"] is True
        assert "anthropic" in result["company_url"]

    async def test_not_following_company(self, mock_context):
        mock_page, _, _ = self._make_page_mock(follow_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow_company")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.company.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("anthropic", mock_context, extractor=mock_extractor)

        assert result["following"] is False

    async def test_unknown_follow_company_status(self, mock_context):
        mock_page, _, _ = self._make_page_mock()  # both count=0
        mock_browser = MagicMock()
        mock_browser.page = mock_page
        mock_extractor = MagicMock()

        from linkedin_mcp_server.tools.company import register_company_tools

        mcp = FastMCP("test")
        register_company_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "check_follow_company")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.company.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("anthropic", mock_context, extractor=mock_extractor)

        assert result["following"] is None
        assert "note" in result


class TestGetRawPage:
    def _make_page_mock(self, more_btn_count=0):
        mock_page = MagicMock()
        mock_page.goto = AsyncMock()
        mock_page.url = "https://www.linkedin.com/in/testuser/"
        mock_page.title = AsyncMock(return_value="Test User | LinkedIn")
        mock_page.keyboard = MagicMock()
        mock_page.keyboard.press = AsyncMock()

        buttons_data = [
            {"text": "Follow", "class": "artdeco-button artdeco-button--primary",
             "aria_label": None, "disabled": False, "outer_html": "<button>Follow</button>"},
        ]
        menu_items_data = [
            {"text": "Follow", "class": "artdeco-dropdown__item", "aria_label": None,
             "role": "menuitem", "outer_html": "<li role='menuitem'>Follow</li>"},
        ]
        mock_page.evaluate = AsyncMock(
            side_effect=[
                "Test User\nSoftware Engineer",  # innerText
                buttons_data,                    # buttons
                menu_items_data,                 # menu items (only if More clicked)
            ]
        )

        more_btn = MagicMock()
        more_btn.count = AsyncMock(return_value=more_btn_count)
        more_btn.click = AsyncMock()

        def locator_side_effect(selector):
            loc = MagicMock()
            if selector == "button":
                loc.filter.return_value.nth.return_value = more_btn
            return loc

        mock_page.locator = MagicMock(side_effect=locator_side_effect)
        return mock_page, more_btn

    async def test_returns_page_content(self, mock_context):
        mock_page, _ = self._make_page_mock()
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        from linkedin_mcp_server.tools.debug import register_debug_tools

        mcp = FastMCP("test")
        register_debug_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_raw_page")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.debug.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("https://www.linkedin.com/in/testuser/", mock_context)

        assert result["url"] == "https://www.linkedin.com/in/testuser/"
        assert result["title"] == "Test User | LinkedIn"
        assert result["text"] == "Test User\nSoftware Engineer"
        assert len(result["buttons"]) == 1
        assert result["buttons"][0]["text"] == "Follow"
        assert "outer_html" in result["buttons"][0]
        assert "more_menu_items" not in result

    async def test_opens_more_dropdown_and_returns_menu_items(self, mock_context):
        mock_page, more_btn = self._make_page_mock(more_btn_count=1)
        mock_browser = MagicMock()
        mock_browser.page = mock_page

        from linkedin_mcp_server.tools.debug import register_debug_tools

        mcp = FastMCP("test")
        register_debug_tools(mcp)
        tool_fn = await get_tool_fn(mcp, "get_raw_page")

        with (
            patch(
                "linkedin_mcp_server.drivers.browser.get_or_create_browser",
                new_callable=AsyncMock,
                return_value=mock_browser,
            ),
            patch("linkedin_mcp_server.tools.debug.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await tool_fn("https://www.linkedin.com/in/testuser/", mock_context)

        assert "more_menu_items" in result
        assert result["more_menu_items"][0]["text"] == "Follow"
        assert result["more_menu_items"][0]["role"] == "menuitem"
        more_btn.click.assert_awaited_once()
        mock_page.keyboard.press.assert_awaited_once_with("Escape")


class TestToolTimeouts:
    async def test_all_tools_have_global_timeout(self):
        from linkedin_mcp_server.constants import TOOL_TIMEOUT_SECONDS
        from linkedin_mcp_server.server import create_mcp_server

        mcp = create_mcp_server()

        tool_names = (
            "get_person_profile",
            "search_people",
            "follow_person",
            "check_follow",
            "check_connection",
            "get_company_profile",
            "get_company_posts",
            "check_follow_company",
            "get_job_details",
            "search_jobs",
            "get_inbox",
            "get_conversation",
            "get_raw_page",
            "close_session",
        )

        for name in tool_names:
            tool = await mcp.get_tool(name)
            assert tool is not None
            assert tool.timeout == TOOL_TIMEOUT_SECONDS
