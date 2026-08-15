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


def progress(done, total, label=""):
    if not USE_COLOR:
        return
    total = total or 0
    width = 30
    if total > 0:
        frac = min(done / total, 1.0)
    else:
        frac = None
    filled = int(frac * width) if frac is not None else 0
    bar = "█" * filled + "─" * (width - filled)
    if frac is not None:
        pct = f"{frac * 100:5.1f}%"
    else:
        pct = f"{_human(done):>7}"
    line = f"\r{label} [{bar}] {pct}"
    sys.stdout.write(line)
    sys.stdout.flush()


def progress_end(label=""):
    if not USE_COLOR:
        return
    sys.stdout.write("\r" + " " * (_term_width() - 1) + "\r")
    sys.stdout.flush()


def _human(num):
    for unit in ("B", "K", "M", "G"):
        if num < 1024 or unit == "G":
            return f"{num:.1f}{unit}"
        num /= 1024.0
    return f"{num:.1f}T"


class Progress:
    """Cumulative progress bar across multiple downloads.

    Accumulates the bytes transferred (and the known content-length totals)
    into a single in-place bar. No-op when colors/TTY are unavailable.
    """

    def __init__(self, width=30):
        self.width = width
        self.done = 0
        self.total = 0
        self.label = ""
        self._started = False

    def update(self, delta, chunk_total=None, label=""):
        if not USE_COLOR:
            return
        self.done += delta
        if chunk_total:
            self.total += chunk_total
        if label:
            self.label = label
        self._draw()

    def _draw(self):
        if not USE_COLOR:
            return
        width = self.width
        if self.total > 0:
            frac = min(self.done / self.total, 1.0)
            filled = int(frac * width)
            pct = f"{frac * 100:5.1f}%"
        else:
            filled = int((self.done % (width + 1)) * (width + 1) / (width + 1))
            pct = f"{_human(self.done):>7}"
        bar = "█" * filled + "─" * (width - filled)
        line = f"\r{self.label} [{bar}] {pct}"
        sys.stdout.write(line)
        sys.stdout.flush()
        self._started = True

    def finish(self):
        if self._started and USE_COLOR:
            sys.stdout.write("\r" + " " * (_term_width() - 1) + "\r")
            sys.stdout.flush()
            self._started = False
