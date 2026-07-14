from io import BytesIO
import json
import zipfile

import numpy as np
import pandas as pd
import pytest

from positionsignal.errors import DataProblem
from positionsignal.io import (
    load_data,
    results_to_excel,
    results_to_json,
    safe_for_spreadsheet,
    tables_to_csv_zip,
)
from positionsignal.validation import prepare_brand_profiles


def _respondent_ratings() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "respondent_id": ["R1", "R2"] * 3,
            "brand": ["Alpha", "Alpha", "Beta", "Beta", "Gamma", "Gamma"],
            "quality": [1.0, 3.0, 5.0, 7.0, 9.0, 7.0],
            "value": [6.0, 4.0, 2.0, 4.0, 8.0, 6.0],
            "modern": [2.0, 4.0, 6.0, 8.0, 4.0, 2.0],
            "survey_weight": [1.0, 3.0] * 3,
        }
    )


def test_respondent_rows_aggregate_to_means_counts_and_context() -> None:
    frame = _respondent_ratings()
    prepared = prepare_brand_profiles(
        frame,
        brand_column="brand",
        attributes=["quality", "value", "modern"],
        respondent_column="respondent_id",
    )

    expected = pd.DataFrame(
        {
            "quality": [2.0, 6.0, 8.0],
            "value": [5.0, 3.0, 7.0],
            "modern": [3.0, 7.0, 3.0],
        },
        index=pd.Index(["Alpha", "Beta", "Gamma"], name="brand"),
    )
    pd.testing.assert_frame_equal(prepared.profiles, expected)
    assert prepared.counts["respondents"].to_dict() == {
        "Alpha": 2,
        "Beta": 2,
        "Gamma": 2,
    }
    assert prepared.has_respondents
    assert prepared.attributes == ("quality", "value", "modern")
    assert prepared.dropped_brand_rows == 0


def test_positive_survey_weights_are_used_for_each_available_rating() -> None:
    frame = _respondent_ratings()
    prepared = prepare_brand_profiles(
        frame,
        brand_column="brand",
        attributes=["quality", "value", "modern"],
        respondent_column="respondent_id",
        weight_column="survey_weight",
    )

    expected = pd.DataFrame(
        {
            "quality": [2.5, 6.5, 7.5],
            "value": [4.5, 3.5, 6.5],
            "modern": [3.5, 7.5, 2.5],
        },
        index=pd.Index(["Alpha", "Beta", "Gamma"], name="brand"),
    )
    pd.testing.assert_frame_equal(prepared.profiles, expected)

    invalid = frame.copy()
    invalid.loc[0, "survey_weight"] = 0
    with pytest.raises(DataProblem, match="finite positive"):
        prepare_brand_profiles(
            invalid,
            brand_column="brand",
            attributes=["quality", "value", "modern"],
            respondent_column="respondent_id",
            weight_column="survey_weight",
        )


def test_missing_cells_are_never_imputed_and_policy_is_explicit() -> None:
    frame = pd.DataFrame(
        {
            "brand": ["Alpha", "Beta", "Gamma", "Delta"],
            "quality": [1.0, 2.0, 3.0, 4.0],
            "value": [4.0, 2.0, 5.0, 1.0],
            "modern": [1.0, 2.0, 3.0, np.nan],
            "constant": [9.0, 9.0, 9.0, 9.0],
        }
    )

    with pytest.raises(DataProblem, match="no usable rating for: modern"):
        prepare_brand_profiles(
            frame,
            brand_column="brand",
            attributes=["quality", "value", "modern", "constant"],
            missing_policy="error",
        )

    prepared = prepare_brand_profiles(
        frame,
        brand_column="brand",
        attributes=["quality", "value", "modern", "constant"],
        missing_policy="drop_attributes",
    )
    assert prepared.excluded_incomplete == ("modern",)
    assert prepared.excluded_constant == ("constant",)
    assert list(prepared.profiles.columns) == ["quality", "value"]
    assert not prepared.profiles.isna().any().any()


def test_csv_loader_round_trips_and_rejects_unsupported_content() -> None:
    raw = b"brand,quality,value\nAlpha,7,4\nBeta,5,8\nGamma,6,6\n"
    loaded = load_data(raw, name="ratings.csv")
    assert loaded.source_name == "ratings.csv"
    assert loaded.tables["ratings"].to_dict(orient="list") == {
        "brand": ["Alpha", "Beta", "Gamma"],
        "quality": [7, 5, 6],
        "value": [4, 8, 6],
    }
    with pytest.raises(DataProblem, match="CSV, Excel, or JSON"):
        load_data(b"not executable", name="ratings.exe")
    with pytest.raises(DataProblem, match="empty"):
        load_data(b"", name="ratings.csv")


def test_spreadsheet_and_csv_exports_neutralize_formulas_and_control_characters() -> None:
    dangerous = pd.DataFrame(
        {
            "label": ["=2+2", " \t+cmd", "-run", "@sum", "ordinary", "A\x00B"],
            "number": [-2, 3, 4, 5, 6, 7],
        }
    )
    safe = safe_for_spreadsheet(dangerous)
    assert safe["label"].tolist() == [
        "'=2+2",
        "' \t+cmd",
        "'-run",
        "'@sum",
        "ordinary",
        "AB",
    ]
    # Numeric negatives are data, not spreadsheet formulas.
    assert safe["number"].tolist() == [-2, 3, 4, 5, 6, 7]

    archive_bytes = tables_to_csv_zip({"Brand positions": dangerous})
    with zipfile.ZipFile(BytesIO(archive_bytes)) as archive:
        exported = pd.read_csv(BytesIO(archive.read("Brand_positions.csv")), keep_default_na=False)
    assert exported.loc[0, "label"] == "'=2+2"
    assert exported.loc[5, "label"] == "AB"


def test_excel_export_sanitizes_sheet_names_and_preserves_safe_values() -> None:
    dangerous = pd.DataFrame({"label": ["=2+2", "ordinary"]})
    workbook = results_to_excel({"Map/results:*?[]": dangerous})
    assert workbook[:2] == b"PK"

    sheets = pd.read_excel(BytesIO(workbook), sheet_name=None)
    assert len(sheets) == 1
    sheet_name, exported = next(iter(sheets.items()))
    assert not any(character in sheet_name for character in "[]:*?/\\")
    assert exported["label"].tolist() == ["'=2+2", "ordinary"]


def test_json_export_keeps_metadata_and_uses_json_null_for_missing_values() -> None:
    payload = json.loads(
        results_to_json(
            {"brand_coordinates": pd.DataFrame({"brand": ["Alpha"], "pc1": [np.nan]})},
            metadata={"scale_attributes": True, "seed": 2026},
        )
    )
    assert payload["brand_coordinates"] == [{"brand": "Alpha", "pc1": None}]
    assert payload["analysis_metadata"] == {"scale_attributes": True, "seed": 2026}
