from __future__ import annotations

import os

# Keep Streamlit/Arrow serialization stable on macOS. This must be set early.
os.environ.setdefault("ARROW_DEFAULT_MEMORY_POOL", "system")

import base64
import hashlib
import inspect
import json
import platform
from pathlib import Path
import sys
import traceback

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import sklearn
import streamlit as st


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

from positionsignal import __version__
from positionsignal.errors import DataProblem, friendly_message
from positionsignal.io import LoadedData, load_data, results_to_excel, results_to_json, tables_to_csv_zip
from positionsignal.mapping import (
    BootstrapResult,
    MapResult,
    bootstrap_respondent_maps,
    fit_perceptual_map,
    nearest_competitors,
    relative_attribute_positions,
)
from positionsignal.plotting import (
    CORAL,
    INK,
    MUTED,
    TEAL,
    competitor_distance_figure,
    correlation_circle_figure,
    perceptual_map_figure,
    profile_heatmap_figure,
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


PAGES = [
    "Welcome",
    "1 · Data & setup",
    "2 · Build the map",
    "3 · Interpret & export",
    "Methods & limits",
]
CAUTION = (
    "**Treat the map as decision support, not objective market truth.** It depends on the respondents, brands, "
    "attributes, scaling, and missing-data choices. A two-dimensional view necessarily leaves information out."
)
MARK_URI = "data:image/svg+xml;base64," + base64.b64encode(
    (ROOT / "assets" / "positionsignal-mark.svg").read_bytes()
).decode("ascii")
NONE = "None — not present in this data"


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


st.set_page_config(page_title="PositionSignal | Open perceptual mapping", page_icon="⌖", layout="wide")
st.markdown(
    """
    <style>
    :root {
        --ps-ink:#17322e; --ps-deep:#102c2a; --ps-teal:#173c3a;
        --ps-coral:#d95b40; --ps-mint:#83d2b4; --ps-gold:#f2c66d;
        --ps-paper:#f8f5ed; --ps-line:rgba(23,50,46,.14);
    }
    [data-testid="stAppViewContainer"] {
        background:radial-gradient(circle at 94% 2%,rgba(131,210,180,.20),transparent 27rem),
                   linear-gradient(180deg,#fbf9f3 0%,var(--ps-paper) 100%);
    }
    [data-testid="stHeader"] { background:rgba(248,245,237,.78); }
    [data-testid="stSidebar"] { background:linear-gradient(165deg,#173c3a 0%,#102c2a 65%,#0c2422 100%); }
    [data-testid="stSidebar"] h1,[data-testid="stSidebar"] h2,[data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] label,[data-testid="stSidebar"] span { color:#f8f5ed; }
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p { color:#b9cbc5; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] {
        background:rgba(255,255,255,.06); border-color:rgba(131,210,180,.32);
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small,
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] small span { color:#b9cbc5 !important; }
    [data-testid="stSidebar"] [data-testid="stButton"] button {
        background:rgba(255,255,255,.08); color:#f8f5ed !important; border-color:rgba(255,255,255,.23);
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
        background:rgba(131,210,180,.16); border-color:rgba(131,210,180,.48);
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button * { color:#f8f5ed !important; }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button {
        background:#f8f5ed; color:#17322e !important;
    }
    [data-testid="stSidebar"] [data-testid="stFileUploaderDropzone"] button * { color:#17322e !important; }
    .block-container { max-width:1240px; padding-top:4.4rem; padding-bottom:4rem; }
    h1,h2,h3 { color:var(--ps-ink); letter-spacing:-.025em; }
    a { color:#9b3e2b; }
    [data-testid="stMetric"] {
        background:rgba(255,255,255,.75); border:1px solid var(--ps-line); border-radius:16px;
        padding:1rem 1.05rem; box-shadow:0 8px 28px rgba(23,50,46,.045);
    }
    [data-testid="stMetricValue"] { color:var(--ps-ink); font-size:clamp(1.55rem,2.3vw,2rem); }
    .stButton > button[kind="primary"] {
        background:linear-gradient(135deg,#e26748,#c94c34); color:white; border:0;
        box-shadow:0 8px 20px rgba(217,91,64,.22); font-weight:750;
    }
    .stButton > button[kind="primary"]:hover { background:linear-gradient(135deg,#c94c34,#b63f2b); color:white; }
    button:focus-visible,a:focus-visible,input:focus-visible { outline:3px solid #f2c66d !important; outline-offset:2px; }
    [data-testid="stExpander"],[data-testid="stAlert"],[data-testid="stVerticalBlockBorderWrapper"] { border-radius:14px; }
    .ps-brand { padding:.25rem 0 1.1rem; }
    .ps-lockup { display:flex; align-items:center; gap:.65rem; }
    .ps-mark { width:38px; height:38px; }
    .ps-name { color:white; font-size:1.28rem; line-height:1; font-weight:850; letter-spacing:-.04em; }
    .ps-name span { color:#f2c66d !important; }
    .ps-tag { margin:.55rem 0 0 !important; color:#b9cbc5 !important; font-size:.77rem; line-height:1.4; }
    .ps-masthead {
        display:flex; justify-content:space-between; align-items:center; gap:1rem; padding:.72rem 1rem .72rem .78rem;
        margin-bottom:1.35rem; background:rgba(255,255,255,.65); border:1px solid var(--ps-line);
        border-radius:18px; box-shadow:0 10px 36px rgba(23,50,46,.05);
    }
    .ps-masthead .ps-mark { width:48px; height:48px; }
    .ps-wordmark { color:var(--ps-ink); font-weight:850; letter-spacing:-.045em; font-size:1.55rem; line-height:1; }
    .ps-wordmark span { color:var(--ps-coral); }
    .ps-kicker { margin-top:.32rem; color:#59716c; font-size:.67rem; font-weight:800; letter-spacing:.13em; }
    .ps-promise { color:#47645e; font-size:.78rem; font-weight:700; white-space:nowrap; }
    .ps-promise span { color:var(--ps-coral); padding:0 .3rem; }
    .ps-hero {
        position:relative; overflow:hidden; padding:clamp(1.7rem,4vw,3.4rem); margin-bottom:1.3rem;
        background:linear-gradient(135deg,#173c3a 0%,#102c2a 75%); border-radius:26px;
        box-shadow:0 18px 50px rgba(23,50,46,.17);
    }
    .ps-hero:after {
        content:""; position:absolute; width:310px; height:310px; right:-100px; top:-135px;
        border-radius:50%; border:58px solid rgba(131,210,180,.12);
    }
    .ps-eyebrow { color:#83d2b4; font-size:.72rem; font-weight:850; letter-spacing:.16em; }
    .ps-hero h1 { color:white; font-size:clamp(2.25rem,5vw,4.7rem); line-height:.97; margin:.75rem 0 1rem; max-width:900px; }
    .ps-hero h1 em { color:#f2c66d; font-style:normal; }
    .ps-hero p { color:#d7e3df; font-size:1.06rem; line-height:1.6; max-width:780px; }
    .ps-pills { display:flex; flex-wrap:wrap; gap:.55rem; margin-top:1.15rem; }
    .ps-pill {
        padding:.4rem .72rem; border:1px solid rgba(255,255,255,.16); border-radius:999px;
        color:#f8f5ed; font-size:.78rem; font-weight:700; background:rgba(255,255,255,.055);
    }
    .ps-step,.ps-insight {
        height:100%; padding:1.2rem 1.2rem 1rem; background:rgba(255,255,255,.66);
        border:1px solid var(--ps-line); border-radius:18px;
    }
    .ps-step b,.ps-insight b { color:var(--ps-coral); font-size:.72rem; letter-spacing:.12em; }
    .ps-step h3,.ps-insight h3 { margin:.4rem 0 .5rem; }
    .ps-step p,.ps-insight p { color:#59716c; font-size:.9rem; line-height:1.55; }
    .ps-note {
        padding:1rem 1.1rem; margin:.75rem 0 1rem; border-left:4px solid var(--ps-mint);
        background:rgba(255,255,255,.62); border-radius:0 14px 14px 0; color:#47645e;
    }
    .ps-footer { margin-top:3.2rem; padding-top:1rem; border-top:1px solid var(--ps-line); color:#617670; font-size:.76rem; text-align:center; }
    .ps-footer span { color:var(--ps-coral); padding:0 .38rem; }
    @media (max-width:760px) { .ps-promise{display:none}.ps-hero{border-radius:20px}.block-container{padding-top:3.5rem} }
    @media (prefers-reduced-motion:reduce) { * { scroll-behavior:auto !important; transition:none !important; } }
    </style>
    """,
    unsafe_allow_html=True,
)


def show_error(exc: Exception) -> None:
    st.error(friendly_message(exc))
    if not isinstance(exc, DataProblem) and os.getenv("POSITIONSIGNAL_DEBUG") == "1":
        with st.expander("Technical details"):
            st.code("".join(traceback.format_exception(exc)))


def masthead() -> None:
    st.markdown(
        f"""
        <div class="ps-masthead"><div class="ps-lockup">
        <img class="ps-mark" src="{MARK_URI}" alt="PositionSignal map mark"/>
        <div><div class="ps-wordmark">Position<span>Signal</span></div>
        <div class="ps-kicker">OPEN PERCEPTUAL MAPPING</div></div></div>
        <div class="ps-promise">Local-first <span>•</span> Explainable <span>•</span> Open source</div></div>
        """,
        unsafe_allow_html=True,
    )


def footer() -> None:
    st.markdown(
        f"<div class='ps-footer'>PositionSignal {__version__}<span>•</span>Local-first analytics<span>•</span>AGPL-3.0-or-later</div>",
        unsafe_allow_html=True,
    )


for key, default in (
    ("tables", None), ("source_name", None), ("active_table", None), ("source_fingerprint", None),
    ("profile_data", None), ("setup", None), ("map_result", None), ("bootstrap_result", None),
    ("map_settings", None), ("upload_epoch", 0), ("_uploader_had_file", False),
    ("nav_target", PAGES[0]), ("nav_epoch", 0),
):
    st.session_state.setdefault(key, default)


def clear_analysis() -> None:
    for key in ("profile_data", "setup", "map_result", "bootstrap_result", "map_settings"):
        st.session_state[key] = None


def set_loaded(loaded: LoadedData, fingerprint: str | None = None) -> None:
    st.session_state["tables"] = loaded.tables
    st.session_state["source_name"] = loaded.source_name
    st.session_state["active_table"] = next(iter(loaded.tables))
    st.session_state["source_fingerprint"] = fingerprint
    clear_analysis()


def go_to(page_name: str) -> None:
    st.session_state["nav_target"] = page_name
    st.session_state["nav_epoch"] = int(st.session_state["nav_epoch"]) + 1


def load_demo(filename: str) -> None:
    path = ROOT / "examples" / filename
    raw = path.read_bytes()
    set_loaded(load_data(raw, name=filename), hashlib.sha256(raw).hexdigest())
    go_to("1 · Data & setup")


def current_frame() -> pd.DataFrame | None:
    tables = st.session_state.get("tables")
    if not tables:
        return None
    name = st.session_state.get("active_table") or next(iter(tables))
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
            "positionsignal_respondent_template.csv", "text/csv", key="template_respondent",
        )
        full_width(
            middle.download_button, "Brand-summary CSV", brand_template.to_csv(index=False).encode(),
            "positionsignal_brand_template.csv", "text/csv", key="template_brand",
        )
        full_width(
            right.download_button, "Excel templates", results_to_excel({"Respondent ratings": respondent_template, "Brand profiles": brand_template}),
            "positionsignal_templates.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="template_excel",
        )
        st.caption("Ratings should all point in the same semantic direction: higher means more of the named attribute. Reverse-code items before upload.")


with st.sidebar:
    st.markdown(
        f"""<div class='ps-brand'><div class='ps-lockup'>
        <img class='ps-mark' src='{MARK_URI}' alt='PositionSignal map mark'/>
        <div class='ps-name'>Position<span>Signal</span></div></div>
        <p class='ps-tag'>See where brands stand.</p></div>""",
        unsafe_allow_html=True,
    )
    st.markdown("### 1. Bring your data")
    uploaded = st.file_uploader(
        "CSV, Excel, or JSON", type=["csv", "xlsx", "xls", "xlsm", "json"],
        key=f"position_upload_{st.session_state['upload_epoch']}",
    )
    if uploaded is not None:
        identity = (str(getattr(uploaded, "file_id", "")), uploaded.name, int(getattr(uploaded, "size", 0)))
        st.session_state["_uploader_had_file"] = True
        if st.session_state.get("upload_identity") != identity:
            try:
                raw = uploaded.getvalue()
                fingerprint = hashlib.sha256(uploaded.name.encode() + b"\0" + raw).hexdigest()
                set_loaded(load_data(raw, name=uploaded.name), fingerprint)
                st.session_state["upload_identity"] = identity
                st.session_state["upload_epoch"] = int(st.session_state["upload_epoch"]) + 1
                st.session_state["_uploader_had_file"] = False
                go_to("1 · Data & setup")
                st.rerun()
            except Exception as exc:
                show_error(exc)
    elif st.session_state.get("_uploader_had_file"):
        st.session_state["_uploader_had_file"] = False

    if full_width(st.button, "Demo · sneaker ratings"):
        try:
            load_demo("demo_sneaker_ratings.csv")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    if full_width(st.button, "Demo · brand summary"):
        try:
            load_demo("demo_brand_profiles.csv")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    st.caption("Fictional data, built to show a useful but imperfect map.")

    tables = st.session_state.get("tables")
    if tables:
        if len(tables) > 1:
            names = list(tables)
            active = st.selectbox("Table or worksheet", names, index=names.index(st.session_state["active_table"]))
            if active != st.session_state["active_table"]:
                st.session_state["active_table"] = active
                clear_analysis()
        frame = current_frame()
        st.caption(f"Loaded: {st.session_state['source_name']} · {len(frame):,} rows · {len(frame.columns)} columns")
        if full_width(st.button, "Clear data and results"):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    st.markdown("### 2. Follow the workflow")
    target = st.session_state.get("nav_target", PAGES[0])
    page = st.radio(
        "Page", PAGES, index=PAGES.index(target) if target in PAGES else 0,
        key=f"nav_{st.session_state['nav_epoch']}", label_visibility="collapsed",
    )
    st.session_state["nav_target"] = page


def render_welcome() -> None:
    masthead()
    st.markdown(
        """
        <div class="ps-hero">
          <div class="ps-eyebrow">POSITIONING, WITHOUT THE BLACK BOX</div>
          <h1>See the market.<br/><em>Find your position.</em></h1>
          <p>Turn brand-attribute ratings into a perceptual map that shows where your brand sits,
          which competitors are genuinely closest, and which attributes create the separation.</p>
          <div class="ps-pills"><span class="ps-pill">Excel & CSV</span><span class="ps-pill">No account</span>
          <span class="ps-pill">Transparent PCA</span><span class="ps-pill">Exportable evidence</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.warning(CAUTION)
    columns = st.columns(3)
    steps = [
        ("STEP 01", "Define the market", "Bring the brand set and attributes that belong to the decision you are making."),
        ("STEP 02", "Build the map", "PositionSignal aggregates ratings, standardizes transparently, and fits one auditable PCA biplot."),
        ("STEP 03", "Read the evidence", "See the nearest rivals in the full profile—not only the picture—and export every diagnostic."),
    ]
    for column, (number, title, copy) in zip(columns, steps):
        column.markdown(f"<div class='ps-step'><b>{number}</b><h3>{title}</h3><p>{copy}</p></div>", unsafe_allow_html=True)
    st.write("")
    metrics = st.columns(4)
    metrics[0].metric("Input", "Ratings")
    metrics[1].metric("Primary method", "PCA biplot")
    metrics[2].metric("Privacy", "Local-first")
    metrics[3].metric("Output", "Evidence pack")
    with st.expander("Where this tool fits"):
        st.markdown(
            "PositionSignal is for **perceptual mapping from brand-by-attribute ratings**. It is not a brand tracker, "
            "a demand forecast, a segmentation model, or proof of causal positioning. Use the map to frame strategic "
            "questions, then test those questions with customers and market outcomes."
        )
    if full_width(st.button, "Start with a fictional market", type="primary"):
        try:
            load_demo("demo_sneaker_ratings.csv")
            st.rerun()
        except Exception as exc:
            show_error(exc)
    template_panel()
    footer()


def render_data_setup() -> None:
    masthead()
    st.header("Data & setup")
    st.markdown("Tell PositionSignal which column names each brand and which numeric columns describe perception.")
    frame = current_frame()
    if frame is None:
        st.info("Upload a file in the sidebar or open one of the fictional demos.")
        template_panel()
        footer()
        return

    metrics = st.columns(4)
    metrics[0].metric("Rows", f"{len(frame):,}")
    metrics[1].metric("Columns", f"{len(frame.columns):,}")
    metrics[2].metric("Missing cells", f"{int(frame.isna().sum().sum()):,}")
    metrics[3].metric("Possible PII fields", f"{len(likely_pii_columns(frame))}")
    with st.expander("Preview and data-quality audit", expanded=False):
        full_width(st.dataframe, frame.head(30), hide_index=True)
        full_width(st.dataframe, data_quality_report(frame), hide_index=True)
    pii = likely_pii_columns(frame)
    if pii:
        st.warning("Direct identifiers are unnecessary for positioning. Remove or ignore: " + ", ".join(pii) + ".")

    columns = [str(column) for column in frame.columns]
    inferred_brand = infer_brand_column(frame)
    brand_column = st.selectbox(
        "Which column names the brand or competitor?", columns,
        index=columns.index(inferred_brand) if inferred_brand in columns else 0,
    )
    respondent_choices = [NONE] + [column for column in columns if column != brand_column]
    inferred_respondent = infer_respondent_column(frame, brand_column)
    respondent_column = st.selectbox(
        "Respondent ID (optional, enables honest uncertainty regions)", respondent_choices,
        index=respondent_choices.index(inferred_respondent) if inferred_respondent in respondent_choices else 0,
    )
    respondent_column = None if respondent_column == NONE else respondent_column
    weight_choices = [NONE] + [column for column in columns if column not in {brand_column, respondent_column}]
    inferred_weight = infer_weight_column(frame)
    weight_column = st.selectbox(
        "Survey weight (optional)", weight_choices,
        index=weight_choices.index(inferred_weight) if inferred_weight in weight_choices else 0,
    )
    weight_column = None if weight_column == NONE else weight_column
    candidates = numeric_candidates(frame, [column for column in (brand_column, respondent_column, weight_column) if column])
    prior_setup = st.session_state.get("setup") or {}
    prior_attributes = [column for column in prior_setup.get("attributes", []) if column in candidates]
    attributes = st.multiselect(
        "Which attributes should define the map?", candidates,
        default=prior_attributes or candidates[: min(12, len(candidates))],
        help="Choose ratings where higher means more of the named attribute. Two are required; 4–12 is usually readable.",
    )
    missing_label = st.radio(
        "If a whole brand–attribute cell has no usable ratings",
        ["Remove that attribute from every brand (recommended)", "Stop and ask me to fix the data"],
        horizontal=True,
    )
    missing_policy = "drop_attributes" if missing_label.startswith("Remove") else "error"

    if full_width(st.button, "Save this data setup", type="primary"):
        try:
            prepared = prepare_brand_profiles(
                frame, brand_column=brand_column, attributes=attributes,
                respondent_column=respondent_column, weight_column=weight_column,
                missing_policy=missing_policy,
            )
            st.session_state["profile_data"] = prepared
            st.session_state["setup"] = {
                "brand_column": brand_column, "respondent_column": respondent_column,
                "weight_column": weight_column, "attributes": list(prepared.attributes),
                "missing_policy": missing_policy,
            }
            st.session_state["map_result"] = None
            st.session_state["bootstrap_result"] = None
            st.session_state["map_settings"] = None
            go_to("2 · Build the map")
            st.rerun()
        except Exception as exc:
            show_error(exc)

    prepared: ProfileData | None = st.session_state.get("profile_data")
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
    footer()


def fidelity_text(result: MapResult) -> tuple[str, str]:
    retained = result.variance_2d
    if retained >= 0.70:
        return "Clear two-dimensional summary", "The picture retains a large share of variation in this particular brand-profile matrix."
    if retained >= 0.50:
        return "Useful but compressed", "Read the map with the brand-level representation scores; some structure sits beyond the page."
    return "Strongly compressed view", "The first two axes leave most profile variation outside the picture. Use full-profile distances and diagnostics."


def render_map_summary(result: MapResult, focus_brand: str, vector_limit: int, show_vectors: bool) -> None:
    bootstrap: BootstrapResult | None = st.session_state.get("bootstrap_result")
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
    full_width(
        st.plotly_chart, figure,
        config={"displaylogo": False, "toImageButtonOptions": {"format": "png", "filename": "positionsignal_map", "scale": 2}},
        key=f"main_map_{focus_brand}_{vector_limit}_{show_vectors}",
    )
    st.caption(
        "Nearby dots are similar in the displayed 2-D projection; check full-profile distances before calling brands close. "
        "Arrows point toward increasing reconstructed values; "
        "their reciprocal common scaling with the brand points preserves the rank-two biplot geometry. The origin is "
        "the average selected brand. Quadrants have no fixed strategic meaning."
    )


def render_build_map() -> None:
    masthead()
    st.header("Build the positioning map")
    prepared: ProfileData | None = st.session_state.get("profile_data")
    if prepared is None:
        st.info("Save the brand and attribute setup on page 1 first.")
        if full_width(st.button, "Go to data setup", type="primary"):
            go_to("1 · Data & setup")
            st.rerun()
        footer()
        return

    st.markdown(
        "PositionSignal maps **brand means**, not individual rating rows. This keeps within-brand response noise from "
        "defining the axes while preserving respondent records for optional uncertainty analysis."
    )
    controls = st.columns([1.2, 1])
    focus_brand = controls[0].selectbox("Which brand should be highlighted?", prepared.brands, key="build_focus_brand")
    scaling_label = controls[1].radio(
        "How should attributes influence the map?",
        ["Equal influence (standardize; recommended)", "Keep observed dispersion (center only)"],
        help="Standardization divides each attribute by its sample standard deviation across brands. Center-only PCA lets attributes with larger observed spread drive more of the map.",
    )
    scale_attributes = scaling_label.startswith("Equal")
    if len(prepared.attributes) < 3:
        st.warning("With only two attributes, the map is simply a rotation of the input plane. Add more relevant attributes if the strategy question is broader.")
    if len(prepared.attributes) > len(prepared.brands) - 1:
        st.caption(
            f"Technical note: {len(prepared.attributes)} attributes are allowed, but with {len(prepared.brands)} brands the PCA rank cannot exceed {len(prepared.brands) - 1}."
        )

    with st.expander("Advanced map controls"):
        show_vectors = st.toggle("Show attribute arrows on the main map", value=True)
        vector_limit = st.slider("Maximum arrows to label", 2, min(20, len(prepared.attributes)), min(10, len(prepared.attributes)))
        use_bootstrap = False
        iterations = 500
        confidence = 0.90
        seed = 2026
        if prepared.has_respondents:
            use_bootstrap = st.toggle(
                "Estimate respondent-sampling uncertainty",
                value=False,
                help="Resamples respondent IDs, recomputes brand means and PCA, then aligns the maps by orthogonal Procrustes rotation.",
            )
            if use_bootstrap:
                iterations = st.slider("Bootstrap iterations", 200, 2000, 500, step=100)
                confidence = st.select_slider("Uncertainty ellipse level", options=[0.80, 0.90, 0.95], value=0.90, format_func=lambda value: f"{value:.0%}")
                seed = int(st.number_input("Random seed", min_value=0, max_value=2_147_483_647, value=2026, step=1))
        else:
            st.caption("Uncertainty ellipses are unavailable for aggregate-only files; there are no respondents to resample.")

    if full_width(st.button, "Build perceptual map", type="primary"):
        try:
            with st.spinner("Fitting the brand map…"):
                result = fit_perceptual_map(prepared.profiles, scale_attributes=scale_attributes)
            bootstrap_result = None
            if use_bootstrap:
                with st.spinner(f"Refitting and aligning {iterations:,} respondent bootstrap maps…"):
                    bootstrap_result = bootstrap_respondent_maps(
                        prepared, result, iterations=iterations, confidence=confidence, random_state=seed,
                    )
            st.session_state["map_result"] = result
            st.session_state["bootstrap_result"] = bootstrap_result
            st.session_state["map_settings"] = {
                "focus_brand": focus_brand, "scale_attributes": scale_attributes,
                "show_vectors": show_vectors, "vector_limit": vector_limit,
                "bootstrap": use_bootstrap, "bootstrap_iterations": iterations if use_bootstrap else 0,
                "confidence": confidence if use_bootstrap else None, "random_seed": seed if use_bootstrap else None,
            }
        except Exception as exc:
            show_error(exc)

    result: MapResult | None = st.session_state.get("map_result")
    if result is not None:
        render_map_summary(result, focus_brand, vector_limit, show_vectors)
        tabs = st.tabs(["Coordinates", "Attribute directions", "Expert diagnostics", "Profile matrix"])
        with tabs[0]:
            st.markdown("**Brand scores** are exported in their unscaled PCA units. `map_quality` is the brand cos²: how much of that brand's displacement from the average is visible in 2-D.")
            full_width(st.dataframe, result.brand_coordinates, hide_index=True)
        with tabs[1]:
            full_width(st.plotly_chart, correlation_circle_figure(result), config={"displaylogo": False}, key="correlation_circle")
            st.caption(
                "This separate circle uses actual attribute–component correlations. Short or faded arrows are poorly represented in two dimensions. "
                "Angles are interpretable only as associations within this displayed subspace, not as causal relationships."
            )
            full_width(st.dataframe, result.attribute_coordinates, hide_index=True)
        with tabs[2]:
            full_width(st.plotly_chart, scree_figure(result), config={"displaylogo": False}, key="scree_build")
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
            full_width(st.plotly_chart, profile_heatmap_figure(result), config={"displaylogo": False}, key="profile_heatmap_build")
            st.caption("Values are centered across brands and, under the default, divided by each attribute's sample standard deviation.")
        bootstrap_result: BootstrapResult | None = st.session_state.get("bootstrap_result")
        if bootstrap_result is not None:
            st.caption(
                f"Bootstrap: {bootstrap_result.successful_iterations} of {bootstrap_result.requested_iterations} maps aligned successfully; "
                f"ellipses show {bootstrap_result.confidence_level:.0%} covariance regions using {bootstrap_result.resampling_scheme}. "
                "Overlap is not a hypothesis test."
            )
        if full_width(st.button, "Interpret this position", type="primary"):
            st.session_state["map_settings"]["focus_brand"] = focus_brand
            go_to("3 · Interpret & export")
            st.rerun()
    footer()


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
    bootstrap: BootstrapResult | None = st.session_state.get("bootstrap_result")
    if bootstrap is not None:
        tables["Bootstrap ellipses"] = bootstrap.ellipses
        tables["Bootstrap points"] = bootstrap.points
    return tables


def analysis_metadata(result: MapResult, prepared: ProfileData, focus_brand: str) -> dict[str, object]:
    bootstrap: BootstrapResult | None = st.session_state.get("bootstrap_result")
    return {
        "product": "PositionSignal", "version": __version__, "source_file": st.session_state.get("source_name"),
        "source_table": st.session_state.get("active_table"), "source_sha256": st.session_state.get("source_fingerprint"),
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
    masthead()
    st.header("Interpret & export")
    result: MapResult | None = st.session_state.get("map_result")
    prepared: ProfileData | None = st.session_state.get("profile_data")
    if result is None or prepared is None:
        st.info("Build a perceptual map on page 2 first.")
        if full_width(st.button, "Go to map builder", type="primary"):
            go_to("2 · Build the map")
            st.rerun()
        footer()
        return

    settings = st.session_state.get("map_settings") or {}
    default_focus = settings.get("focus_brand") if settings.get("focus_brand") in prepared.brands else prepared.brands[0]
    focus_brand = st.selectbox("Focus brand", prepared.brands, index=prepared.brands.index(default_focus), key="interpret_focus_brand")
    nearest = nearest_competitors(result, focus_brand)
    relative = relative_attribute_positions(result, focus_brand)
    closest = nearest.iloc[0]
    strongest = relative.iloc[0]
    weakest = relative.iloc[-1]
    label, explanation = fidelity_text(result)

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
    st.markdown(
        f"<div class='ps-note'><b>{focus_brand}</b> is most similar to <b>{closest['competitor']}</b> across the complete "
        f"{len(prepared.attributes)}-attribute profile. Its clearest relative high point is <b>{strongest['attribute']}</b>; "
        f"its clearest relative low point is <b>{weakest['attribute']}</b>. These are comparative descriptions, not preference or demand effects.</div>",
        unsafe_allow_html=True,
    )
    render_map_summary(
        result, focus_brand,
        int(settings.get("vector_limit", min(10, len(prepared.attributes)))),
        bool(settings.get("show_vectors", True)),
    )

    left, right = st.columns([1.05, 1])
    with left:
        full_width(st.plotly_chart, competitor_distance_figure(result, focus_brand), config={"displaylogo": False}, key="competitor_distances")
        st.caption("This ranking uses every selected attribute. It does not rely on the 2-D map being faithful.")
    with right:
        ordered = relative.sort_values("relative_position_sd")
        figure = go.Figure(
            go.Bar(
                x=ordered["relative_position_sd"], y=ordered["attribute"], orientation="h",
                marker_color=[CORAL if value < 0 else TEAL for value in ordered["relative_position_sd"]],
                customdata=ordered[["brand_rating", "market_mean"]],
                hovertemplate="%{y}<br>Relative position %{x:+.2f} SD<br>Brand mean %{customdata[0]:.2f}<br>Market mean %{customdata[1]:.2f}<extra></extra>",
            )
        )
        figure.update_layout(
            title=f"{focus_brand} relative to the market", height=max(350, 42 * len(ordered) + 140),
            margin={"l": 15, "r": 15, "t": 55, "b": 20}, paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(255,255,255,.54)", font={"color": INK},
        )
        figure.update_xaxes(title="SD from selected-brand mean", zeroline=True, zerolinecolor=MUTED)
        figure.update_yaxes(title="")
        full_width(st.plotly_chart, figure, config={"displaylogo": False}, key="relative_profile")
        st.caption("Positive means above the average selected brand on that attribute; it does not automatically mean strategically better.")

    st.subheader("Questions worth taking to strategy")
    cards = st.columns(3)
    cards[0].markdown(
        f"<div class='ps-insight'><b>DEFEND OR PROVE</b><h3>{strongest['attribute']}</h3><p>Is this relative association important to customers, credible in market behavior, and protectable?</p></div>",
        unsafe_allow_html=True,
    )
    cards[1].markdown(
        f"<div class='ps-insight'><b>COMPETITIVE PRESSURE</b><h3>{closest['competitor']}</h3><p>Where do buyers actually distinguish these two profiles—and where is the similarity useful?</p></div>",
        unsafe_allow_html=True,
    )
    cards[2].markdown(
        f"<div class='ps-insight'><b>INVESTIGATE, DON'T ASSUME</b><h3>{weakest['attribute']}</h3><p>Is this a meaningful weakness, a deliberate trade-off, or simply irrelevant to choice?</p></div>",
        unsafe_allow_html=True,
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
        "positionsignal_evidence.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="download_excel",
    )
    full_width(
        downloads[1].download_button, "CSV evidence pack", tables_to_csv_zip(tables_with_manifest),
        "positionsignal_evidence_csv.zip", "application/zip", key="download_csv_zip",
    )
    full_width(
        downloads[2].download_button, "JSON + audit trail", results_to_json(tables, metadata),
        "positionsignal_evidence.json", "application/json", key="download_json",
    )
    interactive = perceptual_map_figure(
        result, target_brand=focus_brand,
        show_attribute_vectors=bool(settings.get("show_vectors", True)),
        vector_limit=int(settings.get("vector_limit", min(10, len(prepared.attributes)))),
        bootstrap=st.session_state.get("bootstrap_result"),
    ).to_html(include_plotlyjs=True, full_html=True)
    full_width(
        st.download_button, "Interactive standalone map (HTML)", interactive.encode(),
        "positionsignal_interactive_map.html", "text/html", key="download_html",
    )
    st.caption("Every export records the source fingerprint, data roles, attributes, scaling, PCA convention, diagnostics, software versions, and caution language.")
    footer()


def render_methods_limits() -> None:
    masthead()
    st.header("Methods & limits")
    st.markdown(
        "PositionSignal uses one primary method because the data-generating question is specific: **where do brands sit in a "
        "multivariate attribute space?** PCA on aggregated brand profiles answers that question without pretending that "
        "within-brand respondent noise is a positioning dimension."
    )
    st.warning(CAUTION)
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
            "Component signs have no substantive meaning. PositionSignal makes the coefficient with the largest "
            "absolute magnitude positive on each component so harmless reruns produce stable exports. A small PC2–PC3 "
            "eigengap warns that the exact displayed plane may be sensitive; the 0.10 flag is a heuristic, not a test."
        )
    with tabs[2]:
        st.markdown(
            "When respondent IDs are available, PositionSignal resamples **respondents**, carrying all of each selected "
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
            - Raw text, image associations, brand–attribute mention counts, nonmetric proximities, ideal points, longitudinal tracking, and causal modeling are outside v1.
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
    footer()


ROUTES = {
    "Welcome": render_welcome,
    "1 · Data & setup": render_data_setup,
    "2 · Build the map": render_build_map,
    "3 · Interpret & export": render_interpret_export,
    "Methods & limits": render_methods_limits,
}
ROUTES[page]()
