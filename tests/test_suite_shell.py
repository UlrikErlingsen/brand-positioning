from pathlib import Path

from streamlit.testing.v1 import AppTest

from positionsignal import __version__


ROOT = Path(__file__).parents[1]
APP = str(ROOT / "app.py")
UI = ROOT / "src" / "positionsignal" / "ui"
OLD_COLOURS = ("#173c3a", "#d95b40", "#83d2b4", "#f2c66d", "#17322e", "#102c2a", "#59716c", "#9b3e2b", "#f8f5ed")


def test_shared_signal_shell_renders() -> None:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    body = "\n".join(str(item.value) for item in app.markdown)
    sidebar = "\n".join(str(item.value) for item in app.sidebar.markdown)
    assert "OPEN PERCEPTUAL MAPPING" in body
    assert "POSITIONING, WITHOUT THE BLACK BOX" in body
    assert f"Position Signal v{__version__}" in body
    assert "Perceptual evidence, not market truth" in body
    assert "Part of the Signal suite" in body
    assert "AGPL-3.0-or-later" in body
    assert "sg-mast" in body  # the shared Signal masthead
    assert "sg-hero" in body  # the shared Signal hero
    assert "sg-foot" in body  # the shared Signal footer
    assert "decision support, not objective market truth" in body
    assert "See where brands stand." in sidebar
    assert "sg-side" in sidebar  # the shared Signal sidebar lockup


def test_app_uses_shared_signal_theme_instead_of_pasted_styles() -> None:
    standalone = (ROOT / "app.py").read_text(encoding="utf-8")
    ui_source = (UI / "app.py").read_text(encoding="utf-8")
    plotting = (UI / "plotting.py").read_text(encoding="utf-8")
    theme = (UI / "signal_theme.py").read_text(encoding="utf-8")
    assert 'st.set_page_config(**sig.page_config("position"))' in standalone
    assert "sig.apply(NS)" in ui_source
    assert "<style>" not in standalone + ui_source + plotting
    assert "unsafe_allow_html" not in standalone + ui_source  # every styled block goes through signal_theme
    for old_colour in OLD_COLOURS:
        assert old_colour not in (standalone + ui_source + plotting).lower(), old_colour
    assert "st.plotly_chart" not in ui_source  # sig.chart sets the per-app template and theme=None
    assert (UI / "assets" / "marks" / "positionsignal-mark-64.png").exists()
    assert ":focus-visible" in theme
    assert "@media (max-width:760px)" in theme
    assert "@media (prefers-reduced-motion:reduce)" in theme
    assert "friendly_message" in ui_source


def test_every_figure_carries_the_position_template() -> None:
    import pandas as pd

    from positionsignal.mapping import fit_perceptual_map, relative_attribute_positions
    from positionsignal.ui import plotting
    from positionsignal.ui import signal_theme as sig

    profiles = pd.DataFrame(
        {
            "quality": [6.1, 5.7, 5.2, 5.9, 5.0],
            "value": [4.7, 5.2, 6.2, 4.9, 5.5],
            "innovation": [6.2, 5.3, 4.5, 5.1, 5.8],
            "style": [5.4, 6.3, 4.2, 4.4, 6.1],
        },
        index=pd.Index(["A", "B", "C", "D", "E"], name="brand"),
    )
    result = fit_perceptual_map(profiles)
    figures = [
        plotting.perceptual_map_figure(result, target_brand="A"),
        plotting.correlation_circle_figure(result),
        plotting.scree_figure(result),
        plotting.profile_heatmap_figure(result),
        plotting.competitor_distance_figure(result, "A"),
        plotting.relative_position_figure(relative_attribute_positions(result, "A"), "A"),
    ]
    for figure in figures:
        layout = figure.layout.template.layout
        assert "Figtree" in layout.font.family
        assert layout.colorway[0] == sig.FAMILIES["brand"]["600"]
    focus = next(trace for trace in figures[0].data if trace.name == "Focus brand")
    assert focus.marker.color == sig.app("position")["fam"]["600"]


def test_readme_matches_suite_information_architecture() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # Signal README template order: readers find the same section in the same place in every repo.
    sections = [
        "## Read this first",
        "## Scope",
        "## Try the demo in three minutes",
        "## Data contract",
        "## Analysis contract",
        "## Methods",
        "## Decision statuses",
        "## Exports",
        "## Run locally",
        "## Privacy",
        "## No install? Give this file to an AI",
        "## Development",
        "## Where this fits in Signal",
        "## References",
        "## Originality and license",
    ]
    positions = [readme.find(f"\n{heading}\n") for heading in sections]
    assert all(position >= 0 for position in positions), dict(zip(sections, positions, strict=True))
    assert positions == sorted(positions)
    assert readme.startswith('<p align="center">\n  <img src="assets/positionsignal-banner.png"')
    assert "assets/positionsignal-banner.svg" not in readme
    assert "Signal-Brand-b2622d" in readme  # family badge in the Brand 600 colour
    assert "github.com/UlrikErlingsen/brand-positioning/actions" in readme  # tests badge
    assert "Open perceptual mapping for marketers" in readme
    assert "**Position Signal**" in readme
    assert "PositionSignal" not in readme
    assert '<img src="assets/positionsignal-mark-64.png"' in readme  # suite footer
    assert "Creator Signal" not in readme
    # Honesty statements and scope limits survive the restructure.
    assert "Treat the map as decision support, not objective market truth." in readme
    assert "does not label empty map space as demand" in readme
    assert "A perceptual gap is not demand" in readme
    assert "Perception is not preference." in readme
    assert "no warranty is provided" in readme
    for path in (
        "assets/positionsignal-banner.png",
        "assets/positionsignal-mark-64.png",
        "assets/positionsignal-social.png",
    ):
        assert (ROOT / path).exists()
    assert not (ROOT / "assets" / "positionsignal-banner.svg").exists()


def test_runtime_scaffolding_is_private_and_health_checked() -> None:
    config = (ROOT / ".streamlit" / "config.toml").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    launcher = (ROOT / "run_app.command").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")

    assert "gatherUsageStats = false" in config
    assert 'base = "light"' in config
    assert 'primaryColor = "#b2622d"' in config  # Signal Brand family, 600 step
    assert "USER positionsignal" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "chown" not in dockerfile
    assert "8501" in dockerfile
    assert "--browser.gatherUsageStats=false" in launcher
    assert "POSITIONSIGNAL_PORT" in launcher
    # No built-in data limit locally: Streamlit's uploader takes 10,000 MB unless the launch variable says otherwise.
    windows_launcher = (ROOT / "run_app.bat").read_text(encoding="utf-8")
    assert "maxUploadSize = 10000" in config
    assert 'MAX_UPLOAD_MB="${POSITIONSIGNAL_MAX_UPLOAD_MB:-10000}"' in launcher
    assert 'set "POSITIONSIGNAL_MAX_UPLOAD_MB=10000"' in windows_launcher
    assert "--server.maxUploadSize=%POSITIONSIGNAL_MAX_UPLOAD_MB%" in windows_launcher
    assert "STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10000" in dockerfile
    assert "--server.maxUploadSize" not in dockerfile
    assert 'python-version: ["3.10", "3.11", "3.12", "3.13"]' in workflow
    for template in ("bug_report.yml", "feature_request.yml", "config.yml"):
        text = (ROOT / ".github" / "ISSUE_TEMPLATE" / template).read_text(encoding="utf-8")
        assert "Track Signal" not in text and "brand-tracking" not in text
    assert "Position Signal" in (ROOT / ".github" / "ISSUE_TEMPLATE" / "bug_report.yml").read_text(encoding="utf-8")
