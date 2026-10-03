"""Schema inference, aggregation, and validation for brand-rating data."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

from . import limits
from .errors import DataProblem


BRAND_PATTERN = re.compile(r"brand|competitor|company|product|offer|alternative|name", re.I)
RESPONDENT_PATTERN = re.compile(r"respondent|participant|consumer|customer|person|panelist|subject|(^|_)id$", re.I)
WEIGHT_PATTERN = re.compile(r"(^|_)weight$|survey.?weight|sample.?weight|expansion", re.I)
PII_PATTERN = re.compile(r"e.?mail|phone|mobile|address|first.?name|last.?name|full.?name", re.I)


@dataclass(frozen=True)
class ProfileData:
    """Validated brand profiles plus the source context needed for diagnostics."""

    profiles: pd.DataFrame
    counts: pd.DataFrame
    source_rows: pd.DataFrame
    brand_column: str
    attributes: tuple[str, ...]
    respondent_column: str | None
    weight_column: str | None
    excluded_incomplete: tuple[str, ...]
    excluded_constant: tuple[str, ...]
    dropped_brand_rows: int

    @property
    def brands(self) -> list[str]:
        return self.profiles.index.astype(str).tolist()

    @property
    def has_respondents(self) -> bool:
        return bool(self.respondent_column and self.respondent_column in self.source_rows)


def infer_brand_column(frame: pd.DataFrame) -> str | None:
    """Suggest a categorical brand identifier."""
    candidates = [str(column) for column in frame.columns if BRAND_PATTERN.search(str(column))]
    sensible = [
        column for column in candidates
        if 3 <= int(frame[column].nunique(dropna=True)) <= min(100, max(3, len(frame)))
    ]
    return (sensible or candidates or [None])[0]


def infer_respondent_column(frame: pd.DataFrame, brand_column: str | None = None) -> str | None:
    """Suggest a respondent identifier when rows appear to contain repeated ratings."""
    for column in frame.columns:
        name = str(column)
        if name == brand_column or not RESPONDENT_PATTERN.search(name):
            continue
        unique = int(frame[column].nunique(dropna=True))
        if 2 <= unique <= len(frame):
            return name
    return None


def infer_weight_column(frame: pd.DataFrame) -> str | None:
    """Suggest a conventional survey-weight field."""
    return next((str(column) for column in frame.columns if WEIGHT_PATTERN.search(str(column))), None)


def _is_numeric_candidate(series: pd.Series) -> bool:
    if pd.api.types.is_numeric_dtype(series.dtype) and not pd.api.types.is_bool_dtype(series.dtype):
        # Large files: min/max finds "more than one distinct value" without hashing millions of rows.
        if not bool(series.notna().any()):
            return False
        return bool(series.min() != series.max())
    if isinstance(series.dtype, pd.CategoricalDtype):
        counts = series.value_counts(dropna=True)
        counts = counts[counts > 0]
        if counts.empty:
            return False
        converted = pd.to_numeric(pd.Series(counts.index, dtype=object), errors="coerce").to_numpy()
        numeric_share = float(counts.to_numpy()[~pd.isna(converted)].sum() / counts.sum())
        return numeric_share >= 0.85 and int(pd.Series(converted).nunique(dropna=True)) > 1
    nonmissing = series.dropna()
    if nonmissing.empty:
        return False
    converted = pd.to_numeric(nonmissing, errors="coerce")
    if pd.api.types.is_numeric_dtype(series) or float(converted.notna().mean()) >= 0.85:
        return int(converted.nunique(dropna=True)) > 1
    return False


def numeric_candidates(frame: pd.DataFrame, excluded: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Return columns that are numeric or at least 85% numeric-like."""
    blocked = set(excluded)
    return [str(column) for column in frame.columns if str(column) not in blocked and _is_numeric_candidate(frame[column])]


def likely_pii_columns(frame: pd.DataFrame) -> list[str]:
    """Flag obvious direct-identifier fields that are unnecessary for mapping."""
    flagged: list[str] = []
    for column in frame.columns:
        name = str(column)
        if PII_PATTERN.search(name):
            flagged.append(name)
            continue
        # Take the first 100 values before converting, so a column with millions of rows is not turned into text.
        sample = frame[column].dropna().head(100).astype(str)
        if not sample.empty and float(sample.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$").mean()) > 0.7:
            flagged.append(name)
    return flagged


def data_quality_report(frame: pd.DataFrame) -> pd.DataFrame:
    """Build a compact column-level audit."""
    pii = set(likely_pii_columns(frame))
    rows: list[dict[str, object]] = []
    for column in frame.columns:
        series = frame[column]
        unique = int(series.nunique(dropna=True))
        rows.append(
            {
                "column": str(column),
                "type": str(series.dtype),
                "missing_%": round(100 * float(series.isna().mean()), 1),
                "unique": unique,
                "constant": bool(unique <= 1),
                "privacy_note": "direct identifier" if str(column) in pii else "",
            }
        )
    return pd.DataFrame(rows)


def clean_labels(series: pd.Series) -> pd.Series:
    """Strip text labels once per distinct value and return a categorical column (missing becomes "").

    Brand and respondent columns repeat a few values millions of times in large files, so working on the
    distinct labels keeps cleaning fast. Categories are sorted, which keeps grouped output alphabetical.
    """
    if isinstance(series.dtype, pd.CategoricalDtype):
        codes = series.cat.codes.to_numpy()
        uniques = pd.Series(series.cat.categories, dtype=object)
    else:
        codes, unique_index = pd.factorize(series, use_na_sentinel=True)
        uniques = pd.Series(unique_index, dtype=object)
    labels = pd.Series([*uniques.astype(str).str.strip().tolist(), ""], dtype=object)
    label_codes, categories = pd.factorize(labels, sort=True)
    mapped = label_codes[np.where(codes >= 0, codes, len(labels) - 1)]
    return pd.Series(
        pd.Categorical.from_codes(mapped, categories=pd.Index(categories, dtype=object)),
        index=series.index,
        name=series.name,
    )


def _blank_ids(series: pd.Series) -> pd.Series:
    """Missing or whitespace-only identifiers, without converting millions of numeric IDs to text."""
    missing = series.isna()
    if pd.api.types.is_numeric_dtype(series.dtype):
        return missing
    if isinstance(series.dtype, pd.CategoricalDtype):
        blank_categories = [category for category in series.cat.categories if str(category).strip() == ""]
        return missing | series.isin(blank_categories)
    return missing | series.astype(str).str.strip().eq("")


def _weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    mask = values.notna() & weights.notna()
    if not bool(mask.any()):
        return float("nan")
    denominator = float(weights.loc[mask].sum())
    if denominator <= 0:
        return float("nan")
    return float(np.average(values.loc[mask].astype(float), weights=weights.loc[mask].astype(float)))


def prepare_brand_profiles(
    frame: pd.DataFrame,
    brand_column: str,
    attributes: list[str] | tuple[str, ...],
    respondent_column: str | None = None,
    weight_column: str | None = None,
    missing_policy: str = "drop_attributes",
) -> ProfileData:
    """Aggregate rating rows to one complete brand-by-attribute profile matrix.

    Means are calculated from every available rating for each brand/attribute cell.
    Missing cells can either stop the analysis or cause the affected attribute to be
    removed. No rating value is silently imputed.
    """
    if brand_column not in frame:
        raise DataProblem("Choose the column containing the brand or competitor name.")
    chosen = list(dict.fromkeys(str(attribute) for attribute in attributes))
    missing_columns = [column for column in chosen if column not in frame]
    if missing_columns:
        raise DataProblem(f"These selected attributes are missing: {', '.join(missing_columns)}.")
    if len(chosen) < 2:
        raise DataProblem("Choose at least two numeric brand attributes.")
    if limits.exceeds(len(chosen), limits.max_attributes()):
        raise DataProblem(limits.demo_message(f"A map uses at most {limits.DEMO_MAX_ATTRIBUTES} attributes here."))
    if respondent_column and respondent_column not in frame:
        raise DataProblem("The selected respondent ID column is missing.")
    if weight_column and weight_column not in frame:
        raise DataProblem("The selected survey-weight column is missing.")
    blocked = {brand_column, respondent_column, weight_column} - {None}
    overlap = [column for column in chosen if column in blocked]
    if overlap:
        raise DataProblem(f"A role column cannot also be an attribute: {', '.join(overlap)}.")

    keep = [brand_column, *chosen]
    if respondent_column:
        keep.append(respondent_column)
    if weight_column:
        keep.append(weight_column)
    work = frame.loc[:, list(dict.fromkeys(keep))].copy()
    work[brand_column] = clean_labels(work[brand_column])
    unusable = [category for category in work[brand_column].cat.categories if category == "" or category.lower() == "nan"]
    valid_brand = ~work[brand_column].isin(unusable)
    dropped_brand_rows = int((~valid_brand).sum())
    if dropped_brand_rows:
        work = work.loc[valid_brand].copy()
    work[brand_column] = work[brand_column].cat.remove_unused_categories()
    if work.empty:
        raise DataProblem("No rows contain a usable brand name.")
    if work[brand_column].nunique() < 3:
        raise DataProblem("A two-dimensional map needs ratings for at least three brands.")
    if limits.exceeds(int(work[brand_column].nunique()), limits.max_brands()):
        raise DataProblem(limits.demo_message(f"A map shows at most {limits.DEMO_MAX_BRANDS} brands here."))

    for attribute in chosen:
        work[attribute] = pd.to_numeric(work[attribute], errors="coerce")
    if weight_column:
        work[weight_column] = pd.to_numeric(work[weight_column], errors="coerce")
        invalid_weight = work[weight_column].isna() | ~np.isfinite(work[weight_column]) | (work[weight_column] <= 0)
        if bool(invalid_weight.any()):
            raise DataProblem("Survey weights must be finite positive numbers on every retained row.")
        if respondent_column:
            weight_counts = work.groupby(respondent_column, dropna=False, observed=True)[weight_column].nunique(dropna=False)
            if bool((weight_counts > 1).any()):
                raise DataProblem("A respondent's survey weight must be constant across every brand they rated.")
    if respondent_column:
        missing_respondent = _blank_ids(work[respondent_column])
        if bool(missing_respondent.any()):
            raise DataProblem("Respondent IDs cannot be blank when respondent-level data are selected.")
        if bool(work.duplicated([respondent_column, brand_column]).any()):
            raise DataProblem(
                "The same respondent-brand pair appears more than once. Keep one wide rating row per respondent and brand."
            )

    grouped = work.groupby(brand_column, sort=True, observed=True)
    counts = grouped[chosen].count().astype(int)
    if respondent_column:
        counts.insert(0, "respondents", grouped[respondent_column].nunique())
    else:
        counts.insert(0, "rating_rows", grouped.size())

    if weight_column:
        # Same weighted mean as _weighted_mean per brand and attribute, computed with grouped sums.
        weights = work[weight_column].to_numpy(dtype=float)
        brand_codes = work[brand_column].cat.codes.to_numpy()
        brand_index = pd.Index(work[brand_column].cat.categories, name=brand_column)
        size = len(brand_index)
        means: dict[str, np.ndarray] = {}
        for attribute in chosen:
            values = work[attribute].to_numpy(dtype=float)
            valid = ~np.isnan(values)
            valid_weights = np.where(valid, weights, 0.0)
            weighted_values = np.bincount(brand_codes, weights=np.where(valid, values, 0.0) * valid_weights, minlength=size)
            weight_sums = np.bincount(brand_codes, weights=valid_weights, minlength=size)
            squared_sums = np.bincount(brand_codes, weights=np.square(valid_weights), minlength=size)
            with np.errstate(divide="ignore", invalid="ignore"):
                means[attribute] = np.where(weight_sums > 0, weighted_values / weight_sums, np.nan)
                effective = np.where(squared_sums > 0, np.square(weight_sums) / squared_sums, 0.0)
            counts[f"{attribute}__effective_n"] = pd.Series(effective, index=brand_index).reindex(counts.index)
        profiles = pd.DataFrame(means, index=brand_index)
    else:
        profiles = grouped[chosen].mean()
    # Aggregated tables are small; plain text indexes keep downstream code independent of category storage.
    profiles.index = pd.Index(profiles.index.astype(str), name=brand_column)
    counts.index = pd.Index(counts.index.astype(str), name=brand_column)

    incomplete = [str(column) for column in profiles.columns if bool(profiles[column].isna().any())]
    if incomplete and missing_policy == "error":
        raise DataProblem(
            "At least one brand has no usable rating for: " + ", ".join(incomplete) + ". "
            "Add ratings or choose the option to remove incomplete attributes."
        )
    if missing_policy not in {"drop_attributes", "error"}:
        raise DataProblem("Unknown missing-data policy.")
    profiles = profiles.drop(columns=incomplete, errors="ignore")
    constant = [str(column) for column in profiles.columns if int(profiles[column].nunique(dropna=True)) <= 1]
    profiles = profiles.drop(columns=constant, errors="ignore")
    if profiles.shape[1] < 2:
        raise DataProblem(
            "Fewer than two complete, varying attributes remain. Add ratings, choose different attributes, or fix constants."
        )
    if profiles.shape[0] < 3:
        raise DataProblem("Fewer than three usable brands remain after aggregation.")
    if not np.isfinite(profiles.to_numpy(dtype=float)).all():
        raise DataProblem("The aggregated brand profiles contain non-finite values.")

    return ProfileData(
        profiles=profiles.astype(float),
        counts=counts,
        source_rows=work,
        brand_column=brand_column,
        attributes=tuple(str(column) for column in profiles.columns),
        respondent_column=respondent_column,
        weight_column=weight_column,
        excluded_incomplete=tuple(incomplete),
        excluded_constant=tuple(constant),
        dropped_brand_rows=dropped_brand_rows,
    )
