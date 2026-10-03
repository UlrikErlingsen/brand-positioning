"""Position Signal Streamlit UI.

Everything that draws the app runs inside ``render()`` (or the functions it calls), so it runs on every rerun,
both in the standalone ``app.py`` and inside Signal Hub. Module-level code here only defines constants and
functions. ``render()`` never calls ``st.set_page_config`` or ``st.navigation``.
"""

from __future__ import annotations

import hashlib
import inspect
import json
import os
from pathlib import Path
import platform
import traceback

import numpy as np
import pandas as pd
import sklearn
import streamlit as st

from positionsignal import __version__
from positionsignal.comparison import ComparisonConfig, PositionComparisonResult, analyze_position_comparisons
from positionsignal.errors import DataProblem, friendly_message
from positionsignal import limits
from positionsignal.io import LoadedData, load_data, results_to_excel, results_to_json, tables_to_csv_zip
from positionsignal.mapping import (
    BootstrapResult,
    MapResult,
    bootstrap_respondent_maps,
    fit_perceptual_map,
    nearest_competitors,
    relative_attribute_positions,
)
from positionsignal.ui import signal_theme as sig
from positionsignal.ui.plotting import (
    competitor_distance_figure,
    correlation_circle_figure,
    perceptual_map_figure,
    profile_heatmap_figure,
    relative_position_figure,
    scree_figure,
)
from positionsignal.validation import (
    ProfileData,
    data_quality_report,
    infer_brand_column,
    infer_respondent_column,
    infer_weight_column,
    likely_pii_columns,
    numeric_candidates,
    prepare_brand_profiles,
)


NS = "position"


def k(name: str) -> str:
    """Namespace a session-state or widget key with the app slug, so apps can share one Hub session."""
    return f"{NS}:{name}"


# The fictional demos ship inside the package (copies of examples/), so they also load from an installed wheel.
DEMO_DATA = Path(__file__).resolve().parent / "demo"
# Opened automatically on first run, with its default setup saved and its default map built, so every page shows
# results before anything is uploaded. It is the respondent-level demo, so uncertainty and comparisons work too.
PRELOADED_DEMO = "demo_sneaker_ratings.csv"
SIDEBAR_TAGLINE = "See where brands stand."
MASTHEAD_KICKER = "OPEN PERCEPTUAL MAPPING"
MASTHEAD_PROMISES = ["Local-first", "Explainable", "Open source"]
FOOTER_LINE = "Perceptual evidence, not market truth"
CAUTION = (
    "**Treat the map as decision support, not objective market truth.** It depends on the respondents, brands, "
    "attributes, scaling, and missing-data choices. A two-dimensional view necessarily leaves information out."
)
NONE = "None — not present in this data"

STATE_DEFAULTS = (
    ("tables", None), ("source_name", None), ("active_table", None), ("source_fingerprint", None),
    ("profile_data", None), ("setup", None), ("map_result", None), ("bootstrap_result", None),
    ("comparison_result", None), ("comparison_config", None),
    ("map_settings", None), ("upload_epoch", 0), ("uploader_had_file", False),
)
ANALYSIS_KEYS = (
    "profile_data", "setup", "map_result", "bootstrap_result", "map_settings",
    "comparison_result", "comparison_config",
)
# Widgets whose options depend on the loaded table. Their state is forgotten when the data change, so their
# defaults (inferred roles, suggested attributes) are recomputed for the new table.
DATA_WIDGET_PREFIXES = ("setup_", "build_", "compare_", "interpret_")


def full_width(widget, *args, **kwargs):
    """Use Streamlit's current width API while retaining older compatibility."""
    try:
        parameters = inspect.signature(widget).parameters
    except (TypeError, ValueError):
        parameters = {}
    # Current releases may still expose the deprecated boolean alongside the
    # new string API. A string default identifies the new ``Width`` contract;
    # older releases fall back to the boolean without raising a warning.
    width_parameter = parameters.get("width")
    if width_parameter is not None and isinstance(width_parameter.default, str):
        kwargs["width"] = "stretch"
    elif "use_container_width" in parameters:
        kwargs["use_container_width"] = True
    return widget(*args, **kwargs)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, DataProblem) and os.getenv("POSITIONSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def _ensure_state() -> None:
    for name, default in STATE_DEFAULTS:
        st.session_state.setdefault(k(name), default)
    # First run only: "Clear data and results" keeps the app empty instead of preloading the demo again.
    if not st.session_state.get(k("demo_preloaded")):
        st.session_state[k("demo_preloaded")] = True
        if not st.session_state.get(k("tables")):
            try:
                preload_demo()
            except Exception as exc:
                for name, default in STATE_DEFAULTS:
                    st.session_state[k(name)] = default
                show_error(exc)


def _forget_data_widgets() -> None:
    prefixes = tuple(k(prefix) for prefix in DATA_WIDGET_PREFIXES)
    for key in [key for key in st.session_state if str(key).startswith(prefixes)]:
        del st.session_state[key]


def _clear_namespace() -> None:
    """Forget this app's data, results and widgets only; other Signal Hub apps keep their state."""
    for key in [key for key in st.session_state if str(key).startswith(f"{NS}:")]:
        del st.session_state[key]


def clear_analysis() -> None:
    for name in ANALYSIS_KEYS:
        st.session_state[k(name)] = None
    _forget_data_widgets()


def set_loaded(loaded: LoadedData, fingerprint: str | None = None) -> None:
    st.session_state[k("tables")] = loaded.tables
    st.session_state[k("source_name")] = loaded.source_name
    st.session_state[k("active_table")] = next(iter(loaded.tables))
    st.session_state[k("source_fingerprint")] = fingerprint
    clear_analysis()


def go_to(page_name: str) -> None:
    """Ask the next run to open another page. The page radio picks the request up before it is drawn."""
    st.session_state[k("nav_request")] = page_name


def load_demo(filename: str) -> None:
    raw = (DEMO_DATA / filename).read_bytes()
    set_loaded(load_data(raw, name=filename), hashlib.sha256(raw).hexdigest())
    go_to("1 · Data & setup")


def _default_setup(frame: pd.DataFrame) -> dict[str, object]:
    """The roles page 1 suggests for a fresh table: inferred brand, respondent and weight, first 12 attributes."""
    columns = [str(column) for column in frame.columns]
    inferred_brand = infer_brand_column(frame)
    brand_column = inferred_brand if inferred_brand in columns else columns[0]
    respondent_column = infer_respondent_column(frame, brand_column)
    if respondent_column not in columns or respondent_column == brand_column:
        respondent_column = None
    weight_column = infer_weight_column(frame)
    if weight_column not in columns or weight_column in {brand_column, respondent_column}:
        weight_column = None
    candidates = numeric_candidates(frame, [column for column in (brand_column, respondent_column, weight_column) if column])
    return {
        "brand_column": brand_column, "respondent_column": respondent_column, "weight_column": weight_column,
        "attributes": candidates[: min(12, len(candidates))], "missing_policy": "drop_attributes",
    }


def preload_demo() -> None:
    """Load the fictional demo, save its suggested setup and build the default map (standardized, no bootstrap).

    Uses the same functions and defaults as the Save and Build buttons, without changing pages.
    """
    raw = (DEMO_DATA / PRELOADED_DEMO).read_bytes()
    set_loaded(load_data(raw, name=PRELOADED_DEMO), hashlib.sha256(raw).hexdigest())
    frame = current_frame()
    roles = _default_setup(frame)
    prepared = prepare_brand_profiles(frame, **roles)
    result = fit_perceptual_map(prepared.profiles, scale_attributes=True)
    st.session_state[k("profile_data")] = prepared
    st.session_state[k("setup")] = {**roles, "attributes": list(prepared.attributes)}
    st.session_state[k("map_result")] = result
    st.session_state[k("bootstrap_result")] = None
    st.session_state[k("map_settings")] = {
        "focus_brand": prepared.brands[0], "scale_attributes": True,
        "show_vectors": True, "vector_limit": min(10, len(prepared.attributes)),
        "bootstrap": False, "bootstrap_iterations": 0, "confidence": None, "random_seed": None,
    }


def frame_audit(frame: pd.DataFrame) -> dict[str, object]:
    """Column audit for the active table, computed once per loaded file so reruns stay fast on large files."""
    key = (st.session_state.get(k("source_fingerprint")), st.session_state.get(k("active_table")), id(frame), frame.shape)
    cached = st.session_state.get(k("frame_audit"))
    if isinstance(cached, dict) and cached.get("key") == key:
        return cached
    audit: dict[str, object] = {
        "key": key,
        "missing_cells": int(frame.isna().sum().sum()),
        "pii": likely_pii_columns(frame),
        "quality": data_quality_report(frame),
        "numeric": numeric_candidates(frame),
    }
    st.session_state[k("frame_audit")] = audit
    return audit


def audited_candidates(frame: pd.DataFrame, excluded: list[str]) -> list[str]:
    blocked = set(excluded)
    return [column for column in frame_audit(frame)["numeric"] if column not in blocked]


def upload_limit_note() -> str:
    """The upload limit that applies here: a demo cap online, otherwise only the Streamlit upload setting."""
    if limits.is_public():
        return limits.demo_message(
            f"Files up to {limits.DEMO_MAX_UPLOAD_MB} MB and {limits.DEMO_MAX_TABLE_ROWS:,} rows."
        )
    try:
        server_mb = int(st.get_option("server.maxUploadSize"))
    except Exception:  # pragma: no cover - the option exists in every supported Streamlit version
        server_mb = 10_000
    return (
        f"No built-in data limit: your computer's memory is the limit. The uploader accepts files up to "
        f"{server_mb:,} MB (set POSITIONSIGNAL_MAX_UPLOAD_MB before launch to change it). CSV reads fastest."
    )


def current_frame() -> pd.DataFrame | None:
    tables = st.session_state.get(k("tables"))
    if not tables:
        return None
    name = st.session_state.get(k("active_table")) or next(iter(tables))
    return tables[name]


def template_panel() -> None:
    with st.expander("What data do I need? Templates inside"):
        st.markdown(
            "Use **one row per respondent and brand** with numeric attribute columns, or **one row per brand** "
            "when the numbers are already brand means. Brand and attribute labels can be your own."
        )
        respondent_template = pd.DataFrame(
            {
                "respondent_id": ["R001", "R001", "R002", "R002"],
                "brand": ["Your brand", "Competitor A", "Your brand", "Competitor A"],
                "innovative": [6, 4, 5, 3], "trustworthy": [5, 6, 6, 5], "good_value": [4, 5, 5, 6],
            }
        )
        brand_template = pd.DataFrame(
            {"brand": ["Your brand", "Competitor A", "Competitor B"], "innovative": [5.5, 3.5, 4.2], "trustworthy": [5.3, 5.5, 4.6], "good_value": [4.5, 5.5, 3.9]}
        )
        left, middle, right = st.columns(3)
        full_width(
            left.download_button, "Respondent CSV", respondent_template.to_csv(index=False).encode(),
            "positionsignal_respondent_template.csv", "text/csv", key=k("template_respondent"),
        )
        full_width(
            middle.download_button, "Brand-summary CSV", brand_template.to_csv(index=False).encode(),
            "positionsignal_brand_template.csv", "text/csv", key=k("template_brand"),
        )
        full_width(
            right.download_button, "Excel templates", results_to_excel({"Respondent ratings": respondent_template, "Brand profiles": brand_template}),
            "positionsignal_templates.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=k("template_excel"),
        )
        st.caption("Ratings should all point in the same semantic direction: higher means more of the named attribute. Reverse-code items before upload.")


def render_welcome() -> None:
    sig.hero(
        NS,
        eyebrow="POSITIONING, WITHOUT THE BLACK BOX",
        title="See the market.",
        em="Find your position.",
        body=(
            "Turn brand-attribute ratings into a perceptual map that shows where your brand sits, which competitors "
            "are genuinely closest, and which attributes create the separation."
        ),
        pills=["Excel & CSV", "No account", "Transparent PCA", "Exportable evidence"],
    )
    if st.session_state.get(k("source_name")) == PRELOADED_DEMO and st.session_state.get(k("map_result")) is not None:
        sig.note(
            "info",
            "**A fictional sneaker market is already loaded and mapped:** 180 made-up respondents rating six made-up "
            "brands on eight attributes. Open **2 · Build the map** or **4 · Interpret & export** to see the results, "
            "or upload your own file in the sidebar to replace the demo.",
        )
    sig.note("warn", CAUTION)
    sig.cards(
        [
            ("STEP 01", "Define the market", "Bring the brand set and attributes that belong to the decision you are making."),
            ("STEP 02", "Build the map", "Position Signal aggregates ratings, standardizes transparently, and fits one auditable PCA biplot."),
            ("STEP 03", "Read the evidence", "See the nearest rivals in the full profile—not only the picture—and export every diagnostic."),
        ]
    )
    metrics = st.columns(4)
    metrics[0].metric("Input", "Ratings")
    metrics[1].metric("Primary method", "PCA biplot")
    metrics[2].metric("Privacy", "Local-first")
    metrics[3].metric("Output", "Evidence pack")
    with st.expander("Where this tool fits"):
        st.markdown(
            "Position Signal is for **perceptual mapping and declared descriptive comparisons from brand-by-attribute ratings**. It is not a full brand tracker, "
            "a demand forecast, a segmentation model, or proof of causal positioning. Use the map to frame strategic "
            "questions, then test those questions with customers and market outcomes."
        )
    if full_width(st.button, "See the fictional market map", type="primary", key=k("start_demo")):
        try:
            preload_demo()
            go_to("2 · Build the map")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    template_panel()


def render_data_setup() -> None:
    sig.header(
        "Step 1",
        "Data and setup",
        "Tell Position Signal which column names each brand and which numeric columns describe perception.",
    )
    frame = current_frame()
    if frame is None:
        st.info("Upload a file in the sidebar or open one of the fictional demos.")
        template_panel()
        return

    audit = frame_audit(frame)
    metrics = st.columns(4)
    metrics[0].metric("Rows", f"{len(frame):,}")
    metrics[1].metric("Columns", f"{len(frame.columns):,}")
    metrics[2].metric("Missing cells", f"{audit['missing_cells']:,}")
    metrics[3].metric("Possible PII fields", f"{len(audit['pii'])}")
    with st.expander("Preview and data-quality audit", expanded=False):
        full_width(st.dataframe, frame.head(30), hide_index=True)
        if len(frame) > 30:
            st.caption(f"Showing the first 30 of {len(frame):,} rows; every calculation uses all rows.")
        full_width(st.dataframe, audit["quality"], hide_index=True)
    pii = list(audit["pii"])
    if pii:
        st.warning("Direct identifiers are unnecessary for positioning. Remove or ignore: " + ", ".join(pii) + ".")

    columns = [str(column) for column in frame.columns]
    inferred_brand = infer_brand_column(frame)
    brand_column = st.selectbox(
        "Which column names the brand or competitor?", columns,
        index=columns.index(inferred_brand) if inferred_brand in columns else 0,
        key=k("setup_brand_column"),
    )
    respondent_choices = [NONE] + [column for column in columns if column != brand_column]
    inferred_respondent = infer_respondent_column(frame, brand_column)
    respondent_column = st.selectbox(
        "Respondent ID (optional, enables honest uncertainty regions)", respondent_choices,
        index=respondent_choices.index(inferred_respondent) if inferred_respondent in respondent_choices else 0,
        key=k("setup_respondent_column"),
    )
    respondent_column = None if respondent_column == NONE else respondent_column
    weight_choices = [NONE] + [column for column in columns if column not in {brand_column, respondent_column}]
    inferred_weight = infer_weight_column(frame)
    weight_column = st.selectbox(
        "Survey weight (optional)", weight_choices,
        index=weight_choices.index(inferred_weight) if inferred_weight in weight_choices else 0,
        key=k("setup_weight_column"),
    )
    weight_column = None if weight_column == NONE else weight_column
    candidates = audited_candidates(frame, [column for column in (brand_column, respondent_column, weight_column) if column])
    prior_setup = st.session_state.get(k("setup")) or {}
    prior_attributes = [column for column in prior_setup.get("attributes", []) if column in candidates]
    attributes = st.multiselect(
        "Which attributes should define the map?", candidates,
        default=prior_attributes or candidates[: min(12, len(candidates))],
        help="Choose ratings where higher means more of the named attribute. Two are required; 4–12 is usually readable.",
        key=k("setup_attributes"),
    )
    missing_label = st.radio(
        "If a whole brand–attribute cell has no usable ratings",
        ["Remove that attribute from every brand (recommended)", "Stop and ask me to fix the data"],
        horizontal=True,
        key=k("setup_missing_policy"),
    )
    missing_policy = "drop_attributes" if missing_label.startswith("Remove") else "error"

    if full_width(st.button, "Save this data setup", type="primary", key=k("setup_save")):
        try:
            with st.spinner("Aggregating the ratings…"):
                prepared = prepare_brand_profiles(
                    frame, brand_column=brand_column, attributes=attributes,
                    respondent_column=respondent_column, weight_column=weight_column,
                    missing_policy=missing_policy,
                )
            st.session_state[k("profile_data")] = prepared
            st.session_state[k("setup")] = {
                "brand_column": brand_column, "respondent_column": respondent_column,
                "weight_column": weight_column, "attributes": list(prepared.attributes),
                "missing_policy": missing_policy,
            }
            st.session_state[k("map_result")] = None
            st.session_state[k("bootstrap_result")] = None
            st.session_state[k("map_settings")] = None
            go_to("2 · Build the map")
            st.rerun()
        except Exception as exc:
            show_error(exc)

    prepared: ProfileData | None = st.session_state.get(k("profile_data"))
    if prepared is not None:
        st.success(f"Ready: {len(prepared.brands)} brands × {len(prepared.attributes)} attributes.")
        if prepared.excluded_incomplete:
            st.warning("Removed because at least one brand had no ratings: " + ", ".join(prepared.excluded_incomplete) + ".")
        if prepared.excluded_constant:
            st.warning("Removed because every brand had the same mean: " + ", ".join(prepared.excluded_constant) + ".")
        if len(prepared.brands) == 3:
            st.warning("With exactly three brands, PCA can retain 100% in two dimensions automatically. That is geometry, not proof of a strong map.")
        if len(prepared.brands) < 5:
            st.info("The map can run, but five or more brands usually give a more useful competitive frame.")
        if len(prepared.brands) > limits.DEMO_MAX_BRANDS or len(prepared.attributes) > limits.DEMO_MAX_ATTRIBUTES:
            st.info(
                f"{len(prepared.brands)} brands × {len(prepared.attributes)} attributes will map, but labels crowd "
                "beyond about 60 brands or 40 attributes. Keep the brands and attributes relevant to the decision."
            )
        minimum_base = int(prepared.counts.loc[:, list(prepared.attributes)].min().min())
        if prepared.has_respondents and minimum_base < 10:
            st.warning(
                f"The smallest brand–attribute cell has {minimum_base} respondent(s). Mapping can continue, but "
                "respondent-sampling uncertainty is fragile below 10 and is disabled below 2."
            )
        tabs = st.tabs(["Aggregated profiles", "Cell bases"])
        with tabs[0]:
            full_width(st.dataframe, prepared.profiles.reset_index(), hide_index=True)
        with tabs[1]:
            full_width(st.dataframe, prepared.counts.reset_index(), hide_index=True)
            st.caption("Bases are the valid ratings in each cell. Weighted files also show Kish effective bases.")
    template_panel()


def fidelity_text(result: MapResult) -> tuple[str, str]:
    retained = result.variance_2d
    if retained >= 0.70:
        return "Clear two-dimensional summary", "The picture retains a large share of variation in this particular brand-profile matrix."
    if retained >= 0.50:
        return "Useful but compressed", "Read the map with the brand-level representation scores; some structure sits beyond the page."
    return "Strongly compressed view", "The first two axes leave most profile variation outside the picture. Use full-profile distances and diagnostics."


def render_map_summary(result: MapResult, focus_brand: str, vector_limit: int, show_vectors: bool) -> None:
    bootstrap: BootstrapResult | None = st.session_state.get(k("bootstrap_result"))
    label, explanation = fidelity_text(result)
    nearest = nearest_competitors(result, focus_brand).iloc[0]
    target_quality = float(
        result.brand_coordinates.set_index("brand").loc[focus_brand, "map_quality"]
    )
    metrics = st.columns(4)
    metrics[0].metric("Variance in 2-D", f"{result.variance_2d:.1%}")
    metrics[1].metric("Focus-brand fit", "—" if not np.isfinite(target_quality) else f"{target_quality:.1%}")
    metrics[2].metric("Nearest profile", str(nearest["competitor"]))
    metrics[3].metric("Distance stress", f"{result.normalized_distance_error:.3f}")
    if result.variance_2d < 0.50:
        st.warning(f"**{label}.** {explanation}")
    else:
        st.info(f"**{label}.** {explanation}")
    figure = perceptual_map_figure(
        result, target_brand=focus_brand, show_attribute_vectors=show_vectors,
        vector_limit=vector_limit, bootstrap=bootstrap,
    )
    sig.chart(
        NS, figure,
        config={"displaylogo": False, "toImageButtonOptions": {"format": "png", "filename": "positionsignal_map", "scale": 2}},
        key=k(f"main_map_{focus_brand}_{vector_limit}_{show_vectors}"),
    )
    st.caption(
        "Nearby dots are similar in the displayed 2-D projection; check full-profile distances before calling brands close. "
        "Arrows point toward increasing reconstructed values; "
        "their reciprocal common scaling with the brand points preserves the rank-two biplot geometry. The origin is "
        "the average selected brand. Quadrants have no fixed strategic meaning."
    )


def render_build_map() -> None:
    sig.header(
        "Step 2",
        "Build the positioning map",
        "Fit one auditable PCA biplot on the saved brand profiles, then check what the two-dimensional picture leaves out.",
    )
    prepared: ProfileData | None = st.session_state.get(k("profile_data"))
    if prepared is None:
        st.info("Save the brand and attribute setup on page 1 first.")
        if full_width(st.button, "Go to data setup", type="primary", key=k("goto_setup")):
            go_to("1 · Data & setup")
            st.rerun()
        return

    st.markdown(
        "Position Signal maps **brand means**, not individual rating rows. This keeps within-brand response noise from "
        "defining the axes while preserving respondent records for optional uncertainty analysis."
    )
    controls = st.columns([1.2, 1])
    focus_brand = controls[0].selectbox("Which brand should be highlighted?", prepared.brands, key=k("build_focus_brand"))
    scaling_label = controls[1].radio(
        "How should attributes influence the map?",
        ["Equal influence (standardize; recommended)", "Keep observed dispersion (center only)"],
        help="Standardization divides each attribute by its sample standard deviation across brands. Center-only PCA lets attributes with larger observed spread drive more of the map.",
        key=k("build_scaling"),
    )
    scale_attributes = scaling_label.startswith("Equal")
    if len(prepared.attributes) < 3:
        st.warning("With only two attributes, the map is simply a rotation of the input plane. Add more relevant attributes if the strategy question is broader.")
    if len(prepared.attributes) > len(prepared.brands) - 1:
        st.caption(
            f"Technical note: {len(prepared.attributes)} attributes are allowed, but with {len(prepared.brands)} brands the PCA rank cannot exceed {len(prepared.brands) - 1}."
        )

    with st.expander("Advanced map controls"):
        show_vectors = st.toggle("Show attribute arrows on the main map", value=True, key=k("build_show_vectors"))
        vector_limit = st.slider(
            "Maximum arrows to label", 2, min(20, len(prepared.attributes)), min(10, len(prepared.attributes)),
            key=k("build_vector_limit"),
        )
        use_bootstrap = False
        iterations = 500
        confidence = 0.90
        seed = 2026
        if prepared.has_respondents:
            use_bootstrap = st.toggle(
                "Estimate respondent-sampling uncertainty",
                value=False,
                help="Resamples respondent IDs, recomputes brand means and PCA, then aligns the maps by orthogonal Procrustes rotation.",
                key=k("build_bootstrap"),
            )
            if use_bootstrap:
                most = limits.max_bootstrap_iterations() or 2000
                iterations = st.slider(
                    "Bootstrap iterations", 200, most, min(500, most), step=100, key=k("build_iterations"),
                )
                if limits.is_public():
                    st.caption(limits.demo_message(f"At most {most:,} iterations."))
                confidence = st.select_slider(
                    "Uncertainty ellipse level", options=[0.80, 0.90, 0.95], value=0.90,
                    format_func=lambda value: f"{value:.0%}", key=k("build_confidence"),
                )
                seed = int(st.number_input(
                    "Random seed", min_value=0, max_value=2_147_483_647, value=2026, step=1, key=k("build_seed"),
                ))
        else:
            st.caption("Uncertainty ellipses are unavailable for aggregate-only files; there are no respondents to resample.")

    if full_width(st.button, "Build perceptual map", type="primary", key=k("build_map")):
        try:
            with st.spinner("Fitting the brand map…"):
                result = fit_perceptual_map(prepared.profiles, scale_attributes=scale_attributes)
            bootstrap_result = None
            if use_bootstrap:
                bar = st.progress(0.0, text=f"Refitting and aligning {iterations:,} respondent bootstrap maps…")

                def report(done: int, total: int) -> None:
                    bar.progress(done / total, text=f"Bootstrap maps: {done:,} of {total:,}")

                try:
                    bootstrap_result = bootstrap_respondent_maps(
                        prepared, result, iterations=iterations, confidence=confidence, random_state=seed,
                        progress=report,
                    )
                finally:
                    bar.empty()
            st.session_state[k("map_result")] = result
            st.session_state[k("bootstrap_result")] = bootstrap_result
            st.session_state[k("map_settings")] = {
                "focus_brand": focus_brand, "scale_attributes": scale_attributes,
                "show_vectors": show_vectors, "vector_limit": vector_limit,
                "bootstrap": use_bootstrap, "bootstrap_iterations": iterations if use_bootstrap else 0,
                "confidence": confidence if use_bootstrap else None, "random_seed": seed if use_bootstrap else None,
            }
        except Exception as exc:
            show_error(exc)

    result: MapResult | None = st.session_state.get(k("map_result"))
    if result is not None:
        render_map_summary(result, focus_brand, vector_limit, show_vectors)
        tabs = st.tabs(["Coordinates", "Attribute directions", "Expert diagnostics", "Profile matrix"])
        with tabs[0]:
            st.markdown("**Brand scores** are exported in their unscaled PCA units. `map_quality` is the brand cos²: how much of that brand's displacement from the average is visible in 2-D.")
            full_width(st.dataframe, result.brand_coordinates, hide_index=True)
        with tabs[1]:
            sig.chart(NS, correlation_circle_figure(result), config={"displaylogo": False}, key=k("correlation_circle"))
            st.caption(
                "This separate circle uses actual attribute–component correlations. Short or faded arrows are poorly represented in two dimensions. "
                "Angles are interpretable only as associations within this displayed subspace, not as causal relationships."
            )
            full_width(st.dataframe, result.attribute_coordinates, hide_index=True)
        with tabs[2]:
            sig.chart(NS, scree_figure(result), config={"displaylogo": False}, key=k("scree_build"))
            diagnostics = st.columns(3)
            diagnostics[0].metric(
                "Full-vs-map distance r",
                "n/a" if not np.isfinite(result.distance_correlation) else f"{result.distance_correlation:.3f}",
            )
            diagnostics[1].metric("PC1–PC2 eigengap", f"{result.eigengap_pc1_pc2:.3f}")
            diagnostics[2].metric(
                "PC2–PC3 eigengap",
                "n/a" if result.eigengap_pc2_pc3 is None else f"{result.eigengap_pc2_pc3:.3f}",
            )
            if result.eigengap_pc2_pc3 is not None and result.eigengap_pc2_pc3 < 0.10:
                st.warning("PC2 and PC3 are close in variance. The exact two-dimensional plane may be sensitive to sampling or small data changes; 0.10 is a descriptive warning threshold, not a test.")
            full_width(st.dataframe, result.pairwise_distances, hide_index=True)
        with tabs[3]:
            sig.chart(NS, profile_heatmap_figure(result), config={"displaylogo": False}, key=k("profile_heatmap_build"))
            st.caption("Values are centered across brands and, under the default, divided by each attribute's sample standard deviation.")
        bootstrap_result: BootstrapResult | None = st.session_state.get(k("bootstrap_result"))
        if bootstrap_result is not None:
            st.caption(
                f"Bootstrap: {bootstrap_result.successful_iterations} of {bootstrap_result.requested_iterations} maps aligned successfully; "
                f"ellipses show {bootstrap_result.confidence_level:.0%} covariance regions using {bootstrap_result.resampling_scheme}. "
                "Overlap is not a hypothesis test."
            )
        if full_width(st.button, "Interpret this position", type="primary", key=k("interpret_position")):
            st.session_state[k("map_settings")]["focus_brand"] = focus_brand
            go_to("4 · Interpret & export")
            st.rerun()


def _comparison_tables(result: PositionComparisonResult) -> dict[str, pd.DataFrame]:
    tables = {
        "Current profiles": result.current_profiles.reset_index(),
        "Association ownership": result.association_ownership,
        "POP POD candidates": result.pop_pod,
    }
    if not result.wave_change.empty:
        tables["Wave comparison"] = result.wave_change
    if not result.segment_change.empty:
        tables["Segment comparison"] = result.segment_change
    if result.warnings:
        tables["Interpretation warnings"] = pd.DataFrame({"warning": result.warnings})
    return tables


def render_position_comparisons() -> None:
    sig.header(
        "Step 3",
        "Compare waves, segments and association ownership",
        "Use declared comparison roles to inspect movement and segment differences, then classify descriptive "
        "association leadership and points-of-parity/points-of-difference candidates. Nothing on this page proves causality.",
    )
    frame = current_frame()
    if frame is None:
        st.info("Upload a file in the sidebar or open a fictional demo first.")
        return

    columns = [str(column) for column in frame.columns]
    setup = st.session_state.get(k("setup")) or {}
    inferred_brand = setup.get("brand_column") or infer_brand_column(frame)
    brand_column = st.selectbox(
        "Brand column", columns,
        index=columns.index(inferred_brand) if inferred_brand in columns else 0,
        key=k("compare_brand_column"),
    )
    role_choices = [NONE] + [column for column in columns if column != brand_column]
    inferred_respondent = setup.get("respondent_column") or infer_respondent_column(frame, brand_column)
    respondent_column = st.selectbox(
        "Respondent ID (optional)", role_choices,
        index=role_choices.index(inferred_respondent) if inferred_respondent in role_choices else 0,
        key=k("compare_respondent_column"),
    )
    respondent_column = None if respondent_column == NONE else respondent_column
    inferred_weight = setup.get("weight_column") or infer_weight_column(frame)
    weight_column = st.selectbox(
        "Survey weight (optional)", role_choices,
        index=role_choices.index(inferred_weight) if inferred_weight in role_choices else 0,
        key=k("compare_weight_column"),
    )
    weight_column = None if weight_column == NONE else weight_column
    role_columns = {brand_column, respondent_column, weight_column}
    scope_choices = [NONE] + [column for column in columns if column not in role_columns]
    wave_column = st.selectbox("Wave or period (optional)", scope_choices, key=k("compare_wave_column"))
    wave_column = None if wave_column == NONE else wave_column
    segment_column = st.selectbox(
        "Segment (optional)", [NONE] + [column for column in scope_choices[1:] if column != wave_column],
        key=k("compare_segment_column"),
    )
    segment_column = None if segment_column == NONE else segment_column

    candidates = audited_candidates(
        frame, [column for column in (brand_column, respondent_column, weight_column, wave_column, segment_column) if column]
    )
    prior_attributes = [column for column in setup.get("attributes", []) if column in candidates]
    attributes = st.multiselect(
        "Brand attributes", candidates,
        default=prior_attributes or candidates[: min(12, len(candidates))],
        key=k("compare_attributes"),
    )
    brands = sorted(
        frame[brand_column].dropna().astype(str).str.strip().loc[lambda values: values.ne("")].unique().tolist(),
        key=str.casefold,
    )
    focus_brand = st.selectbox("Focus brand", brands, key=k("compare_focus_brand")) if brands else ""

    reference_wave = comparison_wave = None
    if wave_column:
        wave_values = sorted(frame[wave_column].dropna().astype(str).unique().tolist(), key=str.casefold)
        if len(wave_values) >= 2:
            wave_controls = st.columns(2)
            reference_wave = wave_controls[0].selectbox("Reference wave", wave_values, key=k("compare_reference_wave"))
            comparison_wave = wave_controls[1].selectbox(
                "Comparison wave", wave_values, index=1, key=k("compare_comparison_wave")
            )
        else:
            st.warning("The selected wave column needs at least two non-missing values.")

    reference_segment = comparison_segment = None
    if segment_column:
        segment_scope = frame
        if wave_column and comparison_wave is not None:
            segment_scope = frame.loc[frame[wave_column].astype(str) == str(comparison_wave)]
        segment_values = sorted(segment_scope[segment_column].dropna().astype(str).unique().tolist(), key=str.casefold)
        if len(segment_values) >= 2:
            segment_controls = st.columns(2)
            reference_segment = segment_controls[0].selectbox(
                "Reference segment", segment_values, key=k("compare_reference_segment")
            )
            comparison_segment = segment_controls[1].selectbox(
                "Comparison segment", segment_values, index=1, key=k("compare_comparison_segment")
            )
        else:
            st.warning("The selected segment column needs at least two non-missing values in the comparison scope.")

    thresholds = st.columns(2)
    difference_threshold = float(thresholds[0].number_input(
        "POP/POD difference threshold", min_value=0.01, value=0.30, step=0.05,
        help="A focus-brand lead at or above this descriptive threshold becomes a point-of-difference candidate.",
        key=k("compare_difference_threshold"),
    ))
    parity_tolerance = float(thresholds[1].number_input(
        "Parity tolerance", min_value=0.00, value=0.15, step=0.05,
        help="Absolute focus-versus-competitor differences within this band become a point-of-parity candidate.",
        key=k("compare_parity_tolerance"),
    ))
    st.caption("These thresholds are declared decision rules, not universal academic cut-offs or significance tests.")

    if full_width(st.button, "Run position comparisons", type="primary", key=k("compare_run")):
        try:
            config = ComparisonConfig(
                brand_column=brand_column, attributes=tuple(attributes), focus_brand=focus_brand,
                wave_column=wave_column, reference_wave=reference_wave, comparison_wave=comparison_wave,
                segment_column=segment_column, reference_segment=reference_segment,
                comparison_segment=comparison_segment, respondent_column=respondent_column,
                weight_column=weight_column, difference_threshold=difference_threshold,
                parity_tolerance=parity_tolerance,
            )
            with st.spinner("Comparing the declared groups…"):
                st.session_state[k("comparison_result")] = analyze_position_comparisons(frame, config)
            st.session_state[k("comparison_config")] = config
        except Exception as exc:
            show_error(exc)

    result: PositionComparisonResult | None = st.session_state.get(k("comparison_result"))
    if result is not None:
        for warning in result.warnings:
            st.warning(warning)
        ownership_tab, pop_tab, wave_tab, segment_tab = st.tabs(
            ["Association ownership", "POP / POD", "Wave change", "Segment difference"]
        )
        with ownership_tab:
            full_width(st.dataframe, result.association_ownership, hide_index=True)
            st.caption("Leadership is conditional on the brands and attributes in this file; it is not legal ownership or proof of salience.")
        with pop_tab:
            full_width(st.dataframe, result.pop_pod, hide_index=True)
            st.caption("Candidates should be checked for customer importance, credibility, distinctiveness, and business value.")
        with wave_tab:
            if result.wave_change.empty:
                st.info("Select a wave column and two values to calculate wave changes.")
            else:
                full_width(st.dataframe, result.wave_change, hide_index=True)
                st.caption("Intervals use an independent-samples approximation and are descriptive, not causal.")
        with segment_tab:
            if result.segment_change.empty:
                st.info("Select a segment column and two values to calculate segment differences.")
            else:
                full_width(st.dataframe, result.segment_change, hide_index=True)
                st.caption("Segment differences describe the selected groups; they do not establish why the groups differ.")

        tables = _comparison_tables(result)
        config = st.session_state.get(k("comparison_config"))
        metadata = {
            "product": "Position Signal", "version": __version__, "source_file": st.session_state.get(k("source_name")),
            "source_table": st.session_state.get(k("active_table")), "source_sha256": st.session_state.get(k("source_fingerprint")),
            "comparison_config": config.__dict__ if config else None,
            "interpretation": "Descriptive comparisons; no causal identification claimed.",
        }
        manifest = pd.DataFrame({
            "property": list(metadata),
            "value": [json.dumps(value, default=str) if isinstance(value, (list, dict)) else value for value in metadata.values()],
        })
        export_tables = {"Manifest": manifest, **tables}
        st.subheader("Download comparison evidence")
        downloads = st.columns(3)
        full_width(
            downloads[0].download_button, "Excel comparison pack", results_to_excel(export_tables),
            "positionsignal_comparisons.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            key=k("compare_download_excel"),
        )
        full_width(
            downloads[1].download_button, "CSV comparison pack", tables_to_csv_zip(export_tables),
            "positionsignal_comparisons.zip", "application/zip", key=k("compare_download_csv"),
        )
        full_width(
            downloads[2].download_button, "JSON comparison pack", results_to_json(tables, metadata),
            "positionsignal_comparisons.json", "application/json", key=k("compare_download_json"),
        )


def evidence_tables(result: MapResult, prepared: ProfileData) -> dict[str, pd.DataFrame]:
    centers = pd.DataFrame(
        {
            "attribute": result.attribute_centers.index.astype(str),
            "center": result.attribute_centers.to_numpy(dtype=float),
            "scale_divisor": result.attribute_scales.to_numpy(dtype=float),
        }
    )
    tables: dict[str, pd.DataFrame] = {
        "Brand profiles": prepared.profiles.reset_index(),
        "Cell bases": prepared.counts.reset_index(),
        "Brand coordinates": result.brand_coordinates,
        "Attribute directions": result.attribute_coordinates,
        "Explained variance": result.explained_variance,
        "Pairwise distances": result.pairwise_distances,
        "Preprocessing": centers,
    }
    bootstrap: BootstrapResult | None = st.session_state.get(k("bootstrap_result"))
    if bootstrap is not None:
        tables["Bootstrap ellipses"] = bootstrap.ellipses
        tables["Bootstrap points"] = bootstrap.points
    return tables


def analysis_metadata(result: MapResult, prepared: ProfileData, focus_brand: str) -> dict[str, object]:
    bootstrap: BootstrapResult | None = st.session_state.get(k("bootstrap_result"))
    return {
        "product": "Position Signal", "version": __version__, "source_file": st.session_state.get(k("source_name")),
        "source_table": st.session_state.get(k("active_table")), "source_sha256": st.session_state.get(k("source_fingerprint")),
        "source_grain": "respondent-brand rows" if prepared.has_respondents else "aggregate or unkeyed rating rows",
        "brand_column": prepared.brand_column, "respondent_column": prepared.respondent_column,
        "weight_column": prepared.weight_column, "brands": prepared.brands, "attributes": list(prepared.attributes),
        "focus_brand": focus_brand, "method": "PCA on aggregated brand-by-attribute means",
        "standardized_attributes": result.scale_attributes, "standard_deviation_ddof": 1,
        "pca_solver": "full deterministic SVD", "axis_sign_rule": "largest absolute coefficient made positive; lexical tie-break",
        "biplot": "row-metric Gabriel rank-two biplot with reciprocal common scalar",
        "biplot_scale": result.biplot_scale, "variance_retained_2d": result.variance_2d,
        "distance_stress_2d": result.normalized_distance_error,
        "full_map_distance_correlation": result.distance_correlation if np.isfinite(result.distance_correlation) else None,
        "eigengap_pc1_pc2": result.eigengap_pc1_pc2, "eigengap_pc2_pc3": result.eigengap_pc2_pc3,
        "bootstrap_iterations_requested": bootstrap.requested_iterations if bootstrap else 0,
        "bootstrap_iterations_successful": bootstrap.successful_iterations if bootstrap else 0,
        "bootstrap_confidence": bootstrap.confidence_level if bootstrap else None,
        "bootstrap_random_seed": bootstrap.random_state if bootstrap else None,
        "bootstrap_resampling_scheme": bootstrap.resampling_scheme if bootstrap else None,
        "bootstrap_minimum_cell_base": bootstrap.minimum_cell_base if bootstrap else None,
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
        "scikit_learn": sklearn.__version__, "caution": CAUTION.replace("**", ""),
    }


def render_interpret_export() -> None:
    sig.header(
        "Step 4",
        "Interpret and export",
        "Read the focus brand against the complete profile, then export the map with the evidence needed to audit it.",
    )
    result: MapResult | None = st.session_state.get(k("map_result"))
    prepared: ProfileData | None = st.session_state.get(k("profile_data"))
    if result is None or prepared is None:
        st.info("Build a perceptual map on page 2 first.")
        if full_width(st.button, "Go to map builder", type="primary", key=k("goto_build")):
            go_to("2 · Build the map")
            st.rerun()
        return

    settings = st.session_state.get(k("map_settings")) or {}
    default_focus = settings.get("focus_brand") if settings.get("focus_brand") in prepared.brands else prepared.brands[0]
    focus_brand = st.selectbox(
        "Focus brand", prepared.brands, index=prepared.brands.index(default_focus), key=k("interpret_focus_brand"),
    )
    nearest = nearest_competitors(result, focus_brand)
    relative = relative_attribute_positions(result, focus_brand)
    closest = nearest.iloc[0]
    strongest = relative.iloc[0]
    weakest = relative.iloc[-1]

    st.subheader(f"The position of {focus_brand}")
    metrics = st.columns(4)
    metrics[0].metric("Closest profile", str(closest["competitor"]), f"distance {closest['full_distance']:.2f}")
    metrics[1].metric("Most above market", str(strongest["attribute"]), f"{strongest['relative_position_sd']:+.2f} SD")
    metrics[2].metric("Most below market", str(weakest["attribute"]), f"{weakest['relative_position_sd']:+.2f} SD")
    if result.variance_2d >= 0.70:
        metric_read = "Clear in 2-D"
    elif result.variance_2d >= 0.50:
        metric_read = "Compressed"
    else:
        metric_read = "Highly compressed"
    metrics[3].metric("Map read", metric_read)
    # sig.note escapes HTML, so brand and attribute names from uploaded data cannot inject markup.
    sig.note(
        "info",
        f"**{focus_brand}** is most similar to **{closest['competitor']}** across the complete "
        f"{len(prepared.attributes)}-attribute profile. Its clearest relative high point is **{strongest['attribute']}**; "
        f"its clearest relative low point is **{weakest['attribute']}**. These are comparative descriptions, not preference or demand effects.",
    )
    render_map_summary(
        result, focus_brand,
        int(settings.get("vector_limit", min(10, len(prepared.attributes)))),
        bool(settings.get("show_vectors", True)),
    )

    left, right = st.columns([1.05, 1])
    with left:
        sig.chart(NS, competitor_distance_figure(result, focus_brand), config={"displaylogo": False}, key=k("competitor_distances"))
        st.caption("This ranking uses every selected attribute. It does not rely on the 2-D map being faithful.")
    with right:
        sig.chart(NS, relative_position_figure(relative, focus_brand), config={"displaylogo": False}, key=k("relative_profile"))
        st.caption("Positive means above the average selected brand on that attribute; it does not automatically mean strategically better.")

    st.subheader("Questions worth taking to strategy")
    sig.cards(
        [
            ("DEFEND OR PROVE", str(strongest["attribute"]), "Is this relative association important to customers, credible in market behavior, and protectable?"),
            ("COMPETITIVE PRESSURE", str(closest["competitor"]), "Where do buyers actually distinguish these two profiles—and where is the similarity useful?"),
            ("INVESTIGATE, DON'T ASSUME", str(weakest["attribute"]), "Is this a meaningful weakness, a deliberate trade-off, or simply irrelevant to choice?"),
        ]
    )
    st.warning("Empty-looking map space is not proven white space. A gap says no selected brand has that profile; it says nothing about customer demand, feasibility, or profitability.")

    with st.expander("Expert interpretation table"):
        full_width(st.dataframe, relative, hide_index=True)
        st.markdown(f"**Axis helper only:** {result.axis_1_label}  \n**Axis helper only:** {result.axis_2_label}")
        st.caption("Axis signs are arbitrary and canonicalized only for reproducible exports. These helpers summarize correlations; they do not turn PCs into objectively named constructs.")

    st.subheader("Download the evidence")
    tables = evidence_tables(result, prepared)
    metadata = analysis_metadata(result, prepared, focus_brand)
    manifest = pd.DataFrame({"property": list(metadata.keys()), "value": [json.dumps(value, default=str) if isinstance(value, (list, dict)) else value for value in metadata.values()]})
    tables_with_manifest = {"Manifest": manifest, **tables}
    downloads = st.columns(3)
    full_width(
        downloads[0].download_button, "Excel evidence pack", results_to_excel(tables_with_manifest),
        "positionsignal_evidence.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=k("download_excel"),
    )
    full_width(
        downloads[1].download_button, "CSV evidence pack", tables_to_csv_zip(tables_with_manifest),
        "positionsignal_evidence_csv.zip", "application/zip", key=k("download_csv_zip"),
    )
    full_width(
        downloads[2].download_button, "JSON + audit trail", results_to_json(tables, metadata),
        "positionsignal_evidence.json", "application/json", key=k("download_json"),
    )
    interactive = perceptual_map_figure(
        result, target_brand=focus_brand,
        show_attribute_vectors=bool(settings.get("show_vectors", True)),
        vector_limit=int(settings.get("vector_limit", min(10, len(prepared.attributes)))),
        bootstrap=st.session_state.get(k("bootstrap_result")),
    ).to_html(include_plotlyjs=True, full_html=True)
    full_width(
        st.download_button, "Interactive standalone map (HTML)", interactive.encode(),
        "positionsignal_interactive_map.html", "text/html", key=k("download_html"),
    )
    st.caption("Every export records the source fingerprint, data roles, attributes, scaling, PCA convention, diagnostics, software versions, and caution language.")


def render_methods_limits() -> None:
    sig.header(
        "Methods and limits",
        "What Position Signal calculates",
        "One primary method, the diagnostics that travel with it, and the limits that stay in force.",
    )
    st.markdown(
        "Position Signal uses one primary method because the data-generating question is specific: **where do brands sit in a "
        "multivariate attribute space?** PCA on aggregated brand profiles answers that question without pretending that "
        "within-brand respondent noise is a positioning dimension."
    )
    sig.note("warn", CAUTION)
    tabs = st.tabs(["Plain-language method", "Technical specification", "Uncertainty", "Limits & references"])
    with tabs[0]:
        st.markdown(
            """
            1. **Aggregate.** Each brand gets a mean on every chosen attribute. Optional survey weights use a weighted mean.
            2. **Check.** A map requires at least three brands and two complete, varying attributes. No missing brand–attribute cell is imputed.
            3. **Put attributes on a fair footing.** The default subtracts each attribute mean and divides by its sample standard deviation across brands.
            4. **Compress.** Full-SVD PCA finds the two orthogonal directions that retain the most variation between brand profiles.
            5. **Map honestly.** Brand distances are the primary object. Attribute arrows and brand points use reciprocal common scaling that preserves the rank-two biplot reconstruction.
            6. **Check what the picture lost.** Explained variance, brand/attribute representation, scree values, distance stress, eigengaps, and full-profile distances travel with the result.
            """
        )
    with tabs[1]:
        st.latex(r"X = UDV^\top,\qquad T = UD,\qquad \lambda_k = d_k^2/(B-1)")
        st.markdown(
            "Rows of `X` are brands; columns are centered or sample-standardized attributes. `T` contains raw brand "
            "scores, while `V` contains PCA coefficients. The plotted row-metric Gabriel biplot uses `G=T₂/c` and "
            "`H=cV₂`, so `GHᵀ=T₂V₂ᵀ`, the rank-two reconstruction. One scalar `c` balances the drawing; neither axis "
            "is stretched separately. Unscaled scores, coefficients, and correlation loadings are exported."
        )
        st.latex(r"\mathrm{brand\ cos^2}_b = \frac{t_{b1}^2+t_{b2}^2}{\sum_k t_{bk}^2}")
        st.latex(r"\mathrm{attribute\ cos^2}_a = \mathrm{corr}(X_a,T_1)^2+\mathrm{corr}(X_a,T_2)^2")
        st.latex(r"\mathrm{stress}_{2D}=\sqrt{\frac{\sum_{i<j}(d^{full}_{ij}-d^{2D}_{ij})^2}{\sum_{i<j}(d^{full}_{ij})^2}}")
        st.markdown(
            "Component signs have no substantive meaning. Position Signal makes the coefficient with the largest "
            "absolute magnitude positive on each component so harmless reruns produce stable exports. A small PC2–PC3 "
            "eigengap warns that the exact displayed plane may be sensitive; the 0.10 flag is a heuristic, not a test."
        )
    with tabs[2]:
        st.markdown(
            "When respondent IDs are available, Position Signal resamples **respondents**, carrying all of each selected "
            "person's brand ratings together; independent brand samples are resampled within brand. Every included cell "
            "must contain at least two respondents. It reaggregates the profiles, refits preprocessing and PCA, then uses "
            "orthogonal Procrustes rotation on the loading matrices and applies that rotation to the score configuration. Covariance "
            "ellipses summarize the aligned bootstrap cloud around its mean."
        )
        st.info(
            "These are respondent-sampling uncertainty regions conditional on the selected respondents, brands, attributes, "
            "weights, preprocessing, and competitive frame. Ellipse overlap is not a hypothesis test, and aggregate-only files cannot support them."
        )
    with tabs[3]:
        st.markdown(
            """
            - Likert-style ratings are treated as approximately interval-scaled so means and PCA are usable; that is a conventional assumption, not a theorem.
            - Results are relative to the selected competitor set and attributes. Add or remove either and the coordinate system can move.
            - The origin is an average profile, not “neutral perception.” Quadrants and axis signs have no inherent strategic meaning.
            - High 2-D variance is not market validity. Low 2-D variance does not make the underlying full profiles useless.
            - Correlated attributes are allowed but can implicitly give a concept more influence; inspect the profile matrix and correlation circle.
            - A perceptual gap is not demand. The map contains no choice, revenue, feasibility, or causal evidence.
            - Survey weights are accepted as positive respondent-constant values. Complex sample design variance is outside this release.
            - Raw text, image associations, brand–attribute mention counts, nonmetric proximities, ideal points, longitudinal modeling, and causal explanation remain outside this release.
            """
        )
        st.markdown(
            "**Primary references**  \n"
            "Gabriel, K. R. (1971), [The biplot graphic display of matrices with application to principal component analysis](https://doi.org/10.1093/biomet/58.3.453).  \n"
            "Jolliffe, I. T. & Cadima, J. (2016), [Principal component analysis: a review and recent developments](https://doi.org/10.1098/rsta.2015.0202).  \n"
            "Josse, J., Wager, S. & Husson, F. (2016), [Confidence areas for fixed-effects PCA](https://doi.org/10.1080/10618600.2014.950871).  \n"
            "Implementation convention: [scikit-learn PCA documentation](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)."
        )
        st.caption("The full data contract and equations also live in docs/data_guide.md and docs/methods.md.")


PAGES = {
    "Welcome": render_welcome,
    "1 · Data & setup": render_data_setup,
    "2 · Build the map": render_build_map,
    "3 · Compare waves & segments": render_position_comparisons,
    "4 · Interpret & export": render_interpret_export,
    "Methods & limits": render_methods_limits,
}


def _sidebar_data() -> None:
    """Upload, demo and table controls. Runs before the page radio, so a new file can open the setup page."""
    st.markdown("### 1. Bring your data")
    epoch = int(st.session_state[k("upload_epoch")])
    uploaded = st.file_uploader(
        "CSV, Excel, or JSON", type=["csv", "xlsx", "xls", "xlsm", "json"], key=k(f"upload_{epoch}"),
    )
    st.caption(upload_limit_note())
    if uploaded is not None:
        identity = (str(getattr(uploaded, "file_id", "")), uploaded.name, int(getattr(uploaded, "size", 0)))
        st.session_state[k("uploader_had_file")] = True
        if st.session_state.get(k("upload_identity")) != identity:
            try:
                with st.spinner("Reading the file… large files can take a little while."):
                    raw = uploaded.getvalue()
                    fingerprint = hashlib.sha256(uploaded.name.encode() + b"\0" + raw).hexdigest()
                    set_loaded(load_data(raw, name=uploaded.name), fingerprint)
                st.session_state[k("upload_identity")] = identity
                st.session_state[k("upload_epoch")] = epoch + 1
                st.session_state[k("uploader_had_file")] = False
                go_to("1 · Data & setup")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    elif st.session_state.get(k("uploader_had_file")):
        st.session_state[k("uploader_had_file")] = False

    if full_width(st.button, "Demo · sneaker ratings", key=k("demo_sneaker")):
        try:
            load_demo("demo_sneaker_ratings.csv")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    if full_width(st.button, "Demo · brand summary", key=k("demo_profiles")):
        try:
            load_demo("demo_brand_profiles.csv")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    st.caption(
        "Fictional data, built to show a useful but imperfect map. The sneaker demo opens preloaded; "
        "an upload replaces it."
    )

    tables = st.session_state.get(k("tables"))
    if tables:
        if len(tables) > 1:
            names = list(tables)
            active = st.selectbox(
                "Table or worksheet", names, index=names.index(st.session_state[k("active_table")]),
                key=k("active_table_select"),
            )
            if active != st.session_state[k("active_table")]:
                st.session_state[k("active_table")] = active
                clear_analysis()
        frame = current_frame()
        st.caption(f"Loaded: {st.session_state[k('source_name')]} · {len(frame):,} rows · {len(frame.columns)} columns")
        if full_width(st.button, "Clear data and results", key=k("clear_data")):
            _clear_namespace()
            st.session_state[k("demo_preloaded")] = True  # stay empty; the demo buttons bring a demo back
            st.rerun()


def _sidebar() -> str:
    """Draw the sidebar lockup, data controls, page selector and status captions; return the selected page."""
    sig.sidebar_brand(NS, SIDEBAR_TAGLINE)
    with st.sidebar:
        st.caption(f"Open perceptual mapping · v{__version__}")
        _sidebar_data()
        st.markdown("### 2. Follow the workflow")
        requested = st.session_state.pop(k("nav_request"), None)
        if requested in PAGES:
            st.session_state[k("page")] = requested
        page = st.radio("Page", list(PAGES), key=k("page"), label_visibility="collapsed")
        st.markdown("---")
        st.caption("Local mode · no telemetry · no external AI calls · uploads stay in this Python process")
    return page


def render() -> None:
    """Draw the whole Position Signal app on the current page. Never calls st.set_page_config or st.navigation."""
    sig.apply(NS)
    _ensure_state()
    page = _sidebar()
    sig.masthead(NS, MASTHEAD_PROMISES, MASTHEAD_KICKER)
    try:
        PAGES[page]()
    except Exception as exc:
        show_error(exc)
    sig.footer(NS, __version__, FOOTER_LINE)
