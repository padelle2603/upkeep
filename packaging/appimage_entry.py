"""Entry point for the AppImage bundle: GUI with no arguments, CLI otherwise.

``upkeep/gui/__main__.py`` cannot be used directly: its relative import dies
once the package is frozen as a top-level script.
"""

import sys

from upkeep.cli import main as cli_main
from upkeep.gui.main_window import run as gui_run

if len(sys.argv) > 1:
    sys.exit(cli_main())
gui_run()