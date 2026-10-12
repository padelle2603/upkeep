import pytest
from upkeep.github import GitHubError, fetch_latest_release, strip_v
from unittest.mock import patch, MagicMock


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
