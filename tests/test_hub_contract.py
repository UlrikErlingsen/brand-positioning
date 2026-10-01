"""Signal Hub contract: importable UI entry point, Streamlit only under ui/, slug-namespaced state."""

import ast
from pathlib import Path
import re
import subprocess
import sys

import pytest
from streamlit.testing.v1 import AppTest

from positionsignal import __version__


ROOT = Path(__file__).parents[1]
PACKAGE = ROOT / "src" / "positionsignal"
UI = PACKAGE / "ui"
UI_ONLY_LIBRARIES = {"streamlit", "plotly"}
PAGES = [
    "Welcome",
    "1 · Data & setup",
    "2 · Build the map",
    "3 · Compare waves & segments",
    "4 · Interpret & export",
    "Methods & limits",
]
RENDER_SCRIPT = """
from positionsignal.ui import render

render()
"""


def _imported_roots(path: Path) -> set[str]:
    roots: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def _button(buttons, label: str):
    return next(button for button in buttons if button.label == label)


def _widgets(app: AppTest) -> list:
    return [
        *app.radio, *app.selectbox, *app.multiselect, *app.checkbox, *app.toggle, *app.button,
        *app.slider, *app.select_slider, *app.number_input,
    ]


def _assert_namespaced(app: AppTest) -> None:
    assert not app.exception, [error.value for error in app.exception]
    widgets = _widgets(app)
    assert widgets
    unkeyed = [(type(widget).__name__, widget.label) for widget in widgets if widget.key is None]
    assert not unkeyed, unkeyed
    assert all(widget.key.startswith("position:") for widget in widgets), [widget.key for widget in widgets]


def test_ui_entry_point_matches_the_hub_contract() -> None:
    from positionsignal.ui import APP_INFO, render

    assert callable(render)
    assert APP_INFO == {
        "product": "Position Signal",
        "version": __version__,
        "repo": "brand-positioning",
        "slug": "position",
    }


def test_only_the_ui_package_imports_streamlit_or_plotly() -> None:
    offenders = {
        str(path.relative_to(PACKAGE)): sorted(_imported_roots(path) & UI_ONLY_LIBRARIES)
        for path in PACKAGE.rglob("*.py")
        if UI not in path.parents and _imported_roots(path) & UI_ONLY_LIBRARIES
    }
    assert not offenders, offenders


def test_core_package_imports_without_streamlit_or_plotly() -> None:
    # A fresh interpreter, so modules already imported by other tests cannot hide a stray import.
    code = (
        f"import sys\nsys.path.insert(0, {str(ROOT / 'src')!r})\n"
        "import positionsignal, positionsignal.comparison, positionsignal.errors, positionsignal.io, "
        "positionsignal.mapping, positionsignal.validation\n"
        "loaded = sorted(name for name in ('streamlit', 'plotly') if name in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr


def test_render_never_sets_page_config_or_navigation() -> None:
    for path in UI.glob("*.py"):
        if path.name == "signal_theme.py":
            continue
        source = path.read_text(encoding="utf-8")
        for call in ("st.set_page_config(", "st.navigation(", "st.Page("):
            assert call not in source, (path.name, call)


def test_render_runs_from_a_script_without_set_page_config() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].key == "position:page"
    assert "position:tables" in app.session_state
    assert "tables" not in app.session_state
    body = "\n".join(str(item.value) for item in app.markdown)
    assert "POSITIONING, WITHOUT THE BLACK BOX" in body
    assert f"Position Signal v{__version__}" in body


def test_render_loads_the_packaged_demo_and_navigates() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()
    _button(app.button, "Start with a fictional market").click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "1 · Data & setup"
    assert app.session_state["position:source_name"] == "demo_sneaker_ratings.csv"
    assert any(metric.label == "Rows" and metric.value == "1,080" for metric in app.metric)


@pytest.mark.parametrize("page", PAGES)
def test_every_widget_key_is_namespaced(page: str) -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.run()
    _button(app.sidebar.button, "Demo · sneaker ratings").click().run()
    app.sidebar.radio[0].set_value(page).run()

    _assert_namespaced(app)


def test_widget_keys_stay_namespaced_through_the_full_workflow() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=180)
    app.run()
    _button(app.sidebar.button, "Demo · sneaker ratings").click().run()
    _button(app.button, "Save this data setup").click().run()
    assert app.sidebar.radio[0].value == "2 · Build the map"
    _assert_namespaced(app)

    _button(app.button, "Build perceptual map").click().run()
    assert app.session_state["position:map_result"] is not None
    _assert_namespaced(app)

    _button(app.button, "Interpret this position").click().run()
    assert app.sidebar.radio[0].value == "4 · Interpret & export"
    _assert_namespaced(app)

    app.sidebar.radio[0].set_value("3 · Compare waves & segments").run()
    _button(app.button, "Run position comparisons").click().run()
    assert app.session_state["position:comparison_result"] is not None
    _assert_namespaced(app)


def test_clearing_data_leaves_other_apps_state_alone() -> None:
    app = AppTest.from_string(RENDER_SCRIPT, default_timeout=120)
    app.session_state["track:raw_data"] = "another app's state"
    app.run()
    _button(app.sidebar.button, "Demo · sneaker ratings").click().run()
    _button(app.sidebar.button, "Clear data and results").click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["track:raw_data"] == "another app's state"
    assert app.session_state["position:tables"] is None
    assert app.sidebar.radio[0].value == "Welcome"


def test_session_state_and_widget_keys_go_through_the_namespace_helper() -> None:
    source = (UI / "app.py").read_text(encoding="utf-8")
    state_keys = re.findall(r"session_state(?:\[|\.get\(|\.pop\(|\.setdefault\()\s*([^,\])]+)", source)
    widget_keys = re.findall(r"\bkey=([^,)\n]+)", source)
    assert state_keys and widget_keys
    # The two clean-up loops delete keys they selected by the namespace prefix (k(...) or f"{NS}:").
    assert all(key.startswith("k(") or key == "key" for key in state_keys), state_keys
    # sorted(..., key=str.casefold) orders labels; every other key= is a widget key.
    assert all(key.startswith("k(") or key == "str.casefold" for key in widget_keys), widget_keys
    assert 'NS = "position"' in source


def test_render_and_demos_work_from_an_installed_package_without_the_repo(tmp_path: Path) -> None:
    """Signal Hub installs the release as a normal wheel: only src/positionsignal and its package data exist."""
    tomllib = pytest.importorskip("tomllib")
    import shutil

    package_data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["tool"]["setuptools"][
        "package-data"
    ]
    site = tmp_path / "site"
    for source in PACKAGE.rglob("*.py"):
        target = site / "positionsignal" / source.relative_to(PACKAGE)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for package, patterns in package_data.items():
        base = PACKAGE.joinpath(*package.split(".")[1:])
        for pattern in patterns:
            for source in base.glob(pattern):
                target = site / "positionsignal" / source.relative_to(PACKAGE)
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)

    code = (
        f"import sys\nsys.path.insert(0, {str(site)!r})\n"
        "from streamlit.testing.v1 import AppTest\n"
        "import positionsignal.ui.app as ui_app\n"
        f"assert ui_app.__file__.startswith({str(site)!r}), ui_app.__file__\n"
        f"app = AppTest.from_string({RENDER_SCRIPT!r}, default_timeout=120)\n"
        "app.run()\n"
        "for label in ('Demo · sneaker ratings', 'Demo · brand summary'):\n"
        "    next(b for b in app.sidebar.button if b.label == label).click().run()\n"
        "    assert not app.exception, [e.value for e in app.exception]\n"
        "    assert not app.error, [e.value for e in app.error]\n"
        "    assert app.session_state['position:tables'], label\n"
        "assert any('sg-mast' in str(m.value) for m in app.markdown)\n"
    )
    # Run outside the repository so no repo-root file (examples/, assets/, docs/) can be reached by accident.
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, timeout=240, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_ui_reads_runtime_files_only_from_inside_the_package() -> None:
    from positionsignal.ui import app as ui_app

    demo_dir = ui_app.DEMO_DATA.resolve()
    assert UI.resolve() in demo_dir.parents
    for name in ("demo_sneaker_ratings.csv", "demo_brand_profiles.csv"):
        assert (demo_dir / name).is_file()
    for path in UI.glob("*.py"):
        source = path.read_text(encoding="utf-8")
        # No repo-root lookups: examples/, docs/ and assets/ are not part of an installed wheel.
        for repo_root_path in ('"examples"', '"docs"', "parents[", "ROOT /"):
            assert repo_root_path not in source, (path.name, repo_root_path)
