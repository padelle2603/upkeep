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
        mock_req.return_value = (404, b'{"message": "Not Found"}')
        with pytest.raises(GitHubError, match="not found"):
            fetch_latest_release("nonexistent/repo")
