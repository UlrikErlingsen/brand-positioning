"""Schema inference, aggregation, and validation for brand-rating data."""

from __future__ import annotations

from dataclasses import dataclass
import re

import numpy as np
import pandas as pd

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


def numeric_candidates(frame: pd.DataFrame, excluded: list[str] | tuple[str, ...] = ()) -> list[str]:
    """Return columns that are numeric or at least 85% numeric-like."""
    blocked = set(excluded)
    result: list[str] = []
    for column in frame.columns:
        name = str(column)
        if name in blocked:
            continue
        series = frame[column]
        nonmissing = series.dropna()
        if nonmissing.empty:
            continue
        converted = pd.to_numeric(nonmissing, errors="coerce")
        if pd.api.types.is_numeric_dtype(series) or float(converted.notna().mean()) >= 0.85:
            if int(converted.nunique(dropna=True)) > 1:
                result.append(name)
    return result


def likely_pii_columns(frame: pd.DataFrame) -> list[str]:
    """Flag obvious direct-identifier fields that are unnecessary for mapping."""
    flagged: list[str] = []
    for column in frame.columns:
        name = str(column)
        if PII_PATTERN.search(name):
            flagged.append(name)
            continue
        sample = frame[column].dropna().astype(str).head(100)
        if not sample.empty and float(sample.str.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$").mean()) > 0.7:
            flagged.append(name)
    return flagged


def data_quality_report(frame: pd.DataFrame) -> pd.DataFrame:
    """Build a compact column-level audit."""
    pii = set(likely_pii_columns(frame))
    rows: list[dict[str, object]] = []
    for column in frame.columns:
        series = frame[column]
        rows.append(
            {
                "column": str(column),
                "type": str(series.dtype),
                "missing_%": round(100 * float(series.isna().mean()), 1),
                "unique": int(series.nunique(dropna=True)),
                "constant": bool(series.nunique(dropna=True) <= 1),
                "privacy_note": "direct identifier" if str(column) in pii else "",
            }
        )
    return pd.DataFrame(rows)


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
    if len(chosen) > 40:
        raise DataProblem("Use at most 40 attributes so the map remains stable and interpretable.")
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
    raw_brands = work[brand_column]
    work[brand_column] = raw_brands.where(raw_brands.notna(), "").astype(str).str.strip()
    valid_brand = work[brand_column].ne("") & work[brand_column].str.lower().ne("nan")
    dropped_brand_rows = int((~valid_brand).sum())
    work = work.loc[valid_brand].copy()
    if work.empty:
        raise DataProblem("No rows contain a usable brand name.")
    if work[brand_column].nunique() < 3:
        raise DataProblem("A two-dimensional map needs ratings for at least three brands.")
    if work[brand_column].nunique() > 60:
        raise DataProblem("This release maps at most 60 brands at once. Keep the competitors relevant to the decision.")

    for attribute in chosen:
        work[attribute] = pd.to_numeric(work[attribute], errors="coerce")
    if weight_column:
        work[weight_column] = pd.to_numeric(work[weight_column], errors="coerce")
        invalid_weight = work[weight_column].isna() | ~np.isfinite(work[weight_column]) | (work[weight_column] <= 0)
        if bool(invalid_weight.any()):
            raise DataProblem("Survey weights must be finite positive numbers on every retained row.")
        if respondent_column:
            weight_counts = work.groupby(respondent_column, dropna=False)[weight_column].nunique(dropna=False)
            if bool((weight_counts > 1).any()):
                raise DataProblem("A respondent's survey weight must be constant across every brand they rated.")
    if respondent_column:
        missing_respondent = work[respondent_column].isna() | work[respondent_column].astype(str).str.strip().eq("")
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
        rows: dict[str, dict[str, float]] = {}
        for brand, group in grouped:
            rows[str(brand)] = {
                attribute: _weighted_mean(group[attribute], group[weight_column]) for attribute in chosen
            }
        profiles = pd.DataFrame.from_dict(rows, orient="index").sort_index()
        profiles.index.name = brand_column
        for attribute in chosen:
            effective: dict[str, float] = {}
            for brand, group in grouped:
                valid = group[attribute].notna()
                weights = group.loc[valid, weight_column].astype(float)
                squared_sum = float(np.square(weights).sum())
                effective[str(brand)] = float(weights.sum() ** 2 / squared_sum) if squared_sum > 0 else 0.0
            counts[f"{attribute}__effective_n"] = pd.Series(effective)
    else:
        profiles = grouped[chosen].mean()

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
