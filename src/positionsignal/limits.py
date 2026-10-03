"""Data limits: none when Position Signal runs locally; hard caps only in a public demo.

Run on someone's own computer (standalone, a local Signal Hub, or an internal company deployment), the app has no
built-in limit on file size, rows, cells, brands or attributes: memory and processor are the limit. A public demo
sets ``SIGNAL_PUBLIC=1`` (Signal Hub's public Docker image does), and then the caps below protect the shared server.
Every cap lives in this module and is read at call time, so the environment decides.
"""

from __future__ import annotations

import os

DEMO_MAX_UPLOAD_MB = 50
DEMO_MAX_JSON_MB = 30
DEMO_MAX_EXPANDED_WORKBOOK_MB = 250
DEMO_MAX_TABLE_ROWS = 500_000
DEMO_MAX_TOTAL_CELLS = 8_000_000
DEMO_MAX_BRANDS = 60
DEMO_MAX_ATTRIBUTES = 40
DEMO_MAX_BOOTSTRAP_ITERATIONS = 500

DEMO_NOTE = "This is a limit of the public demo; the downloaded app has no such limit."
MEMORY_MESSAGE = (
    "There is not enough memory for this file on this computer. Close other programs, keep only the columns the "
    "map needs, or split the file (for example by wave) and try again."
)


def is_public() -> bool:
    """True only in a public demo deployment (``SIGNAL_PUBLIC=1``)."""
    return os.environ.get("SIGNAL_PUBLIC") == "1"


def _cap(value: int) -> int | None:
    return value if is_public() else None


def max_upload_bytes() -> int | None:
    return _cap(DEMO_MAX_UPLOAD_MB * 1024 * 1024)


def max_json_bytes() -> int | None:
    return _cap(DEMO_MAX_JSON_MB * 1024 * 1024)


def max_expanded_workbook_bytes() -> int | None:
    return _cap(DEMO_MAX_EXPANDED_WORKBOOK_MB * 1024 * 1024)


def max_table_rows() -> int | None:
    return _cap(DEMO_MAX_TABLE_ROWS)


def max_total_cells() -> int | None:
    return _cap(DEMO_MAX_TOTAL_CELLS)


def max_brands() -> int | None:
    return _cap(DEMO_MAX_BRANDS)


def max_attributes() -> int | None:
    return _cap(DEMO_MAX_ATTRIBUTES)


def max_bootstrap_iterations() -> int | None:
    return _cap(DEMO_MAX_BOOTSTRAP_ITERATIONS)


def exceeds(value: int, limit: int | None) -> bool:
    return limit is not None and value > limit


def demo_message(what: str) -> str:
    """A capped message: names the demo limit and says the downloaded app has none."""
    return f"{what} {DEMO_NOTE}"
