# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 padelle2603
# Upkeep: automatically update AppImages from GitHub releases.
# Licensed under the GNU GPL v3 or later; see LICENSE and NOTICE.

import os
import sys

USE_COLOR = (
    hasattr(sys.stdout, "isatty")
    and sys.stdout.isatty()
    and os.environ.get("TERM", "") != "dumb"
    and "NO_COLOR" not in os.environ
)

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
FG = {
    "red": "\033[31m",
    "green": "\033[32m",
    "yellow": "\033[33m",
    "cyan": "\033[36m",
    "magenta": "\033[35m",
}


def _wrap(code, text):
    if not USE_COLOR:
        return str(text)
    return f"{code}{text}{RESET}"


def bold(text):
    return _wrap(BOLD, text)


def dim(text):
    return _wrap(DIM, text)


def red(text):
    return _wrap(FG["red"], text)


def green(text):
    return _wrap(FG["green"], text)


def yellow(text):
    return _wrap(FG["yellow"], text)


def cyan(text):
    return _wrap(FG["cyan"], text)


def magenta(text):
    return _wrap(FG["magenta"], text)


def state_color(state):
    colors = {
        "uptodate": green,
        "updated": green,
        "outdated": yellow,
        "missing": yellow,
        "skipped": yellow,
        "error": red,
    }
    return colors.get(state, str)


def print_header(text):
    print(bold(cyan(text)))


def print_table(rows, headers, aligns=None, max_width=None):
    aligns = aligns or []
    ncols = len(headers)
    col_count = max(len(r) for r in rows) if rows else 0
    if col_count < ncols:
        rows = [list(r) + [""] * (ncols - len(r)) for r in rows]
    elif col_count > ncols:
        rows = [r[:ncols] for r in rows]

    if max_width is None:
        max_width = _term_width()

    cells = [[str(r[i]) for i in range(ncols)] for r in rows]

    gap = 2
    sep_pad = 1

    def natural_widths():
        return [max(len(headers[i]), *(len(c[i]) for c in cells)) for i in range(ncols)]

    widths = natural_widths()
    if max_width:
        cap = max(10, max_width // max(1, ncols))
        widths = [min(w, cap) for w in widths]
    total_min = sum(widths) + gap * (ncols - 1)
    if max_width and total_min > max_width:
        over = total_min - max_width
        idx = list(range(ncols))
        while over > 0 and idx:
            pool = [i for i in idx if widths[i] > 4]
            if not pool:
                break
            pool.sort(key=lambda i: widths[i], reverse=True)
            for i in pool:
                if over <= 0:
                    break
                widths[i] -= 1
                over -= 1
            idx = [i for i in idx if widths[i] > 4]
        widths = [max(4, w) for w in widths]
    def truncate(text, w):
        if len(text) <= w:
            return text
        return text[: max(1, w - 1)] + "\u2026"

    def fmt_cell(text, i, header=False):
        t = truncate(text, widths[i])
        align = (aligns[i] if i < len(aligns) else None) or "left"
        if align == "right":
            t = t.rjust(widths[i])
        else:
            t = t.ljust(widths[i])
        if header:
            t = bold(t)
        return t

    def rule():
        return "─" * (sum(widths) + gap * (ncols - 1))

    def rowline(cells_line, header=False):
        sep = " " * gap
        return sep.join(fmt_cell(v, i, header=header) for i, v in enumerate(cells_line))

    print(rule())
    print(rowline(headers, header=True))
    print(rule())
    for c in cells:
        print(rowline(c))
    print(rule())


def _term_width():
    try:
        import shutil
        return shutil.get_terminal_size((120, 24)).columns or 120
    except Exception:
        return 120


def _stderr_tty():
    try:
        return hasattr(sys.stderr, "isatty") and sys.stderr.isatty()
    except Exception:
        return False


_status_len = 0


def show_status(msg):
    """Show a one-line transient status on stderr.

    TTY: in-place ``\\r`` update (no newline). Non-TTY: print line once.
    """
    global _status_len
    if not msg:
        return
    msg = str(msg)
    if _stderr_tty():
        pad = max(0, _status_len - len(msg))
        sys.stderr.write("\r" + msg + " " * pad)
        sys.stderr.flush()
        _status_len = len(msg)
    else:
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


def clear_status():
    """Clear the transient status line (TTY only)."""
    global _status_len
    if _stderr_tty() and _status_len:
        try:
            sys.stderr.write("\r" + " " * _status_len + "\r")
            sys.stderr.flush()
        except Exception:
            pass
    _status_len = 0


def progress(done, total, label=""):
    bar = Progress()
    bar.set(done, total, label=label)


def progress_end(label=""):
    clear_status()


def _human(num):
    for unit in ("B", "K", "M", "G"):
        if num < 1024 or unit == "G":
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}T"


class Progress:
    """Per-file progress bar (single download at a time).

    Expected callback semantics: ``set(done_cumulative, total_or_0)``,
    matching ``updater.download`` which reports cumulative bytes and the
    ``Content-Length`` total (0 when unknown). Draws in-place on stderr
    when a TTY is available, no-op otherwise.
    """

    def __init__(self, width=30):
        self.width = width
        self.done = 0
        self.total = 0
        self.label = ""
        self._started = False

    def set(self, done, total=None, label=""):
        self.done = max(0, done or 0)
        if total is not None:
            self.total = max(0, total or 0)
        if label:
            self.label = label
        self._draw()

    def update(self, done, total=None, label=""):
        """Backwards-compatible alias for :meth:`set`."""
        self.set(done, total, label=label)

    def _draw(self):
        global _status_len
        if not _stderr_tty():
            return
        width = self.width
        if self.total > 0:
            frac = min(self.done / self.total, 1.0)
            filled = int(frac * width)
            pct = f"{frac * 100:5.1f}%"
            size = f"{_human(self.done)}/{_human(self.total)}"
        else:
            filled = 0
            pct = f"{_human(self.done):>7}"
            size = f"{_human(self.done)} downloaded"
        bar = "█" * filled + "─" * (width - filled)
        prefix = f"{self.label} " if self.label else ""
        line = f"\r{prefix}[{bar}] {pct}  {size}"
        # Clear leftover chars from a longer previous line.
        pad = max(0, _status_len - len(line) + 1)
        sys.stderr.write(line + " " * pad)
        sys.stderr.flush()
        _status_len = len(line)
        self._started = True

    def finish(self):
        global _status_len
        if self._started and _stderr_tty():
            try:
                sys.stderr.write("\r" + " " * _status_len + "\r")
                sys.stderr.flush()
            except Exception:
                pass
        _status_len = 0
        self._started = False
