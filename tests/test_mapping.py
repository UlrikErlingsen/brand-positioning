import numpy as np
import pandas as pd
import pytest

from positionsignal.mapping import fit_perceptual_map


def _rank_two_profiles() -> pd.DataFrame:
    """A hand-checkable profile matrix whose centered rank is exactly two."""
    return pd.DataFrame(
        {
            "quality": [-1.0, -1.0, 1.0, 1.0],
            "value": [-1.0, 1.0, -1.0, 1.0],
            "modern": [-2.0, 0.0, 0.0, 2.0],
        },
        index=pd.Index(["Alpha", "Beta", "Gamma", "Delta"], name="brand"),
    )


def test_standardized_pca_matches_covariance_and_preserves_rank_two_distances() -> None:
    profiles = _rank_two_profiles()
    result = fit_perceptual_map(profiles, scale_attributes=True)

    matrix = result.analysis_matrix
    np.testing.assert_allclose(matrix.mean(axis=0), 0.0, atol=1e-14)
    np.testing.assert_allclose(matrix.std(axis=0, ddof=1), 1.0, atol=1e-14)
    np.testing.assert_allclose(result.attribute_centers, profiles.mean(axis=0))
    np.testing.assert_allclose(
        result.attribute_scales,
        profiles.std(axis=0, ddof=1),
    )

    covariance = np.cov(matrix.to_numpy(), rowvar=False, ddof=1)
    expected_eigenvalues = np.linalg.eigvalsh(covariance)[::-1]
    np.testing.assert_allclose(
        result.explained_variance["eigenvalue"],
        expected_eigenvalues,
        atol=1e-12,
    )
    assert result.explained_variance["explained_ratio"].sum() == pytest.approx(1.0)
    assert result.variance_2d == pytest.approx(1.0)

    scores = result.brand_coordinates.set_index("brand").loc[
        profiles.index, ["pc1", "pc2"]
    ]
    np.testing.assert_allclose(
        scores.var(axis=0, ddof=1),
        expected_eigenvalues[:2],
        atol=1e-12,
    )

    # A rank-two matrix loses no Euclidean information in a two-component map.
    np.testing.assert_allclose(
        result.pairwise_distances["map_distance"],
        result.pairwise_distances["full_distance"],
        atol=1e-12,
    )
    assert result.distance_correlation == pytest.approx(1.0)
    assert result.normalized_distance_error == pytest.approx(0.0, abs=1e-12)

    # Exported arrow coordinates are correlations with the displayed scores.
    attributes = result.attribute_coordinates.set_index("attribute")
    for attribute in profiles.columns:
        expected_pc1 = np.corrcoef(matrix[attribute], scores["pc1"])[0, 1]
        expected_pc2 = np.corrcoef(matrix[attribute], scores["pc2"])[0, 1]
        assert attributes.loc[attribute, "pc1_correlation"] == pytest.approx(expected_pc1)
        assert attributes.loc[attribute, "pc2_correlation"] == pytest.approx(expected_pc2)


def test_standardized_map_is_affine_invariant_and_row_order_invariant() -> None:
    profiles = _rank_two_profiles()
    baseline = fit_perceptual_map(profiles, scale_attributes=True)

    transformed = profiles.copy()
    transformed["quality"] = 100.0 + 5.0 * transformed["quality"]
    transformed["value"] = -7.0 + 0.25 * transformed["value"]
    transformed["modern"] = 12.0 + 3.0 * transformed["modern"]
    transformed = transformed.loc[["Gamma", "Alpha", "Delta", "Beta"]]
    repeated = fit_perceptual_map(transformed, scale_attributes=True)

    pd.testing.assert_frame_equal(
        baseline.analysis_matrix,
        repeated.analysis_matrix.loc[profiles.index],
        check_exact=False,
        atol=1e-12,
        rtol=1e-12,
    )
    baseline_scores = baseline.brand_coordinates.set_index("brand").loc[
        profiles.index, ["pc1", "pc2"]
    ]
    repeated_scores = repeated.brand_coordinates.set_index("brand").loc[
        profiles.index, ["pc1", "pc2"]
    ]
    np.testing.assert_allclose(baseline_scores, repeated_scores, atol=1e-12)
    np.testing.assert_allclose(
        baseline.explained_variance["explained_ratio"],
        repeated.explained_variance["explained_ratio"],
        atol=1e-12,
    )

    # The sign convention anchors the strongest loading/correlation positively,
    # so a harmless row reorder cannot mirror either exported axis.
    for column in ("pc1_correlation", "pc2_correlation"):
        values = repeated.attribute_coordinates.set_index("attribute")[column]
        anchor = values.abs().idxmax()
        assert values.loc[anchor] > 0


def test_center_only_mode_uses_original_units_without_rescaling() -> None:
    profiles = _rank_two_profiles().assign(modern=lambda frame: 10 * frame["modern"])
    result = fit_perceptual_map(profiles, scale_attributes=False)

    expected = profiles - profiles.mean(axis=0)
    pd.testing.assert_frame_equal(result.analysis_matrix, expected)
    np.testing.assert_allclose(result.attribute_scales, 1.0)
    assert not result.scale_attributes


def test_equidistant_map_reports_undefined_distance_correlation() -> None:
    profiles = pd.DataFrame(
        {
            "x": [1.0, -0.5, -0.5],
            "y": [0.0, np.sqrt(3.0) / 2.0, -np.sqrt(3.0) / 2.0],
        },
        index=pd.Index(["Alpha", "Beta", "Gamma"], name="brand"),
    )

    result = fit_perceptual_map(profiles, scale_attributes=True)

    # All three pairwise distances are identical, so Pearson correlation is
    # mathematically undefined even though the rank-two map is lossless.
    assert np.isnan(result.distance_correlation)
    assert result.normalized_distance_error == pytest.approx(0.0, abs=1e-12)
