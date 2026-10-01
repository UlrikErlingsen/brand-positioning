"""Position Signal user interface: the Signal Hub entry point.

The only package under ``positionsignal`` that imports Streamlit or Plotly. ``render()`` draws the whole app on the
current page and never calls ``st.set_page_config``; the standalone ``app.py`` or Signal Hub owns the page config.
"""

from positionsignal import __version__
from positionsignal.ui import signal_theme
from positionsignal.ui.app import render

APP_INFO = {"product": "Position Signal", "version": __version__, "repo": "brand-positioning", "slug": "position"}

__all__ = ["APP_INFO", "render", "signal_theme"]
