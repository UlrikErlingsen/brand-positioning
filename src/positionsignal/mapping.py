"""PCA biplots, diagnostics, and respondent-cluster bootstrap uncertainty."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.linalg import orthogonal_procrustes
from scipy.spatial.distance import pdist, squareform
from scipy.stats import chi2
from sklearn.decomposition import PCA

from .errors import DataProblem
from .validation import ProfileData, prepare_brand_profiles


@dataclass(frozen=True)
class MapResult:
    """A complete, auditable two-dimensional PCA map."""

    profiles: pd.DataFrame
    analysis_matrix: pd.DataFrame
    brand_coordinates: pd.DataFrame
    attribute_coordinates: pd.DataFrame
    explained_variance: pd.DataFrame
    pairwise_distances: pd.DataFrame
    attribute_centers: pd.Series
    attribute_scales: pd.Series
    scale_attributes: bool
    biplot_scale: float
    distance_correlation: float
    normalized_distance_error: float
    eigengap_pc1_pc2: float
    eigengap_pc2_pc3: float | None
    axis_1_label: str
    axis_2_label: str

    @property
    def variance_2d(self) -> float:
        return float(self.explained_variance.head(2)["explained_ratio"].sum())


@dataclass(frozen=True)
class BootstrapResult:
    """Aligned bootstrap coordinates and covariance ellipses."""

    points: pd.DataFrame
    ellipses: pd.DataFrame
    requested_iterations: int
    successful_iterations: int
    confidence_level: float
    random_state: int
    resampling_scheme: str
    minimum_cell_base: int

    @property
    def success_rate(self) -> float:
        return self.successful_iterations / self.requested_iterations if self.requested_iterations else 0.0


def _safe_correlation(x: np.ndarray, y: np.ndarray) -> float:
    def effectively_constant(values: np.ndarray) -> bool:
        values = np.asarray(values, dtype=float)
        scale = max(1.0, float(np.max(np.abs(values))))
        tolerance = 32.0 * np.finfo(float).eps * scale
        return float(np.ptp(values)) <= tolerance

    if effectively_constant(x) or effectively_constant(y):
        return float("nan")
    value = float(np.corrcoef(x, y)[0, 1])
    return value if np.isfinite(value) else float("nan")


def _axis_label(attributes: pd.DataFrame, column: str, component: str) -> str:
    negative = attributes.loc[attributes[column] < -0.15].nsmallest(2, column)["attribute"].tolist()
    positive = attributes.loc[attributes[column] > 0.15].nlargest(2, column)["attribute"].tolist()
    left = " + ".join(negative) if negative else "lower scores"
    right = " + ".join(positive) if positive else "higher scores"
    return f"{component} · {left} ↔ {right}"


def fit_perceptual_map(profiles: pd.DataFrame, scale_attributes: bool = True) -> MapResult:
    """Fit a brand-focused PCA biplot with full-space fidelity diagnostics.

    Rows are brands and columns are attributes. Brand coordinates are ordinary
    PCA scores, so Euclidean distances on the two displayed components are the
    projected distances between standardized (or centered) profiles. Attribute
    arrows use PCA coefficients. The renderer applies reciprocal, common scaling
    to row and column markers so their inner products still reconstruct the
    rank-two approximation. Correlation loadings are exported separately.
    """
    if profiles.shape[0] < 3 or profiles.shape[1] < 2:
        raise DataProblem("The map needs at least three brands and two attributes.")
    values = profiles.to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise DataProblem("Brand profiles must be complete finite numbers before mapping.")
    centers = pd.Series(values.mean(axis=0), index=profiles.columns, name="center")
    scales_raw = values.std(axis=0, ddof=1)
    if bool((scales_raw <= np.finfo(float).eps).any()):
        constants = profiles.columns[scales_raw <= np.finfo(float).eps].astype(str).tolist()
        raise DataProblem(f"These attributes do not vary between brands: {', '.join(constants)}.")
    scales = pd.Series(scales_raw if scale_attributes else np.ones_like(scales_raw), index=profiles.columns, name="scale")
    matrix = (values - centers.to_numpy()) / scales.to_numpy()
    matrix_frame = pd.DataFrame(matrix, index=profiles.index, columns=profiles.columns)

    pca = PCA(n_components=None, svd_solver="full")
    all_scores = pca.fit_transform(matrix)
    if all_scores.shape[1] < 2:
        raise DataProblem("The selected data have fewer than two estimable dimensions.")
    # PCA signs are mathematically arbitrary. Anchor every component so the
    # attribute with its largest absolute coefficient points in the positive
    # direction; this makes exports stable across harmless row reordering.
    for component_index in range(all_scores.shape[1]):
        magnitudes = np.abs(pca.components_[component_index])
        maximum = float(magnitudes.max())
        tied = np.flatnonzero(np.isclose(magnitudes, maximum, rtol=1e-10, atol=1e-12))
        anchor = min(tied.tolist(), key=lambda index: str(profiles.columns[index]))
        if pca.components_[component_index, anchor] < 0:
            pca.components_[component_index] *= -1
            all_scores[:, component_index] *= -1
    score_2d = all_scores[:, :2]
    if float(pca.explained_variance_[1]) <= np.finfo(float).eps * max(1.0, float(pca.explained_variance_[0])):
        raise DataProblem(
            "These profiles are essentially one-dimensional. A two-axis map would invent vertical separation; "
            "review the profile table instead."
        )
    row_total = np.square(all_scores).sum(axis=1)
    row_shown = np.square(score_2d).sum(axis=1)
    row_quality = np.divide(row_shown, row_total, out=np.full_like(row_total, np.nan), where=row_total > 1e-15)
    brands = pd.DataFrame(
        {
            "brand": profiles.index.astype(str),
            "pc1": score_2d[:, 0],
            "pc2": score_2d[:, 1],
            "map_quality": row_quality,
            "contribution_pc1": np.square(score_2d[:, 0]) / max(float(np.square(score_2d[:, 0]).sum()), 1e-15),
            "contribution_pc2": np.square(score_2d[:, 1]) / max(float(np.square(score_2d[:, 1]).sum()), 1e-15),
        }
    )

    attribute_rows: list[dict[str, float | str]] = []
    for index, attribute in enumerate(profiles.columns):
        corr_1 = _safe_correlation(matrix[:, index], score_2d[:, 0])
        corr_2 = _safe_correlation(matrix[:, index], score_2d[:, 1])
        attribute_quality = corr_1**2 + corr_2**2 if np.isfinite(corr_1) and np.isfinite(corr_2) else float("nan")
        attribute_rows.append(
            {
                "attribute": str(attribute),
                "pc1_correlation": corr_1,
                "pc2_correlation": corr_2,
                "map_quality": min(1.0, attribute_quality) if np.isfinite(attribute_quality) else float("nan"),
                "pc1_coefficient": float(pca.components_[0, index]),
                "pc2_coefficient": float(pca.components_[1, index]),
                "contribution_pc1": float(pca.components_[0, index] ** 2),
                "contribution_pc2": float(pca.components_[1, index] ** 2),
            }
        )
    attributes = pd.DataFrame(attribute_rows)

    explained = pd.DataFrame(
        {
            "component": [f"PC{index + 1}" for index in range(len(pca.explained_variance_ratio_))],
            "eigenvalue": pca.explained_variance_,
            "explained_ratio": pca.explained_variance_ratio_,
            "cumulative_ratio": np.cumsum(pca.explained_variance_ratio_),
        }
    )

    full_condensed = pdist(matrix, metric="euclidean")
    map_condensed = pdist(score_2d, metric="euclidean")
    distance_correlation = _safe_correlation(full_condensed, map_condensed)
    denominator = float(np.square(full_condensed).sum())
    normalized_error = float(np.sqrt(np.square(full_condensed - map_condensed).sum() / denominator)) if denominator else 0.0
    full_square = squareform(full_condensed)
    map_square = squareform(map_condensed)
    pair_rows: list[dict[str, float | str]] = []
    brand_names = profiles.index.astype(str).tolist()
    for left in range(len(brand_names)):
        for right in range(left + 1, len(brand_names)):
            pair_rows.append(
                {
                    "brand_a": brand_names[left],
                    "brand_b": brand_names[right],
                    "full_distance": float(full_square[left, right]),
                    "map_distance": float(map_square[left, right]),
                    "distance_retained": (
                        float(map_square[left, right] / full_square[left, right])
                        if full_square[left, right] > 0 else 1.0
                    ),
                }
            )
    pairs = pd.DataFrame(pair_rows).sort_values("full_distance", ignore_index=True)

    max_brand_radius = float(np.linalg.norm(score_2d, axis=1).max())
    coefficient_2d = pca.components_[:2, :].T
    max_attribute_radius = float(np.linalg.norm(coefficient_2d, axis=1).max())
    biplot_scale = float(np.sqrt(max_brand_radius / max(max_attribute_radius, 1e-15)))
    lambda_1, lambda_2 = float(pca.explained_variance_[0]), float(pca.explained_variance_[1])
    eigengap_12 = (lambda_1 - lambda_2) / lambda_1 if lambda_1 > 0 else 0.0
    eigengap_23 = None
    if len(pca.explained_variance_) > 2 and lambda_2 > 0:
        eigengap_23 = (lambda_2 - float(pca.explained_variance_[2])) / lambda_2

    return MapResult(
        profiles=profiles.copy(),
        analysis_matrix=matrix_frame,
        brand_coordinates=brands,
        attribute_coordinates=attributes,
        explained_variance=explained,
        pairwise_distances=pairs,
        attribute_centers=centers,
        attribute_scales=scales,
        scale_attributes=scale_attributes,
        biplot_scale=biplot_scale,
        distance_correlation=distance_correlation,
        normalized_distance_error=normalized_error,
        eigengap_pc1_pc2=eigengap_12,
        eigengap_pc2_pc3=eigengap_23,
        axis_1_label=_axis_label(attributes, "pc1_correlation", "PC1"),
        axis_2_label=_axis_label(attributes, "pc2_correlation", "PC2"),
    )


def nearest_competitors(result: MapResult, target_brand: str) -> pd.DataFrame:
    """Rank competitors using the full attribute space, not only the picture."""
    if target_brand not in result.profiles.index.astype(str):
        raise DataProblem("Choose a focus brand that exists in the fitted map.")
    pairs = result.pairwise_distances
    relevant = pairs[(pairs["brand_a"] == target_brand) | (pairs["brand_b"] == target_brand)].copy()
    relevant["competitor"] = np.where(relevant["brand_a"] == target_brand, relevant["brand_b"], relevant["brand_a"])
    return relevant[["competitor", "full_distance", "map_distance", "distance_retained"]].sort_values(
        "full_distance", ignore_index=True
    )


def relative_attribute_positions(result: MapResult, target_brand: str) -> pd.DataFrame:
    """Describe a focus brand relative to the market mean in standard-deviation units."""
    profiles = result.profiles.copy()
    profiles.index = profiles.index.astype(str)
    if target_brand not in profiles.index:
        raise DataProblem("Choose a focus brand that exists in the fitted map.")
    spread = profiles.std(axis=0, ddof=1).replace(0, np.nan)
    relative = (profiles.loc[target_brand] - profiles.mean(axis=0)) / spread
    table = pd.DataFrame(
        {
            "attribute": profiles.columns.astype(str),
            "brand_rating": profiles.loc[target_brand].to_numpy(dtype=float),
            "market_mean": profiles.mean(axis=0).to_numpy(dtype=float),
            "relative_position_sd": relative.to_numpy(dtype=float),
        }
    )
    return table.sort_values("relative_position_sd", ascending=False, ignore_index=True)


def _ellipse_points(center: np.ndarray, covariance: np.ndarray, confidence: float, points: int = 80) -> np.ndarray:
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    eigenvalues = np.clip(eigenvalues, 0.0, None)
    radius = float(np.sqrt(chi2.ppf(confidence, df=2)))
    angles = np.linspace(0, 2 * np.pi, points)
    circle = np.vstack([np.cos(angles), np.sin(angles)])
    transform = eigenvectors @ np.diag(np.sqrt(eigenvalues)) * radius
    return (center[:, None] + transform @ circle).T


def bootstrap_respondent_maps(
    profile_data: ProfileData,
    reference: MapResult,
    iterations: int = 200,
    confidence: float = 0.90,
    random_state: int = 2026,
) -> BootstrapResult:
    """Cluster-bootstrap respondents, refit PCA, and align each map by Procrustes rotation.

    Resampling respondent IDs preserves all rows belonging to a sampled person. PCA
    axes may flip or swap between samples, so each bootstrap score configuration is
    centered and orthogonally aligned to the observed brand coordinates before its
    covariance is summarized. No scale dilation is applied.
    """
    respondent = profile_data.respondent_column
    if not respondent:
        raise DataProblem("Bootstrap uncertainty needs a respondent ID column.")
    if iterations < 50 or iterations > 2000:
        raise DataProblem("Choose between 50 and 2,000 bootstrap iterations.")
    if not (0.50 <= confidence < 1.0):
        raise DataProblem("The uncertainty level must be at least 50% and below 100%.")
    source = profile_data.source_rows
    ids = source[respondent].dropna().unique()
    if len(ids) < 20:
        raise DataProblem("At least 20 distinct respondents are required for bootstrap uncertainty.")
    cell_bases = profile_data.counts.loc[:, list(profile_data.attributes)]
    minimum_cell_base = int(cell_bases.min().min())
    if minimum_cell_base < 2:
        raise DataProblem(
            "Bootstrap uncertainty needs at least two independent respondents in every included brand–attribute cell."
        )

    brands = reference.brand_coordinates["brand"].astype(str).tolist()
    attributes = list(profile_data.attributes)
    reference_loadings = reference.attribute_coordinates.set_index("attribute").loc[
        attributes, ["pc1_coefficient", "pc2_coefficient"]
    ].to_numpy()
    groups = {key: group for key, group in source.groupby(respondent, sort=False, observed=True)}
    brand_counts_by_respondent = source.groupby(respondent, observed=True)[profile_data.brand_column].nunique()
    independent_brand_samples = bool((brand_counts_by_respondent == 1).all())
    resampling_scheme = "within-brand respondents" if independent_brand_samples else "respondent clusters across brands"
    ids_by_brand: dict[str, np.ndarray] = {}
    if independent_brand_samples:
        respondent_brands = source[[respondent, profile_data.brand_column]].drop_duplicates()
        ids_by_brand = {
            str(brand): group[respondent].to_numpy()
            for brand, group in respondent_brands.groupby(profile_data.brand_column, sort=True, observed=True)
        }
    rng = np.random.default_rng(random_state)
    point_rows: list[dict[str, float | int | str]] = []

    for iteration in range(iterations):
        if independent_brand_samples:
            sampled = np.concatenate(
                [rng.choice(brand_ids, size=len(brand_ids), replace=True) for brand_ids in ids_by_brand.values()]
            )
        else:
            sampled = rng.choice(ids, size=len(ids), replace=True)
        pieces: list[pd.DataFrame] = []
        for draw, key in enumerate(sampled):
            piece = groups[key].copy()
            piece["__bootstrap_respondent"] = f"{draw}:{key}"
            pieces.append(piece)
        boot_frame = pd.concat(pieces, ignore_index=True)
        try:
            prepared = prepare_brand_profiles(
                boot_frame,
                brand_column=profile_data.brand_column,
                attributes=list(profile_data.attributes),
                respondent_column="__bootstrap_respondent",
                weight_column=profile_data.weight_column,
                missing_policy="error",
            )
            if set(prepared.brands) != set(brands) or list(prepared.attributes) != list(profile_data.attributes):
                continue
            fitted = fit_perceptual_map(prepared.profiles.loc[brands], scale_attributes=reference.scale_attributes)
            boot_xy = fitted.brand_coordinates.set_index("brand").loc[brands, ["pc1", "pc2"]].to_numpy()
            boot_xy = boot_xy - boot_xy.mean(axis=0, keepdims=True)
            boot_loadings = fitted.attribute_coordinates.set_index("attribute").loc[
                attributes, ["pc1_coefficient", "pc2_coefficient"]
            ].to_numpy()
            rotation, _ = orthogonal_procrustes(boot_loadings, reference_loadings)
            aligned = boot_xy @ rotation
        except (DataProblem, ValueError, np.linalg.LinAlgError):
            continue
        for brand, coordinates in zip(brands, aligned):
            point_rows.append(
                {"iteration": iteration + 1, "brand": brand, "pc1": float(coordinates[0]), "pc2": float(coordinates[1])}
            )

    points = pd.DataFrame(point_rows)
    successful = int(points["iteration"].nunique()) if not points.empty else 0
    minimum_success = max(30, int(np.ceil(iterations * 0.60)))
    if successful < minimum_success:
        raise DataProblem(
            f"Only {successful} of {iterations} bootstrap maps were usable. "
            "The respondent design may be too sparse for stable uncertainty regions."
        )

    ellipse_rows: list[dict[str, float | str]] = []
    for brand in brands:
        cloud = points.loc[points["brand"] == brand, ["pc1", "pc2"]].to_numpy(dtype=float)
        covariance = np.cov(cloud, rowvar=False, ddof=1)
        center = cloud.mean(axis=0)
        ellipse = _ellipse_points(center, covariance, confidence)
        for sequence, coordinates in enumerate(ellipse):
            ellipse_rows.append(
                {"brand": brand, "sequence": sequence, "pc1": float(coordinates[0]), "pc2": float(coordinates[1])}
            )
    return BootstrapResult(
        points=points,
        ellipses=pd.DataFrame(ellipse_rows),
        requested_iterations=iterations,
        successful_iterations=successful,
        confidence_level=confidence,
        random_state=random_state,
        resampling_scheme=resampling_scheme,
        minimum_cell_base=minimum_cell_base,
    )
