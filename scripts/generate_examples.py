"""Regenerate PositionSignal's fictional examples and starter templates.

Every record is synthetic. The respondent key is an arbitrary study ID and no
direct personal information is generated.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"
SEED = 20260714
RESPONDENTS = 180

ATTRIBUTES = [
    "quality",
    "value_for_money",
    "innovation",
    "style",
    "sustainability",
    "comfort",
    "performance",
    "exclusivity",
]

# Six deliberately different fictional positions on a 1-to-7 rating scale.
BRAND_PROFILES = {
    "Aster Run": [6.1, 4.7, 6.2, 5.4, 4.3, 5.8, 6.4, 5.2],
    "Northloop": [5.7, 5.2, 5.3, 6.3, 4.8, 5.4, 5.1, 5.9],
    "Morrow Pace": [5.2, 6.2, 4.5, 4.2, 4.6, 6.0, 5.0, 3.8],
    "Ember Trail": [5.9, 4.9, 5.1, 4.4, 6.0, 5.6, 6.1, 4.7],
    "Luma Court": [5.0, 5.5, 5.8, 6.1, 5.3, 4.9, 4.7, 5.5],
    "Foundry One": [6.3, 4.1, 4.4, 5.0, 5.8, 5.7, 5.5, 6.4],
}


def sneaker_ratings() -> pd.DataFrame:
    """Create a complete respondent-by-brand panel with realistic rating noise."""
    rng = np.random.default_rng(SEED)
    rows: list[dict[str, float | str]] = []

    for respondent_number in range(1, RESPONDENTS + 1):
        respondent_id = f"R{respondent_number:04d}"
        sample_weight = float(np.round(np.clip(rng.lognormal(mean=-0.025, sigma=0.24), 0.50, 2.00), 3))
        response_style = rng.normal(0.0, 0.30)
        attribute_style = rng.normal(0.0, 0.17, len(ATTRIBUTES))
        brand_style = rng.normal(0.0, 0.16, len(BRAND_PROFILES))

        for brand_index, (brand, base_profile) in enumerate(BRAND_PROFILES.items()):
            base = np.asarray(base_profile, dtype=float)
            noise = rng.normal(0.0, 0.43, len(ATTRIBUTES))
            ratings = np.clip(base + response_style + attribute_style + brand_style[brand_index] + noise, 1.0, 7.0)
            ratings = np.round(ratings, 1)
            row: dict[str, float | str] = {
                "respondent_id": respondent_id,
                "brand": brand,
            }
            row.update(dict(zip(ATTRIBUTES, ratings.astype(float))))
            row["sample_weight"] = sample_weight
            rows.append(row)

    columns = ["respondent_id", "brand", *ATTRIBUTES, "sample_weight"]
    return pd.DataFrame(rows, columns=columns)


def aggregate_profiles(ratings: pd.DataFrame) -> pd.DataFrame:
    """Calculate weighted brand means using the same cell-wise rule as the app."""
    output_rows: list[dict[str, float | str]] = []
    for brand in BRAND_PROFILES:
        group = ratings.loc[ratings["brand"] == brand]
        row: dict[str, float | str] = {"brand": brand}
        weights = group["sample_weight"].to_numpy(dtype=float)
        for attribute in ATTRIBUTES:
            values = group[attribute].to_numpy(dtype=float)
            row[attribute] = float(np.average(values, weights=weights))
        output_rows.append(row)
    profiles = pd.DataFrame(output_rows, columns=["brand", *ATTRIBUTES])
    profiles[ATTRIBUTES] = profiles[ATTRIBUTES].round(3)
    return profiles


def ratings_template() -> pd.DataFrame:
    """Return a compact, valid respondent-wide starter table."""
    rows = [
        ["R0001", "Brand A", 6, 4, 6, 5, 4, 6, 6, 5, 0.90],
        ["R0001", "Brand B", 5, 6, 4, 6, 5, 5, 5, 4, 0.90],
        ["R0001", "Brand C", 6, 5, 5, 4, 6, 6, 6, 5, 0.90],
        ["R0002", "Brand A", 7, 4, 6, 5, 4, 6, 7, 5, 1.10],
        ["R0002", "Brand B", 5, 6, 5, 7, 5, 5, 5, 5, 1.10],
        ["R0002", "Brand C", 6, 5, 5, 4, 6, 6, 6, 6, 1.10],
    ]
    return pd.DataFrame(rows, columns=["respondent_id", "brand", *ATTRIBUTES, "sample_weight"])


def _verify(ratings: pd.DataFrame, profiles: pd.DataFrame) -> None:
    expected_rows = RESPONDENTS * len(BRAND_PROFILES)
    if len(ratings) != expected_rows:
        raise RuntimeError(f"Expected {expected_rows} respondent-brand rows, found {len(ratings)}.")
    if ratings["respondent_id"].nunique() != RESPONDENTS:
        raise RuntimeError("The demo does not contain the intended number of respondents.")
    if not bool((ratings.groupby("respondent_id")["sample_weight"].nunique() == 1).all()):
        raise RuntimeError("Every respondent must retain one constant sample weight.")
    counts = ratings.groupby("brand")[ATTRIBUTES].count()
    if int(counts.to_numpy().min()) < RESPONDENTS:
        raise RuntimeError("Every fictional brand-attribute cell must be fully rated.")

    values = profiles.set_index("brand")[ATTRIBUTES].to_numpy(dtype=float)
    scales = values.std(axis=0, ddof=1)
    standardized = (values - values.mean(axis=0)) / scales
    if int(np.linalg.matrix_rank(standardized)) <= 2:
        raise RuntimeError("The demo profile matrix must contain more than two dimensions.")


def _write_excel_template(template: pd.DataFrame, path: Path) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        template.to_excel(writer, sheet_name="Ratings", index=False)
        sheet = writer.sheets["Ratings"]
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cells in sheet.columns:
            width = min(max(len(str(cell.value)) if cell.value is not None else 0 for cell in cells) + 2, 24)
            sheet.column_dimensions[cells[0].column_letter].width = max(width, 10)


def main() -> None:
    EXAMPLES.mkdir(exist_ok=True)
    ratings = sneaker_ratings()
    profiles = aggregate_profiles(ratings)
    template = ratings_template()
    _verify(ratings, profiles)

    ratings.to_csv(EXAMPLES / "demo_sneaker_ratings.csv", index=False)
    profiles.to_csv(EXAMPLES / "demo_brand_profiles.csv", index=False)
    template.to_csv(EXAMPLES / "ratings_template.csv", index=False)
    _write_excel_template(template, EXAMPLES / "ratings_template.xlsx")
    print(f"Wrote {len(ratings):,} synthetic rating rows and four example files to {EXAMPLES}")


if __name__ == "__main__":
    main()
