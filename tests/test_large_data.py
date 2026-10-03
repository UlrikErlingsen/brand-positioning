"""Large-data behaviour: no limits locally, demo caps only with SIGNAL_PUBLIC=1, and vectorized methods that
match the straightforward per-group calculations."""

from io import BytesIO
import json

import numpy as np
import pandas as pd
import pytest
from scipy.linalg import orthogonal_procrustes

from positionsignal import limits
from positionsignal.comparison import ComparisonConfig, _profile_stats, _weighted_stats, analyze_position_comparisons
from positionsignal.errors import DataProblem, friendly_message
from positionsignal.io import load_data
from positionsignal.mapping import bootstrap_respondent_maps, fit_perceptual_map
from positionsignal.validation import clean_labels, prepare_brand_profiles

ATTRIBUTES = ["quality", "value", "modern", "trusted"]


def _ratings(respondents: int = 120, brands: int = 5, seed: int = 4, missing: float = 0.05) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    respondent = np.repeat(np.arange(respondents), brands)
    brand = np.tile(np.arange(brands), respondents)
    effects = rng.normal(0, 1.2, (brands, len(ATTRIBUTES)))
    frame = pd.DataFrame(
        {
            "respondent_id": [f"R{number}" for number in respondent],
            "brand": [f"Brand {chr(65 + number)}" for number in brand],
            "survey_weight": np.repeat(rng.uniform(0.5, 1.5, respondents).round(3), brands),
            "wave": np.where(respondent % 2 == 0, "W1", "W2"),
        }
    )
    for index, attribute in enumerate(ATTRIBUTES):
        values = np.clip(np.rint(4 + effects[brand, index] + rng.normal(0, 1.3, len(frame))), 1, 7)
        values[rng.random(len(frame)) < missing] = np.nan
        frame[attribute] = values
    return frame


@pytest.fixture
def public_demo(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGNAL_PUBLIC", "1")


@pytest.fixture
def local_run(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGNAL_PUBLIC", raising=False)


class _OversizedPayload(bytes):
    """Reports a length over the demo upload cap without allocating it."""

    def __len__(self) -> int:
        return limits.DEMO_MAX_UPLOAD_MB * 1024 * 1024 + 1


def test_local_mode_has_no_limits(local_run: None) -> None:
    assert not limits.is_public()
    for cap in (
        limits.max_upload_bytes(), limits.max_json_bytes(), limits.max_expanded_workbook_bytes(),
        limits.max_table_rows(), limits.max_total_cells(), limits.max_brands(), limits.max_attributes(),
        limits.max_bootstrap_iterations(),
    ):
        assert cap is None


def test_local_mode_accepts_files_beyond_the_demo_caps(local_run: None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(limits, "DEMO_MAX_TABLE_ROWS", 10)
    monkeypatch.setattr(limits, "DEMO_MAX_TOTAL_CELLS", 10)
    frame = _ratings(respondents=40)
    loaded = load_data(frame.to_csv(index=False).encode(), name="ratings.csv").tables["ratings"]
    assert len(loaded) == len(frame) > 10
    many_brands = pd.DataFrame(
        {"brand": [f"B{number}" for number in range(70)], "x": np.arange(70.0), "y": np.arange(70.0) ** 2}
    )
    assert len(prepare_brand_profiles(many_brands, "brand", ["x", "y"]).brands) == 70


def test_a_file_above_the_old_500000_row_cap_loads_and_aggregates(local_run: None) -> None:
    rows = 520_000
    rng = np.random.default_rng(1)
    frame = pd.DataFrame(
        {
            "brand": np.array(["Alpha", "Beta", "Gamma", "Delta"])[np.arange(rows) % 4],
            "quality": rng.integers(1, 8, rows),
            "value": rng.integers(1, 8, rows),
        }
    )
    loaded = load_data(frame.to_csv(index=False).encode(), name="big.csv").tables["ratings"]
    assert len(loaded) == rows
    assert loaded["quality"].dtype == np.int8  # whole-number ratings are stored compactly
    prepared = prepare_brand_profiles(loaded, "brand", ["quality", "value"])
    assert int(prepared.counts["rating_rows"].sum()) == rows
    expected = frame.groupby("brand")[["quality", "value"]].mean()
    pd.testing.assert_frame_equal(prepared.profiles, expected.astype(float), check_names=False)


def test_public_demo_enforces_its_caps(public_demo: None, monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(DataProblem, match="downloaded app has no such limit"):
        load_data(_OversizedPayload(b"brand,x\n"), name="ratings.csv")
    monkeypatch.setattr(limits, "DEMO_MAX_TABLE_ROWS", 10)
    with pytest.raises(DataProblem, match="limited to 10 rows"):
        load_data(_ratings(respondents=40).to_csv(index=False).encode(), name="ratings.csv")
    many_brands = pd.DataFrame({"brand": [f"B{n}" for n in range(70)], "x": np.arange(70.0), "y": np.arange(70.0) ** 2})
    with pytest.raises(DataProblem, match="at most 60 brands here"):
        prepare_brand_profiles(many_brands, "brand", ["x", "y"])
    frame = _ratings()
    prepared = prepare_brand_profiles(frame, "brand", ATTRIBUTES, "respondent_id")
    with pytest.raises(DataProblem, match="at most 500 iterations here"):
        bootstrap_respondent_maps(prepared, fit_perceptual_map(prepared.profiles), iterations=600)


def test_memory_errors_become_a_plain_message() -> None:
    assert "not enough memory" in friendly_message(MemoryError())


def test_csv_delimiter_is_detected_and_text_becomes_categories(local_run: None) -> None:
    loaded = load_data(b"brand;quality;value\nAlpha;7;4\nBeta;5;8\nGamma;6;6\n", name="ratings.csv").tables["ratings"]
    assert loaded["brand"].tolist() == ["Alpha", "Beta", "Gamma"]
    assert isinstance(loaded["brand"].dtype, pd.CategoricalDtype)
    assert loaded["quality"].tolist() == [7, 5, 6]


def test_json_record_lists_and_table_mappings_are_streamed(local_run: None, monkeypatch: pytest.MonkeyPatch) -> None:
    import positionsignal.io as position_io

    monkeypatch.setattr(position_io, "JSON_CHUNK_RECORDS", 2)
    records = [{"brand": name, "quality": score} for name, score in [("A", 1), ("B", 2), ("C", 3), ("D", 4), ("E", 5)]]
    listed = load_data(json.dumps(records).encode(), name="ratings.json").tables["ratings"]
    assert listed["brand"].tolist() == ["A", "B", "C", "D", "E"]
    assert listed["quality"].tolist() == [1, 2, 3, 4, 5]
    mapped = load_data(json.dumps({"wave1": records, "wave2": records[:3]}).encode(), name="ratings.json").tables
    assert list(mapped) == ["wave1", "wave2"]
    assert len(mapped["wave1"]) == 5 and len(mapped["wave2"]) == 3
    columns = load_data(json.dumps({"brand": {"0": "A", "1": "B"}, "quality": {"0": 1, "1": 2}}).encode(), name="x.json")
    assert columns.tables["ratings"]["quality"].tolist() == [1, 2]
    with pytest.raises(DataProblem, match="could not be read"):
        load_data(b"[{\"brand\": \"A\"},", name="broken.json")


def test_clean_labels_strip_and_sort_like_text() -> None:
    cleaned = clean_labels(pd.Series([" Beta", "Alpha ", None, "Beta"]))
    assert cleaned.tolist() == ["Beta", "Alpha", "", "Beta"]
    assert list(cleaned.cat.categories) == ["", "Alpha", "Beta"]


@pytest.mark.parametrize("weight", [None, "survey_weight"])
def test_grouped_comparison_statistics_match_the_per_group_formula(weight: str | None) -> None:
    frame = _ratings()
    frame["brand"] = clean_labels(frame["brand"])
    config = ComparisonConfig(brand_column="brand", attributes=tuple(ATTRIBUTES), focus_brand="Brand A", weight_column=weight)
    stats = _profile_stats(frame, config)
    for _, row in stats.iterrows():
        group = frame.loc[frame["brand"] == row["brand"]]
        mean, se, n, effective_n = _weighted_stats(group[row["attribute"]], group[weight] if weight else None)
        assert row["mean"] == pytest.approx(mean, rel=1e-12)
        assert row["standard_error"] == pytest.approx(se, rel=1e-9)
        assert row["rating_rows"] == n
        assert row["effective_n"] == pytest.approx(effective_n, rel=1e-12)
    result = analyze_position_comparisons(
        _ratings(), ComparisonConfig(
            brand_column="brand", attributes=tuple(ATTRIBUTES), focus_brand="Brand A", wave_column="wave",
            reference_wave="W1", comparison_wave="W2", weight_column=weight,
        )
    )
    assert len(result.wave_change) == 5 * len(ATTRIBUTES)


def _reference_bootstrap_points(prepared, reference, iterations: int, seed: int) -> pd.DataFrame:
    """The plain method: copy each sampled respondent's rows, re-aggregate, refit and align."""
    source = prepared.source_rows
    ids = source["respondent_id"].dropna().unique()
    groups = {key: group for key, group in source.groupby("respondent_id", sort=False, observed=True)}
    brands = reference.brand_coordinates["brand"].astype(str).tolist()
    reference_loadings = reference.attribute_coordinates.set_index("attribute").loc[
        list(prepared.attributes), ["pc1_coefficient", "pc2_coefficient"]
    ].to_numpy()
    rng = np.random.default_rng(seed)
    rows = []
    for iteration in range(iterations):
        sampled = rng.choice(ids, size=len(ids), replace=True)
        pieces = []
        for draw, key in enumerate(sampled):
            piece = groups[key].copy()
            piece["respondent_id"] = f"{draw}:{key}"
            pieces.append(piece)
        try:
            again = prepare_brand_profiles(
                pd.concat(pieces, ignore_index=True).astype({"brand": str}), "brand", list(prepared.attributes),
                "respondent_id", prepared.weight_column, missing_policy="error",
            )
            if list(again.attributes) != list(prepared.attributes):
                continue
            fitted = fit_perceptual_map(again.profiles.loc[brands], scale_attributes=reference.scale_attributes)
        except DataProblem:
            continue
        xy = fitted.brand_coordinates.set_index("brand").loc[brands, ["pc1", "pc2"]].to_numpy()
        xy = xy - xy.mean(axis=0, keepdims=True)
        loadings = fitted.attribute_coordinates.set_index("attribute").loc[
            list(prepared.attributes), ["pc1_coefficient", "pc2_coefficient"]
        ].to_numpy()
        rotation, _ = orthogonal_procrustes(loadings, reference_loadings)
        for brand, point in zip(brands, xy @ rotation):
            rows.append({"iteration": iteration + 1, "brand": brand, "pc1": float(point[0]), "pc2": float(point[1])})
    return pd.DataFrame(rows)


@pytest.mark.parametrize("weight", [None, "survey_weight"])
def test_vectorized_bootstrap_matches_resampling_rows(weight: str | None) -> None:
    frame = _ratings(respondents=60)
    prepared = prepare_brand_profiles(frame, "brand", ATTRIBUTES, "respondent_id", weight)
    reference = fit_perceptual_map(prepared.profiles)
    result = bootstrap_respondent_maps(prepared, reference, iterations=50, random_state=11)
    expected = _reference_bootstrap_points(prepared, reference, iterations=50, seed=11)
    pd.testing.assert_frame_equal(result.points, expected, rtol=1e-8, atol=1e-10)


def test_bootstrap_reports_progress() -> None:
    prepared = prepare_brand_profiles(_ratings(respondents=60), "brand", ATTRIBUTES, "respondent_id")
    calls: list[tuple[int, int]] = []
    bootstrap_respondent_maps(
        prepared, fit_perceptual_map(prepared.profiles), iterations=80, progress=lambda done, total: calls.append((done, total))
    )
    assert calls[-1] == (80, 80) and len(calls) >= 2


def test_compacted_workbook_round_trip(local_run: None) -> None:
    output = BytesIO()
    _ratings(respondents=10).to_excel(output, index=False)
    loaded = load_data(output.getvalue(), name="ratings.xlsx").tables
    table = next(iter(loaded.values()))
    assert isinstance(table["brand"].dtype, pd.CategoricalDtype)
    assert len(table) == 50
