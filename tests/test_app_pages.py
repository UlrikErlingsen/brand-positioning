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
def test_every_page_renders_on_first_open(page: str) -> None:
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    app.sidebar.radio[0].set_value(page).run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == page
    assert app.session_state["position:source_name"] == "demo_sneaker_ratings.csv"


def test_fresh_session_opens_with_the_fictional_demo_mapped() -> None:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "Welcome"
    assert app.session_state["position:source_name"] == "demo_sneaker_ratings.csv"
    body = "\n".join(str(markdown.value) for markdown in app.markdown)
    assert "fictional sneaker market is already loaded and mapped" in body
    setup = app.session_state["position:setup"]
    assert setup["respondent_column"] == "respondent_id"
    assert setup["weight_column"] == "sample_weight"
    assert len(setup["attributes"]) == 8
    result = app.session_state["position:map_result"]
    assert len(result.brand_coordinates) == 6
    assert app.session_state["position:bootstrap_result"] is None

    # The map page shows results without clicking Save or Build.
    app.sidebar.radio[0].set_value("2 · Build the map").run()
    assert not app.exception, [error.value for error in app.exception]
    assert any(metric.label == "Variance in 2-D" for metric in app.metric)
    assert len(app.get("plotly_chart")) >= 1

    app.sidebar.radio[0].set_value("4 · Interpret & export").run()
    assert not app.exception, [error.value for error in app.exception]
    assert any(metric.label == "Closest profile" for metric in app.metric)
    assert any(button.label == "Excel evidence pack" for button in app.get("download_button"))


def test_welcome_button_opens_the_preloaded_map() -> None:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    _button(app.button, "See the fictional market map").click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.sidebar.radio[0].value == "2 · Build the map"
    assert any(metric.label == "Variance in 2-D" for metric in app.metric)


def test_an_upload_replaces_the_preloaded_demo() -> None:
    profiles = (Path(__file__).parents[1] / "examples" / "demo_brand_profiles.csv").read_bytes()
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    assert app.session_state["position:map_result"] is not None

    app.sidebar.file_uploader[0].set_value(("my_profiles.csv", profiles, "text/csv")).run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["position:source_name"] == "my_profiles.csv"
    assert app.session_state["position:map_result"] is None  # the demo map does not survive new data
    assert app.session_state["position:profile_data"] is None
    assert app.sidebar.radio[0].value == "1 · Data & setup"
    assert any(metric.label == "Rows" and metric.value == "6" for metric in app.metric)
    app.run()
    assert app.session_state["position:source_name"] == "my_profiles.csv"


def test_clearing_data_does_not_preload_the_demo_again() -> None:
    app = AppTest.from_file(APP, default_timeout=60)
    app.run()
    _button(app.sidebar.button, "Clear data and results").click().run()

    assert not app.exception, [error.value for error in app.exception]
    assert app.session_state["position:tables"] is None
    for page in PAGES:
        app.sidebar.radio[0].set_value(page).run()
        assert not app.exception, [error.value for error in app.exception]
        assert app.session_state["position:tables"] is None
    _button(app.sidebar.button, "Demo · sneaker ratings").click().run()
    assert app.session_state["position:source_name"] == "demo_sneaker_ratings.csv"


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
