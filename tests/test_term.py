from upkeep.term import print_table


class TestEmptyTable:
    """cmd_check prints a table of only the non-error rows.

    When every app fails that table is empty, and it used to crash:
    natural_widths() called max(len(header)) on a single int, and max() on an
    int is a TypeError. The user saw a traceback instead of the errors.
    """

    def test_no_rows(self):
        print_table([], ["App", "Local", "Remote", "Status"])

    def test_one_row(self):
        print_table([("a", "1.0", "1.1", "outdated")], ["App", "Local", "Remote", "Status"])

    def test_no_headers(self):
        print_table([], [])

    def test_mixed_widths(self):
        print_table(
            [("a very long app name here", "1", "2", "x"), ("b", "2", "3", "y")],
            ["App", "Local", "Remote", "Status"],
        )
