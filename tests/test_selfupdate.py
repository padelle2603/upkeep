from unittest.mock import patch

import pytest

from upkeep import selfupdate


class TestLatestTag:
    def test_network_failure_is_silent(self):
        def boom(*a, **k):
            raise OSError("offline")

        with patch.object(selfupdate.http.client, "HTTPSConnection", boom):
            assert selfupdate.latest_tag() is None
            assert selfupdate.available_version("1.0.0") is None

    @pytest.mark.parametrize(
        "location,expected",
        [
            (None, None),
            ("https://github.com/padelle2603/upkeep/releases", None),
            ("https://github.com/padelle2603/upkeep/releases/latest", None),
            ("https://github.com/padelle2603/upkeep/releases/tag/v1.1.0", "1.1.0"),
            ("https://github.com/padelle2603/upkeep/releases/tag/1.1.0", "1.1.0"),
        ],
    )
    def test_tag_extraction(self, location, expected):
        class Response:
            def getheader(self, name):
                return location

        class Conn:
            def __init__(self, *a, **k):
                pass

            def request(self, *a, **k):
                pass

            def getresponse(self):
                return Response()

            def close(self):
                pass

        with patch.object(selfupdate.http.client, "HTTPSConnection", Conn):
            assert selfupdate.latest_tag() == expected


class TestAvailableVersion:
    def _fake_tag(self, tag):
        with patch.object(selfupdate, "latest_tag", return_value=tag):
            return selfupdate.available_version("1.0.2")

    def test_newer_release_is_offered(self):
        assert self._fake_tag("1.1.0") == "1.1.0"

    def test_current_or_ahead_is_not_offered(self):
        assert self._fake_tag("1.0.2") is None
        assert self._fake_tag("0.9.9") is None

    def test_no_release_is_not_offered(self):
        assert self._fake_tag(None) is None


class TestNoApiBudget:
    def test_self_check_never_touches_the_api(self):
        """A self-check must not consume the 60/h API budget the managed apps share."""
        with patch.object(selfupdate.http.client, "HTTPSConnection") as conn:
            selfupdate.latest_tag()
        assert conn.call_count == 1
        assert conn.call_args[0][0] == selfupdate.HOST