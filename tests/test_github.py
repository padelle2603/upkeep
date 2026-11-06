import json
import pytest
from upkeep.github import GitHubError, fetch_latest_release, normalize_repo, select_asset, strip_v
from unittest.mock import patch


class TestStripV:
    def test_strips_v_prefix(self):
        assert strip_v("v1.0.0") == "1.0.0"

    def test_strips_V_prefix(self):
        assert strip_v("V2.0.0") == "2.0.0"

    def test_no_prefix(self):
        assert strip_v("1.0.0") == "1.0.0"

    def test_empty(self):
        assert strip_v("") == ""

    def test_none(self):
        assert strip_v(None) == ""


class TestNormalizeRepo:
    def test_owner_repo_is_unchanged(self):
        assert normalize_repo("owner/repo") == "owner/repo"

    def test_url_is_normalized(self):
        assert normalize_repo("https://github.com/owner/repo/releases/latest") == "owner/repo"

    def test_at_prefix_is_removed(self):
        assert normalize_repo("@/owner/repo") == "owner/repo"


class TestGitHubError:
    def test_message(self):
        err = GitHubError("test error")
        assert str(err) == "test error"
        assert err.kind == "error"

    def test_kind(self):
        err = GitHubError("rate limited", kind="rate_limit")
        assert err.kind == "rate_limit"


class TestFetchLatestRelease:
    @patch("upkeep.github._request")
    def test_invalid_repo(self, mock_req):
        with pytest.raises(GitHubError, match="Invalid repo"):
            fetch_latest_release("invalid")

    @patch("upkeep.github._request")
    def test_not_found(self, mock_req):
        mock_req.return_value = (404, b'{"message": "Not Found"}', {})
        with pytest.raises(GitHubError, match="not found"):
            fetch_latest_release("nonexistent/repo")


    @patch("upkeep.github._request")
    def test_tag_filter_uses_releases_endpoint(self, mock_req):
        body = json.dumps([
            {"tag_name": "photos-v1"},
            {"tag_name": "auth-v4"},
        ]).encode()
        mock_req.return_value = (200, body, {})

        release = fetch_latest_release("owner/repo", tag_filter="^auth-v")

        assert release["tag_name"] == "auth-v4"
        called_url = mock_req.call_args[0][0]
        assert "/releases?per_page=100" in called_url

    @patch("upkeep.github._request")
    def test_tag_filter_no_match_is_not_found(self, mock_req):
        body = json.dumps([{"tag_name": "photos-v1"}]).encode()
        mock_req.return_value = (200, body, {})

        with pytest.raises(GitHubError) as exc:
            fetch_latest_release("owner/repo", tag_filter="^auth-v")

        assert exc.value.kind == "not_found"

    @patch("upkeep.github._request")
    def test_invalid_tag_filter_fails_fast(self, mock_req):
        with pytest.raises(GitHubError) as exc:
            fetch_latest_release("owner/repo", tag_filter="[")
        assert exc.value.kind == "invalid"
        mock_req.assert_not_called()


class TestSelectAsset:
    def test_invalid_regex_raises_invalid_error(self):
        assets = [{"name": "tool-x86_64.AppImage", "browser_download_url": "https://example.test/a"}]
        with pytest.raises(GitHubError) as exc:
            select_asset(assets, asset_filter="[")
        assert exc.value.kind == "invalid"


class TestRateLimit:
    """The 60/h budget is per IP, so a rate limit hits every app at once."""

    def _mock(self, headers):
        body = (
            b'{"message": "API rate limit exceeded for 203.0.113.9. '
            b'(But here\'s the good news: Authenticated requests get a '
            b'higher rate limit.)"}'
        )
        return patch("upkeep.github._request", return_value=(403, body, headers))

    def test_kind_is_rate_limit(self):
        with self._mock({}):
            with pytest.raises(GitHubError) as exc:
                fetch_latest_release("owner/repo")
        assert exc.value.kind == "rate_limit"

    def test_reset_time_is_reported(self):
        with self._mock({"x-ratelimit-reset": "1791807167"}):
            with pytest.raises(GitHubError) as exc:
                fetch_latest_release("owner/repo")
        assert "resets at" in str(exc.value)

    def test_github_wording_is_not_leaked(self):
        """It names the caller's IP and pitches a token Upkeep will not use."""
        with self._mock({}):
            with pytest.raises(GitHubError) as exc:
                fetch_latest_release("owner/repo")
        message = str(exc.value)
        assert "203.0.113.9" not in message
        assert "Authenticated" not in message

    def test_missing_header_does_not_crash(self):
        with self._mock({}):
            with pytest.raises(GitHubError) as exc:
                fetch_latest_release("owner/repo")
        assert str(exc.value).endswith(".")

    def test_garbage_header_does_not_crash(self):
        with self._mock({"x-ratelimit-reset": "not-a-number"}):
            with pytest.raises(GitHubError) as exc:
                fetch_latest_release("owner/repo")
        assert str(exc.value).endswith(".")
