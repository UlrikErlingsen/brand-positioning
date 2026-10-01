from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest


APP = str(Path(__file__).parents[1] / "app.py")
PAGES = [
    "Welcome",
    "1 · Data & setup",
    "2 · Build the map",
    "3 · Compare waves & segments",
    "4 · Interpret & export",
    "Methods & limits",
]


def _button(buttons, label: str):
    return next(button for button in buttons if button.label == label)


@pytest.mark.parametrize("page", PAGES)
def test_every_page_renders_without_data(page: str) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    app.sidebar.radio[0].set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == page


@pytest.mark.parametrize(
    ("button_label", "source_name", "expected_rows"),
    [
        ("Demo · sneaker ratings", "demo_sneaker_ratings.csv", "1,080"),
        ("Demo · brand summary", "demo_brand_profiles.csv", "6"),
    ],
)
def test_sidebar_demos_load_and_navigate_to_setup(
    button_label: str,
    source_name: str,
    expected_rows: str,
) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    _button(app.sidebar.button, button_label).click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "1 · Data & setup"
    assert app.session_state["position:page"] == "1 · Data & setup"
    assert app.session_state["position:source_name"] == source_name
    assert app.session_state["position:tables"]
    assert any(metric.label == "Rows" and metric.value == expected_rows for metric in app.metric)


def test_sneaker_demo_setup_saves_and_builds_a_map_without_bootstrap() -> None:
    setup_app = AppTest.from_file(APP, default_timeout=60)
    setup_app.run()
    _button(setup_app.sidebar.button, "Demo · sneaker ratings").click().run()

    assert next(widget for widget in setup_app.selectbox if widget.label.startswith("Respondent ID")).value == "respondent_id"
    assert next(widget for widget in setup_app.selectbox if widget.label == "Survey weight (optional)").value == "sample_weight"
    assert len(next(widget for widget in setup_app.multiselect if widget.label.startswith("Which attributes")).value) == 8

    _button(setup_app.button, "Save this data setup").click().run()
    assert not setup_app.exception, [error.value for error in setup_app.exception]
    assert setup_app.session_state["position:profile_data"] is not None
    assert setup_app.session_state["position:setup"]["respondent_column"] == "respondent_id"
    assert setup_app.session_state["position:setup"]["weight_column"] == "sample_weight"
    assert len(setup_app.session_state["position:setup"]["attributes"]) == 8
    assert setup_app.session_state["position:page"] == "2 · Build the map"

    # Start a settled AppTest tree from the setup saved above, so the map run
    # does not carry the setup page's widget tree across the route change.
    map_app = AppTest.from_file(APP, default_timeout=60)
    for key in (
        "tables",
        "source_name",
        "active_table",
        "source_fingerprint",
        "profile_data",
        "setup",
    ):
        map_app.session_state[f"position:{key}"] = setup_app.session_state[f"position:{key}"]
    map_app.session_state["position:page"] = "2 · Build the map"
    map_app.run()

    uncertainty = next(
        widget for widget in map_app.toggle
        if widget.label == "Estimate respondent-sampling uncertainty"
    )
    assert uncertainty.value is False
    _button(map_app.button, "Build perceptual map").click().run()

    assert not map_app.exception, [error.value for error in map_app.exception]
    result = map_app.session_state["position:map_result"]
    assert result is not None
    assert map_app.session_state["position:bootstrap_result"] is None
    assert map_app.session_state["position:map_settings"]["bootstrap"] is False
    assert len(result.brand_coordinates) == 6
    assert len(result.attribute_coordinates) == 8
    assert 0 < result.variance_2d <= 1
    assert any(metric.label == "Variance in 2-D" for metric in map_app.metric)
    assert len(map_app.get("plotly_chart")) >= 1


def test_methods_page_renders_plain_language_equations_and_limits() -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    app.sidebar.radio[0].set_value("Methods & limits").run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "Methods & limits"
    assert [tab.label for tab in app.tabs] == [
        "Plain-language method",
        "Technical specification",
        "Uncertainty",
        "Limits & references",
    ]
    body = "\n".join(str(markdown.value) for markdown in app.markdown)
    assert "What Position Signal calculates" in body  # the shared Signal page header
    assert "PCA on aggregated brand profiles" in body
    assert "resamples **respondents**" in body
    assert "Likert-style ratings" in body
    assert len(app.latex) == 4
