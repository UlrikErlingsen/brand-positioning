"""Wave, segment, association-leadership, and POP/POD comparisons for brand ratings."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
import pandas as pd
from scipy import stats

from .errors import DataProblem
from .validation import clean_labels


@dataclass(frozen=True)
class ComparisonConfig:
    brand_column: str
    attributes: tuple[str, ...]
    focus_brand: str
    wave_column: str | None = None
    reference_wave: str | None = None
    comparison_wave: str | None = None
    segment_column: str | None = None
    reference_segment: str | None = None
    comparison_segment: str | None = None
    respondent_column: str | None = None
    weight_column: str | None = None
    difference_threshold: float = 0.30
    parity_tolerance: float = 0.15


@dataclass(frozen=True)
class PositionComparisonResult:
    current_profiles: pd.DataFrame
    association_ownership: pd.DataFrame
    pop_pod: pd.DataFrame
    wave_change: pd.DataFrame
    segment_change: pd.DataFrame
    warnings: tuple[str, ...]


def _weighted_stats(values: pd.Series, weights: pd.Series | None) -> tuple[float, float, int, float]:
    numeric = pd.to_numeric(values, errors="coerce")
    if weights is None:
        clean = numeric.dropna().to_numpy(float)
        n = len(clean)
        return (
            float(np.mean(clean)) if n else np.nan,
            float(stats.sem(clean)) if n > 1 else np.nan,
            n,
            float(n),
        )
    weight_values = pd.to_numeric(weights, errors="coerce")
    mask = numeric.notna() & weight_values.notna() & (weight_values > 0)
    x = numeric.loc[mask].to_numpy(float)
    w = weight_values.loc[mask].to_numpy(float)
    n = len(x)
    if n == 0 or float(w.sum()) <= 0:
        return np.nan, np.nan, 0, 0.0
    mean = float(np.average(x, weights=w))
    effective_n = float(w.sum() ** 2 / np.square(w).sum())
    variance_denominator = float(w.sum() - np.square(w).sum() / w.sum())
    variance = (
        float(np.sum(w * np.square(x - mean)) / variance_denominator)
        if variance_denominator > 0
        else np.nan
    )
    se = math.sqrt(variance / effective_n) if effective_n > 1 and np.isfinite(variance) else np.nan
    return mean, se, n, effective_n


def _profile_stats(frame: pd.DataFrame, config: ComparisonConfig) -> pd.DataFrame:
    """Per brand and attribute: the statistics of ``_weighted_stats``, computed with grouped sums.

    ``frame`` comes from ``analyze_position_comparisons``, whose brand column is categorical. Grouped sums keep
    the comparison fast on files with millions of rating rows.
    """
    brand_codes = frame[config.brand_column].cat.codes.to_numpy()
    categories = frame[config.brand_column].cat.categories
    size = len(categories)
    present = np.flatnonzero(np.bincount(brand_codes, minlength=size) > 0)
    weights = (
        pd.to_numeric(frame[config.weight_column], errors="coerce").to_numpy(dtype=float) if config.weight_column else None
    )
    columns: dict[str, np.ndarray] = {}
    pieces: list[pd.DataFrame] = []
    for attribute in config.attributes:
        values = pd.to_numeric(frame[attribute], errors="coerce").to_numpy(dtype=float)
        if weights is None:
            valid = ~np.isnan(values)
            w = valid.astype(float)
        else:
            valid = ~np.isnan(values) & ~np.isnan(weights) & (weights > 0)
            w = np.where(valid, weights, 0.0)
        x = np.where(valid, values, 0.0)
        n = np.bincount(brand_codes, weights=valid.astype(float), minlength=size)
        weight_sum = np.bincount(brand_codes, weights=w, minlength=size)
        squared_sum = np.bincount(brand_codes, weights=w * w, minlength=size)
        with np.errstate(divide="ignore", invalid="ignore"):
            mean = np.where(weight_sum > 0, np.bincount(brand_codes, weights=w * x, minlength=size) / weight_sum, np.nan)
            deviation = np.bincount(
                brand_codes, weights=w * np.square(x - np.nan_to_num(mean)[brand_codes]), minlength=size
            )
            if weights is None:
                standard_error = np.where(n > 1, np.sqrt(deviation / (n - 1)) / np.sqrt(n), np.nan)
                effective_n = n.copy()
            else:
                effective_n = np.where(weight_sum > 0, np.square(weight_sum) / squared_sum, 0.0)
                denominator = weight_sum - squared_sum / weight_sum
                variance = np.where((weight_sum > 0) & (denominator > 0), deviation / denominator, np.nan)
                standard_error = np.where(
                    (effective_n > 1) & np.isfinite(variance), np.sqrt(variance / effective_n), np.nan
                )
        columns = {
            "brand": categories[present].astype(str).to_numpy(dtype=object),
            "attribute": np.full(len(present), attribute, dtype=object),
            "mean": mean[present],
            "standard_error": standard_error[present],
            "rating_rows": n[present].astype(np.int64),
            "effective_n": effective_n[present].astype(float),
        }
        pieces.append(pd.DataFrame(columns))
    if not pieces:
        return pd.DataFrame(columns=["brand", "attribute", "mean", "standard_error", "rating_rows", "effective_n"])
    stacked = pd.concat(pieces, ignore_index=True)
    # Brand-major order, attributes in the declared order, as in the per-group calculation.
    stacked["_attribute_order"] = np.repeat(np.arange(len(pieces)), len(present))
    stacked["_brand_order"] = np.tile(np.arange(len(present)), len(pieces))
    return (
        stacked.sort_values(["_brand_order", "_attribute_order"], kind="stable")
        .drop(columns=["_attribute_order", "_brand_order"])
        .reset_index(drop=True)
    )


def _label_mask(labels: pd.Series, value: object) -> pd.Series:
    """Rows whose label equals ``value`` as text, without converting a large categorical column to strings."""
    if isinstance(labels.dtype, pd.CategoricalDtype):
        return labels.isin([category for category in labels.cat.categories if str(category) == str(value)])
    return labels.astype(str) == str(value)


def _difference_table(left: pd.DataFrame, right: pd.DataFrame, left_label: str, right_label: str) -> pd.DataFrame:
    merged = left.merge(right, on=["brand", "attribute"], suffixes=("_reference", "_comparison"))
    merged["difference"] = merged["mean_comparison"] - merged["mean_reference"]
    merged["difference_se_independent"] = np.sqrt(
        np.square(merged["standard_error_reference"]) + np.square(merged["standard_error_comparison"])
    )
    reference_variance = np.square(merged["standard_error_reference"])
    comparison_variance = np.square(merged["standard_error_comparison"])
    df_denominator = (
        np.square(reference_variance) / (merged["effective_n_reference"] - 1)
        + np.square(comparison_variance) / (merged["effective_n_comparison"] - 1)
    )
    merged["degrees_of_freedom_independent"] = np.divide(
        np.square(reference_variance + comparison_variance),
        df_denominator,
        out=np.full(len(merged), np.nan),
        where=df_denominator > 0,
    )
    critical = stats.t.ppf(0.975, merged["degrees_of_freedom_independent"])
    critical = np.where(np.isfinite(critical), critical, 1.96)
    merged["ci_low_independent"] = merged["difference"] - critical * merged["difference_se_independent"]
    merged["ci_high_independent"] = merged["difference"] + critical * merged["difference_se_independent"]
    merged.insert(0, "comparison", f"{right_label} − {left_label}")
    return merged


def analyze_position_comparisons(frame: pd.DataFrame, config: ComparisonConfig) -> PositionComparisonResult:
    """Compare declared waves/segments and report descriptive association ownership and POP/POD candidates."""
    required = [config.brand_column, *config.attributes]
    required.extend(
        column for column in (config.wave_column, config.segment_column, config.respondent_column, config.weight_column) if column
    )
    required = list(dict.fromkeys(required))
    missing = [column for column in required if column not in frame.columns]
    if missing:
        raise DataProblem("These selected comparison columns are missing: " + ", ".join(missing))
    if len(config.attributes) < 2:
        raise DataProblem("Choose at least two brand attributes for comparison.")
    if config.difference_threshold <= 0 or config.parity_tolerance < 0:
        raise DataProblem("Difference threshold must be positive and parity tolerance cannot be negative.")
    if config.parity_tolerance >= config.difference_threshold:
        raise DataProblem("Parity tolerance must be smaller than the point-of-difference threshold.")
    work = frame[required].copy()
    work[config.brand_column] = clean_labels(work[config.brand_column])
    usable = work[config.brand_column].ne("")
    if not bool(usable.all()):
        work = work.loc[usable].copy()
    work[config.brand_column] = work[config.brand_column].cat.remove_unused_categories()
    for attribute in config.attributes:
        work[attribute] = pd.to_numeric(work[attribute], errors="coerce")
    if config.weight_column:
        work[config.weight_column] = pd.to_numeric(work[config.weight_column], errors="coerce")
        if (work[config.weight_column].dropna() <= 0).any():
            raise DataProblem("Survey weights must be positive.")
    brands = sorted(work[config.brand_column].cat.categories.astype(str).tolist(), key=str.casefold)
    if len(brands) < 3:
        raise DataProblem("Comparison reporting needs at least three brands.")
    if config.focus_brand not in brands:
        raise DataProblem("The focus brand is not present in the comparison data.")
    warnings: list[str] = [
        "Association ownership and POP/POD labels are descriptive candidates conditional on the chosen brands, attributes, and thresholds."
    ]

    current = work
    wave_change = pd.DataFrame()
    if config.wave_column:
        if not config.reference_wave or not config.comparison_wave or config.reference_wave == config.comparison_wave:
            raise DataProblem("Choose two different wave values.")
        left_rows = work.loc[_label_mask(work[config.wave_column], config.reference_wave)]
        right_rows = work.loc[_label_mask(work[config.wave_column], config.comparison_wave)]
        if left_rows.empty or right_rows.empty:
            raise DataProblem("Both declared waves need usable rows.")
        wave_change = _difference_table(
            _profile_stats(left_rows, config), _profile_stats(right_rows, config),
            str(config.reference_wave), str(config.comparison_wave),
        )
        current = right_rows
        if config.respondent_column:
            right_ids = pd.unique(right_rows[config.respondent_column].dropna().to_numpy())
            if bool(left_rows[config.respondent_column].dropna().isin(right_ids).any()):
                warnings.append(
                    "Some respondents appear in both waves; displayed change intervals use an independent-samples approximation and ignore pairing."
                )

    segment_change = pd.DataFrame()
    if config.segment_column:
        if not config.reference_segment or not config.comparison_segment or config.reference_segment == config.comparison_segment:
            raise DataProblem("Choose two different segment values.")
        left_rows = work.loc[_label_mask(work[config.segment_column], config.reference_segment)]
        right_rows = work.loc[_label_mask(work[config.segment_column], config.comparison_segment)]
        if config.wave_column:
            left_rows = left_rows.loc[_label_mask(left_rows[config.wave_column], config.comparison_wave)]
            right_rows = right_rows.loc[_label_mask(right_rows[config.wave_column], config.comparison_wave)]
        if left_rows.empty or right_rows.empty:
            raise DataProblem("Both declared segments need usable rows in the comparison scope.")
        segment_change = _difference_table(
            _profile_stats(left_rows, config), _profile_stats(right_rows, config),
            str(config.reference_segment), str(config.comparison_segment),
        )
        current = right_rows

    current_stats = _profile_stats(current, config)
    profiles = current_stats.pivot(index="brand", columns="attribute", values="mean").sort_index()
    ownership_rows: list[dict[str, object]] = []
    pop_rows: list[dict[str, object]] = []
    for attribute in config.attributes:
        values = current_stats.loc[current_stats["attribute"] == attribute].dropna(subset=["mean"]).sort_values(
            "mean", ascending=False
        )
        if len(values) < 3:
            continue
        leader = values.iloc[0]
        runner = values.iloc[1]
        focus = values.loc[values["brand"] == config.focus_brand]
        if focus.empty:
            continue
        focus_mean = float(focus["mean"].iloc[0])
        competitor_mean = float(values.loc[values["brand"] != config.focus_brand, "mean"].mean())
        gap = focus_mean - competitor_mean
        ranked = values.reset_index(drop=True)
        rank = int(ranked.index[ranked["brand"] == config.focus_brand][0] + 1)
        ownership_rows.append(
            {
                "attribute": attribute, "leader_brand": str(leader["brand"]), "leader_mean": float(leader["mean"]),
                "runner_up_brand": str(runner["brand"]), "leader_gap": float(leader["mean"] - runner["mean"]),
                "focus_mean": focus_mean, "focus_rank": rank,
                "focus_lead_status": "DESCRIPTIVE LEADER" if rank == 1 else "NOT LEADING",
            }
        )
        if gap >= config.difference_threshold:
            classification = "POINT OF DIFFERENCE CANDIDATE"
        elif abs(gap) <= config.parity_tolerance:
            classification = "POINT OF PARITY CANDIDATE"
        elif gap <= -config.difference_threshold:
            classification = "COMPETITIVE DEFICIT"
        else:
            classification = "INDETERMINATE"
        pop_rows.append(
            {
                "attribute": attribute, "focus_mean": focus_mean, "competitor_mean": competitor_mean,
                "focus_minus_competitors": gap, "classification": classification,
                "difference_threshold": config.difference_threshold, "parity_tolerance": config.parity_tolerance,
            }
        )
    return PositionComparisonResult(
        current_profiles=profiles,
        association_ownership=pd.DataFrame(ownership_rows),
        pop_pod=pd.DataFrame(pop_rows),
        wave_change=wave_change,
        segment_change=segment_change,
        warnings=tuple(warnings),
    )
