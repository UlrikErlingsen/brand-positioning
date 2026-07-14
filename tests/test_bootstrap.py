import numpy as np
import pandas as pd
import pytest

from positionsignal.errors import DataProblem
from positionsignal.mapping import bootstrap_respondent_maps, fit_perceptual_map
from positionsignal.validation import prepare_brand_profiles


def _complete_panel_with_respondent_effects() -> pd.DataFrame:
    """Every respondent rates every brand, with a common response-style shift.

    Cluster-resampling whole respondents preserves all between-brand differences:
    the sampled response-style mean is added to every brand and disappears when
    PCA centers each attribute. Row-wise resampling would not have this property.
    """
    brand_profiles = {
        "Alpha": (-2.0, -1.0, -3.0),
        "Beta": (-1.0, 2.0, 1.0),
        "Gamma": (1.0, -2.0, -1.0),
        "Delta": (2.0, 1.0, 3.0),
    }
    rows: list[dict[str, float | str]] = []
    for respondent_number in range(24):
        # Attribute-specific response styles are shared across all brands rated
        # by this respondent; they need not be the same shift on every attribute.
        shift = np.array(
            [
                (respondent_number % 5 - 2) * 0.08,
                (respondent_number % 7 - 3) * 0.05,
                (respondent_number % 4 - 1.5) * 0.06,
            ]
        )
        for brand, base in brand_profiles.items():
            rating = np.asarray(base) + shift
            rows.append(
                {
                    "respondent_id": f"R{respondent_number + 1:02d}",
                    "brand": brand,
                    "quality": float(rating[0]),
                    "value": float(rating[1]),
                    "modern": float(rating[2]),
                }
            )
    return pd.DataFrame(rows)


def test_respondent_cluster_bootstrap_is_deterministic_and_preserves_panel_geometry() -> None:
    prepared = prepare_brand_profiles(
        _complete_panel_with_respondent_effects(),
        brand_column="brand",
        attributes=["quality", "value", "modern"],
        respondent_column="respondent_id",
    )
    reference = fit_perceptual_map(prepared.profiles, scale_attributes=True)

    first = bootstrap_respondent_maps(
        prepared,
        reference,
        iterations=50,
        confidence=0.90,
        random_state=17,
    )
    second = bootstrap_respondent_maps(
        prepared,
        reference,
        iterations=50,
        confidence=0.90,
        random_state=17,
    )

    pd.testing.assert_frame_equal(first.points, second.points)
    pd.testing.assert_frame_equal(first.ellipses, second.ellipses)
    assert first.requested_iterations == 50
    assert first.successful_iterations == 50
    assert first.success_rate == pytest.approx(1.0)
    assert first.confidence_level == pytest.approx(0.90)
    assert first.random_state == 17
    assert first.resampling_scheme == "respondent clusters across brands"
    assert first.minimum_cell_base == 24
    assert len(first.points) == 50 * len(prepared.brands)
    assert len(first.ellipses) == 80 * len(prepared.brands)

    reference_xy = reference.brand_coordinates.set_index("brand")[["pc1", "pc2"]]
    merged = first.points.merge(
        reference_xy,
        left_on="brand",
        right_index=True,
        suffixes=("_bootstrap", "_reference"),
    )
    np.testing.assert_allclose(
        merged[["pc1_bootstrap", "pc2_bootstrap"]],
        merged[["pc1_reference", "pc2_reference"]],
        atol=1e-11,
    )

    ellipse_centers = first.ellipses.merge(
        reference_xy,
        left_on="brand",
        right_index=True,
        suffixes=("_ellipse", "_reference"),
    )
    radii = np.hypot(
        ellipse_centers["pc1_ellipse"] - ellipse_centers["pc1_reference"],
        ellipse_centers["pc2_ellipse"] - ellipse_centers["pc2_reference"],
    )
    assert float(radii.max()) < 1e-10


def test_aggregate_only_profiles_cannot_claim_bootstrap_uncertainty() -> None:
    aggregate = pd.DataFrame(
        {
            "brand": ["Alpha", "Beta", "Gamma", "Delta"],
            "quality": [-2.0, -1.0, 1.0, 2.0],
            "value": [-1.0, 2.0, -2.0, 1.0],
            "modern": [-3.0, 1.0, -1.0, 3.0],
        }
    )
    prepared = prepare_brand_profiles(
        aggregate,
        brand_column="brand",
        attributes=["quality", "value", "modern"],
    )
    reference = fit_perceptual_map(prepared.profiles)

    assert not prepared.has_respondents
    with pytest.raises(DataProblem, match="respondent ID"):
        bootstrap_respondent_maps(prepared, reference, iterations=50)


def test_bootstrap_rejects_brand_attribute_cells_with_only_one_respondent() -> None:
    profiles = {
        "Alpha": (-2.0, -1.0, -3.0),
        "Beta": (-1.0, 2.0, 1.0),
        "Gamma": (2.0, 0.0, 2.0),
    }
    rows: list[dict[str, float | str]] = []
    for brand, base in profiles.items():
        count = 18 if brand == "Alpha" else 1
        for respondent_number in range(count):
            rows.append(
                {
                    "respondent_id": f"{brand}-{respondent_number + 1}",
                    "brand": brand,
                    "quality": base[0],
                    "value": base[1],
                    "modern": base[2],
                }
            )

    prepared = prepare_brand_profiles(
        pd.DataFrame(rows),
        brand_column="brand",
        attributes=["quality", "value", "modern"],
        respondent_column="respondent_id",
    )
    reference = fit_perceptual_map(prepared.profiles)

    with pytest.raises(DataProblem, match="at least two independent"):
        bootstrap_respondent_maps(prepared, reference, iterations=50)
