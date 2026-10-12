import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging" / "build-appimage.sh"

# PyInstaller resolves an --add-data destination relative to sys._MEIPASS,
# which in an onedir build is <bundle>/_internal. The frozen loader synthesizes
# __file__ as <_MEIPASS>/upkeep/gui/main_window.py, so that is where
# Path(__file__).parent / "style.css" looks.
CSS_DESTINATION = "upkeep/gui"


def _add_data_entries():
    """Every --add-data in the build script, as (source, destination) pairs."""
    text = SCRIPT.read_text(encoding="utf-8")
    return re.findall(r'--add-data\s+"\$PWD/([^:"]+):([^"]+)"', text)


class TestFrozenDataFiles:
    def test_icons_are_still_shipped(self):
        """The prune only removes extra icon themes; upkeep.svg must survive."""
        sources = [src for src, _ in _add_data_entries()]
        assert "icons" in sources

    def test_style_css_is_shipped(self):
        """PyInstaller does not collect non-Python files inside a package."""
        sources = [src for src, _ in _add_data_entries()]
        assert "src/upkeep/gui/style.css" in sources, (
            "style.css must be passed with --add-data, otherwise the AppImage "
            "opens unstyled and nothing in CI notices"
        )

    def test_style_css_lands_where_the_frozen_module_claims_to_live(self):
        """A wrong destination ships the file and still loses the styling."""
        entries = dict((src, dest) for src, dest in _add_data_entries())
        assert entries.get("src/upkeep/gui/style.css") == CSS_DESTINATION, (
            f"style.css must land in {CSS_DESTINATION!r}: the frozen loader "
            f"reports __file__ under _internal/{CSS_DESTINATION}/"
        )

    def test_source_file_is_where_the_script_claims(self):
        """The source half of the entry has to exist or PyInstaller warns on."""
        for src, _ in _add_data_entries():
            assert (ROOT / src).exists(), f"--add-data points at a missing file: {src}"

    def test_build_fails_when_the_css_is_absent_from_the_freeze(self):
        """The smoke tests never open a window, so the build must check itself."""
        text = SCRIPT.read_text(encoding="utf-8")
        assert "upkeep/gui/style.css" in text, (
            "the build script should assert the css is present in the AppDir; "
            "without it a missing data file ships silently"
        )
