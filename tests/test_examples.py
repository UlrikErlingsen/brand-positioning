from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from positionsignal.io import load_data
from positionsignal.validation import prepare_brand_profiles
from scripts.generate_examples import (
    ATTRIBUTES,
    BRAND_PROFILES,
    RESPONDENTS,
    aggregate_profiles,
    ratings_template,
    sneaker_ratings,
)


ROOT = Path(__file__).parents[1]
EXAMPLES = ROOT / "examples"


@pytest.fixture(scope="module")
def generated_ratings() -> pd.DataFrame:
    return sneaker_ratings()


def test_synthetic_examples_are_deterministic_and_committed_files_are_current(
    generated_ratings: pd.DataFrame,
) -> None:
    pd.testing.assert_frame_equal(generated_ratings, sneaker_ratings())

    committed_ratings = pd.read_csv(EXAMPLES / "demo_sneaker_ratings.csv")
    committed_profiles = pd.read_csv(EXAMPLES / "demo_brand_profiles.csv")
    committed_template = pd.read_csv(EXAMPLES / "ratings_template.csv")
    pd.testing.assert_frame_equal(committed_ratings, generated_ratings, check_dtype=False)
    pd.testing.assert_frame_equal(
        committed_profiles,
        aggregate_profiles(generated_ratings),
        check_dtype=False,
    )
    pd.testing.assert_frame_equal(committed_template, ratings_template(), check_dtype=False)


def test_sneaker_demo_has_six_complete_brands_and_eight_attributes(
    generated_ratings: pd.DataFrame,
) -> None:
    assert len(BRAND_PROFILES) == 6
    assert len(ATTRIBUTES) == 8
    assert len(generated_ratings) == RESPONDENTS * len(BRAND_PROFILES) == 1_080
    assert set(generated_ratings["brand"]) == set(BRAND_PROFILES)
    assert list(generated_ratings.columns) == [
        "respondent_id",
        "collection_wave",
        "segment",
        "brand",
        *ATTRIBUTES,
        "sample_weight",
    ]
    assert generated_ratings["collection_wave"].nunique() == 2
    assert generated_ratings["segment"].nunique() == 2
    assert not generated_ratings.duplicated(["respondent_id", "brand"]).any()
    assert generated_ratings["respondent_id"].nunique() == RESPONDENTS
    assert (generated_ratings.groupby("respondent_id")["brand"].nunique() == 6).all()
    assert generated_ratings[ATTRIBUTES].notna().all().all()
    assert generated_ratings[ATTRIBUTES].apply(lambda column: column.between(1, 7).all()).all()


def test_demo_weights_are_positive_finite_and_constant_within_respondent(
    generated_ratings: pd.DataFrame,
) -> None:
    weights = generated_ratings["sample_weight"]
    assert np.isfinite(weights).all()
    assert (weights > 0).all()
    respondent_weights = generated_ratings.groupby("respondent_id")["sample_weight"].agg(["nunique", "first"])
    assert (respondent_weights["nunique"] == 1).all()
    assert (respondent_weights["first"] > 0).all()


def test_app_weighted_profiles_agree_with_generated_brand_summary(
    generated_ratings: pd.DataFrame,
) -> None:
    prepared = prepare_brand_profiles(
        generated_ratings,
        brand_column="brand",
        attributes=ATTRIBUTES,
        respondent_column="respondent_id",
        weight_column="sample_weight",
        missing_policy="error",
    )
    expected = aggregate_profiles(generated_ratings).set_index("brand").sort_index()
    actual = prepared.profiles.loc[expected.index, ATTRIBUTES]

    # The committed summary is deliberately rounded to three decimals.
    np.testing.assert_allclose(actual, expected[ATTRIBUTES], atol=0.000501, rtol=0)
    assert prepared.counts["respondents"].eq(RESPONDENTS).all()
    effective_columns = [column for column in prepared.counts if column.endswith("__effective_n")]
    assert len(effective_columns) == len(ATTRIBUTES)
    assert (prepared.counts[effective_columns] > 0).all().all()


def test_csv_and_excel_templates_round_trip_through_the_app_loader() -> None:
    expected = ratings_template()
    csv_loaded = load_data(EXAMPLES / "ratings_template.csv").tables["ratings"]
    excel_loaded = load_data(EXAMPLES / "ratings_template.xlsx").tables["Ratings"]

    pd.testing.assert_frame_equal(csv_loaded, expected, check_dtype=False)
    pd.testing.assert_frame_equal(excel_loaded, expected, check_dtype=False)

    csv_profiles = prepare_brand_profiles(
        csv_loaded,
        brand_column="brand",
        attributes=ATTRIBUTES,
        respondent_column="respondent_id",
        weight_column="sample_weight",
        missing_policy="error",
    )
    excel_profiles = prepare_brand_profiles(
        excel_loaded,
        brand_column="brand",
        attributes=ATTRIBUTES,
        respondent_column="respondent_id",
        weight_column="sample_weight",
        missing_policy="error",
    )
    pd.testing.assert_frame_equal(csv_profiles.profiles, excel_profiles.profiles)
    assert csv_profiles.brands == ["Brand A", "Brand B", "Brand C"]
    assert csv_profiles.attributes == tuple(ATTRIBUTES)
