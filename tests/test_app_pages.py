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
    assert app.session_state["nav_target"] == "1 · Data & setup"
    assert app.session_state["source_name"] == source_name
    assert app.session_state["tables"]
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
    assert setup_app.session_state["profile_data"] is not None
    assert setup_app.session_state["setup"]["respondent_column"] == "respondent_id"
    assert setup_app.session_state["setup"]["weight_column"] == "sample_weight"
    assert len(setup_app.session_state["setup"]["attributes"]) == 8
    assert setup_app.session_state["nav_target"] == "2 · Build the map"

    # Start a settled AppTest tree from the setup saved above. Streamlit 1.59's
    # test harness otherwise retains removed, unkeyed setup widgets across the
    # app's route-changing st.rerun and cannot serialize their stale state.
    map_app = AppTest.from_file(APP, default_timeout=60)
    for key in (
        "tables",
        "source_name",
        "active_table",
        "source_fingerprint",
        "profile_data",
        "setup",
    ):
        map_app.session_state[key] = setup_app.session_state[key]
    map_app.session_state["nav_target"] = "2 · Build the map"
    map_app.session_state["nav_epoch"] = 0
    map_app.run()

    uncertainty = next(
        widget for widget in map_app.toggle
        if widget.label == "Estimate respondent-sampling uncertainty"
    )
    assert uncertainty.value is False
    _button(map_app.button, "Build perceptual map").click().run()

    assert not map_app.exception, [error.value for error in map_app.exception]
    result = map_app.session_state["map_result"]
    assert result is not None
    assert map_app.session_state["bootstrap_result"] is None
    assert map_app.session_state["map_settings"]["bootstrap"] is False
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
    assert any(header.value == "Methods & limits" for header in app.header)
    assert [tab.label for tab in app.tabs] == [
        "Plain-language method",
        "Technical specification",
        "Uncertainty",
        "Limits & references",
    ]
    body = "\n".join(str(markdown.value) for markdown in app.markdown)
    assert "PCA on aggregated brand profiles" in body
    assert "resamples **respondents**" in body
    assert "Likert-style ratings" in body
    assert len(app.latex) == 4
