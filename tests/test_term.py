import pytest
from upkeep.term import bold, dim, red, green, yellow, cyan, magenta, USE_COLOR
import os


class TestColorFunctions:
    def test_bold_returns_string(self):
        result = bold("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_dim_returns_string(self):
        result = dim("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_red_returns_string(self):
        result = red("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_green_returns_string(self):
        result = green("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_yellow_returns_string(self):
        result = yellow("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_cyan_returns_string(self):
        result = cyan("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_magenta_returns_string(self):
        result = magenta("hello")
        assert isinstance(result, str)
        assert "hello" in result

    def test_use_color_is_bool(self):
        assert isinstance(USE_COLOR, bool)
