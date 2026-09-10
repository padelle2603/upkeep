import pytest
from upkeep.updater import sanitize_name


class TestSanitizeName:
    def test_normal_name(self):
        assert sanitize_name("MyApp") == "myapp"

    def test_special_chars(self):
        assert sanitize_name("My App!") == "my-app"

    def test_empty(self):
        assert sanitize_name("") == ""

    def test_none(self):
        assert sanitize_name(None) == ""

    def test_leading_trailing(self):
        assert sanitize_name("  MyApp  ") == "myapp"

    def test_preserves_dots(self):
        assert sanitize_name("my.app") == "my.app"

    def test_preserves_hyphens(self):
        assert sanitize_name("my-app") == "my-app"

    def test_preserves_underscores(self):
        assert sanitize_name("my_app") == "my_app"
