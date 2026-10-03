"""PCA biplots, diagnostics, and respondent-cluster bootstrap uncertainty."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

import numpy as np
import pandas as pd
from scipy.linalg import orthogonal_procrustes
from scipy.spatial.distance import pdist, squareform
from scipy.stats import chi2
from sklearn.decomposition import PCA

from . import limits
from .errors import DataProblem
from .validation import ProfileData


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


_BOOTSTRAP_BATCH = 64
_BOOTSTRAP_BLOCK_ROWS = 250_000


class _BootstrapProfiles:
    """Brand-by-attribute means for many bootstrap draws at once.

    A draw resamples respondents with replacement, so each respondent's rows count as often as the respondent
    was drawn. The bootstrap brand mean is therefore a count-weighted mean of the original rows, which equals
    re-aggregating a concatenated resample but needs no copied rows: rows are grouped by brand once, and each
    batch of draws becomes one matrix product per block of rows.
    """

    def __init__(self, profile_data: ProfileData, brands: list[str], attributes: list[str], respondent_index: np.ndarray):
        source = profile_data.source_rows
        brand_position = pd.Index(brands).get_indexer(source[profile_data.brand_column].astype(str).to_numpy())
        keep = (brand_position >= 0) & (respondent_index >= 0)
        rows = np.flatnonzero(keep)
        order = np.argsort(brand_position[rows], kind="stable")
        self.rows = rows[order]
        self.respondents = respondent_index[self.rows]
        sorted_brands = brand_position[self.rows]
        self.brand_bounds = np.searchsorted(sorted_brands, np.arange(len(brands) + 1))
        self.columns = [source[attribute].to_numpy() for attribute in attributes]
        weight_column = profile_data.weight_column
        self.weights = source[weight_column].to_numpy(dtype=float)[self.rows] if weight_column else None
        self.has_missing = any(
            np.issubdtype(column.dtype, np.floating) and bool(np.isnan(column[self.rows]).any()) for column in self.columns
        )
        self.brand_count = len(brands)
        self.attribute_count = len(attributes)

    def _block(self, start: int, stop: int) -> tuple[np.ndarray, np.ndarray | None]:
        """Weighted values (missing as zero) and, when needed, weighted non-missing indicators for sorted rows."""
        positions = self.rows[start:stop]
        values = np.empty((stop - start, self.attribute_count), dtype=float)
        for index, column in enumerate(self.columns):
            values[:, index] = column[positions]
        valid = None
        if self.has_missing:
            missing = np.isnan(values)
            valid = (~missing).astype(float)
            values[missing] = 0.0
        if self.weights is not None:
            weights = self.weights[start:stop, None]
            values *= weights
            if valid is not None:
                valid *= weights
        return values, valid

    def means(self, counts: np.ndarray) -> np.ndarray:
        """Return draws × brands × attributes means (NaN where a cell has no resampled rating)."""
        draws = counts.shape[0]
        numerator = np.zeros((draws, self.brand_count, self.attribute_count))
        denominator = np.zeros((draws, self.brand_count, self.attribute_count))
        for brand in range(self.brand_count):
            lower, upper = int(self.brand_bounds[brand]), int(self.brand_bounds[brand + 1])
            for start in range(lower, upper, _BOOTSTRAP_BLOCK_ROWS):
                stop = min(start + _BOOTSTRAP_BLOCK_ROWS, upper)
                row_counts = counts[:, self.respondents[start:stop]]
                values, valid = self._block(start, stop)
                numerator[:, brand, :] += row_counts @ values
                if valid is not None:
                    denominator[:, brand, :] += row_counts @ valid
                elif self.weights is not None:
                    denominator[:, brand, :] += (row_counts @ self.weights[start:stop])[:, None]
                else:
                    denominator[:, brand, :] += row_counts.sum(axis=1)[:, None]
        with np.errstate(divide="ignore", invalid="ignore"):
            return np.where(denominator > 0, numerator / denominator, np.nan)


def bootstrap_respondent_maps(
    profile_data: ProfileData,
    reference: MapResult,
    iterations: int = 200,
    confidence: float = 0.90,
    random_state: int = 2026,
    progress: Callable[[int, int], None] | None = None,
) -> BootstrapResult:
    """Cluster-bootstrap respondents, refit PCA, and align each map by Procrustes rotation.

    Resampling respondent IDs preserves all rows belonging to a sampled person. PCA
    axes may flip or swap between samples, so each bootstrap score configuration is
    centered and orthogonally aligned to the observed brand coordinates before its
    covariance is summarized. No scale dilation is applied.

    Brand means for each draw are computed as count-weighted means of the original rows (see
    ``_BootstrapProfiles``), so memory does not grow with the resample and large files stay workable.
    ``progress(done, total)`` is called after each batch of draws.
    """
    respondent = profile_data.respondent_column
    if not respondent:
        raise DataProblem("Bootstrap uncertainty needs a respondent ID column.")
    if iterations < 50 or iterations > 2000:
        raise DataProblem("Choose between 50 and 2,000 bootstrap iterations.")
    if limits.exceeds(iterations, limits.max_bootstrap_iterations()):
        raise DataProblem(
            limits.demo_message(f"The bootstrap runs at most {limits.DEMO_MAX_BOOTSTRAP_ITERATIONS} iterations here.")
        )
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
    respondent_index = pd.Index(ids).get_indexer(source[respondent])
    brand_counts_by_respondent = source.groupby(respondent, observed=True)[profile_data.brand_column].nunique()
    independent_brand_samples = bool((brand_counts_by_respondent == 1).all())
    resampling_scheme = "within-brand respondents" if independent_brand_samples else "respondent clusters across brands"
    ids_by_brand: list[np.ndarray] = []
    if independent_brand_samples:
        respondent_brands = (
            pd.DataFrame({"respondent": respondent_index, "brand": source[profile_data.brand_column].to_numpy()})
            .loc[respondent_index >= 0]
            .drop_duplicates()
        )
        ids_by_brand = [
            group["respondent"].to_numpy()
            for _, group in respondent_brands.groupby("brand", sort=True, observed=True)
        ]
    profiles = _BootstrapProfiles(profile_data, brands, attributes, respondent_index)
    rng = np.random.default_rng(random_state)
    point_rows: list[dict[str, float | int | str]] = []

    for batch_start in range(0, iterations, _BOOTSTRAP_BATCH):
        batch = range(batch_start, min(batch_start + _BOOTSTRAP_BATCH, iterations))
        counts = np.zeros((len(batch), len(ids)))
        for row, _ in enumerate(batch):
            # Same random stream as drawing respondent IDs with rng.choice, one draw per iteration.
            if independent_brand_samples:
                sampled = np.concatenate(
                    [rng.choice(brand_ids, size=len(brand_ids), replace=True) for brand_ids in ids_by_brand]
                )
            else:
                sampled = rng.choice(len(ids), size=len(ids), replace=True)
            counts[row] = np.bincount(sampled, minlength=len(ids))
        batch_means = profiles.means(counts)
        for row, iteration in enumerate(batch):
            matrix = batch_means[row]
            # A draw is unusable when a cell has no rating or an attribute stops varying between brands.
            if not np.isfinite(matrix).all() or bool((matrix == matrix[0]).all(axis=0).any()):
                continue
            try:
                fitted = fit_perceptual_map(
                    pd.DataFrame(matrix, index=brands, columns=attributes), scale_attributes=reference.scale_attributes
                )
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
        if progress is not None:
            progress(batch.stop, iterations)

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
