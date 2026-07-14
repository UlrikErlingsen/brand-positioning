# Data guide

PositionSignal accepts CSV, Excel, or JSON tables in either of two wide layouts:

1. one already-aggregated row per brand; or
2. one row per respondent-brand rating occasion.

The first row must contain unique column names. Keep brand and attribute names stable: `Northloop` and `North loop` are treated as different brands.

## Option A: aggregated brand profiles

Use one row per brand and one numeric column per attribute.

| brand | quality | value_for_money | innovation | comfort |
|---|---:|---:|---:|---:|
| Brand A | 5.8 | 4.7 | 6.1 | 5.5 |
| Brand B | 5.1 | 6.0 | 4.4 | 6.2 |
| Brand C | 6.2 | 4.1 | 5.0 | 5.4 |

Select `brand` as the brand column and the rating fields as attributes. Do not select sample sizes, market share, price, or other numeric metadata unless they are intentionally part of the perceptual space.

This layout is useful when a research supplier has already delivered brand means. It can produce the complete PCA map and fidelity diagnostics, but not respondent bootstrap uncertainty. A table of means does not retain the sampling dependence needed to estimate those regions.

## Option B: respondent-brand ratings

Use one row for every respondent-brand pair and one column per attribute.

| respondent_id | brand | quality | value_for_money | innovation | comfort | sample_weight |
|---|---|---:|---:|---:|---:|---:|
| R0001 | Brand A | 6 | 4 | 6 | 5 | 0.92 |
| R0001 | Brand B | 5 | 6 | 4 | 6 | 0.92 |
| R0002 | Brand A | 7 | 4 | 5 | 6 | 1.14 |

Rules:

- each respondent-brand pair may appear only once;
- a respondent may rate all brands or a subset;
- respondent IDs must be present and nonblank if selected;
- use pseudonymous study IDs, not names or contact details;
- ratings must be numeric or blank;
- keep the same response direction across an attribute: a larger number should consistently mean “more” of the named quality.

PositionSignal aggregates these rows to one brand mean per attribute before PCA. Supplying respondent IDs also enables respondent-cluster bootstrap uncertainty, provided there are at least 20 distinct respondents and the design is sufficiently complete.

## Optional weights

A weight column is optional. If selected, every retained value must be finite and strictly positive. A respondent's weight must be constant on every row belonging to that respondent. For example, if `R0001` has weight `0.92`, all of that respondent's brand rows must also have `0.92`.

Weights change the brand means. PositionSignal also reports attribute-level Kish effective bases so highly unequal weights are visible. Ordinary expansion weights do not by themselves reproduce stratification, primary sampling units, replicate-weight variance, or finite-population corrections. For complex survey inference, consult the study's survey statistician.

If the study is unweighted, omit the weight column or leave it unselected. Do not enter zero, negative, or blank weights as a way to exclude rows; remove those rows explicitly.

## Missing ratings

An occasional blank respondent rating is allowed. Each brand-attribute cell is averaged from the available ratings in that cell, and its valid count is reported.

An **empty cell** is different: if no respondent supplied any usable rating for one brand on one attribute, the aggregated matrix is incomplete. PositionSignal never mean-imputes that cell. Choose one of the transparent remedies:

- add or correct the missing source ratings;
- stop and remove the affected attribute yourself; or
- explicitly allow the app to drop that incomplete attribute for every brand.

For an aggregated-wide file, any blank brand value creates the same incomplete-cell problem. Attributes that are constant across every brand are removed because they cannot position brands.

Inspect the valid and effective bases before interpreting small differences. A brand with a much smaller or differently composed base can appear separated for sampling reasons rather than perception.

## Rating scales and attribute design

The demo uses a 1-to-7 scale, but other numeric scales are accepted. The default standardization gives each attribute equal variance across brands, so mixed numeric ranges do not dominate solely through units. Even so, use consistent, clearly anchored questions whenever possible.

Good attribute names describe one direction, such as `innovative`, `comfortable`, or `good_value`. Avoid ambiguous bipolar labels such as `traditional_modern`; split or recode them before upload so higher values have a clear interpretation.

Do not include several near-duplicate attributes unless the repeated weighting is intentional. `premium`, `high_end`, and `exclusive` can make one idea dominate the solution. Conversely, attributes with no meaningful brand variation add no positioning information.

The current release supports at most 40 selected attributes and 60 brands in one map. Five or more brands and several distinct attributes generally make a more informative strategic display, although the mathematical minimum is three brands and two attributes.

## Templates and examples

The `examples` folder contains:

- `demo_sneaker_ratings.csv` — 180 synthetic respondents rating six fictional sneaker brands on eight 1-to-7 attributes, with a constant-per-respondent sample weight;
- `demo_brand_profiles.csv` — weighted brand means derived from that respondent demo;
- `ratings_template.csv` — a small respondent-wide starter table; and
- `ratings_template.xlsx` — the same starter table in Excel format.

The example records are entirely fictional and contain no direct personal information. Delete or replace the sample rows in a template before using real study data. Preserve the column roles, but rename the attribute columns to match the study.

## CSV, Excel, and JSON notes

- CSV: use a header row and a normal comma, semicolon, or tab-delimited text file. UTF-8 is safest.
- Excel: place the table in a simple rectangular sheet with one header row. Avoid merged cells, formulas that return errors, subtotals, and notes above the header.
- JSON: use a list of row objects, or an object whose values are named lists of row objects.
- Numeric decimal separators must be readable as numbers in the chosen file format.
- The uploader accepts `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` within its configured size limits.

## Privacy and research hygiene

PositionSignal needs a pseudonymous respondent key only to keep one person's rows together during bootstrap resampling. It does not need names, email addresses, telephone numbers, postal addresses, open-text comments, or customer account IDs. Remove direct identifiers before upload and avoid encoding them inside `respondent_id`.

When PositionSignal is run locally, analysis occurs on that machine. A separately hosted Streamlit deployment follows the hosting operator's storage, logging, access-control, and retention policies; verify those policies before uploading confidential research.

## Preflight checklist

- One row per brand, or one row per respondent-brand pair.
- At least three brands; five or more recommended.
- At least two numeric, varying attributes.
- One clear direction per attribute.
- No duplicate respondent-brand rows.
- Positive, finite, constant-per-respondent weights if used.
- No wholly empty brand-attribute cell.
- Plausible valid bases for every brand and attribute.
- Direct identifiers removed.
- Competitors and attributes match the strategic question.
