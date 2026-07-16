<p align="center">
  <img src="assets/positionsignal-banner.svg" alt="PositionSignal — See where brands stand" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/brand-positioning/actions/workflows/tests.yml"><img alt="Tests" src="https://github.com/UlrikErlingsen/brand-positioning/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-173C3A?logo=python&logoColor=white">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-D95B40?logo=streamlit&logoColor=white">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-36534E"></a>
</p>

<p align="center"><strong>Open perceptual mapping for marketers — brand-attribute ratings in, an auditable two-dimensional positioning map out.</strong></p>

**PositionSignal** turns brand ratings into a point-and-click PCA biplot. It shows where a focus brand sits relative to competitors, which attributes create separation, how much information the two-dimensional picture retains, and which conclusions still require caution. The app runs locally, needs no account, and exports the map together with the evidence needed to audit it.

## Read this first

> **Treat the map as decision support, not objective market truth.** It depends on the respondents, competitors, attributes, scaling, and missing-data choices. A two-dimensional view necessarily leaves information out.

PositionSignal does not label empty map space as demand, turn association into causation, or treat a visually close competitor as definitive when the complete profile says otherwise. It keeps the full-space diagnostics beside the picture so users can challenge the map.

## Try it in two minutes

1. Start the app and click **Demo · sneaker ratings** in the sidebar. The demo contains 180 fictional respondents, six fictional brands, and eight 1-to-7 attributes.
2. On **1 · Data & setup**, keep the suggested brand, respondent ID, sample-weight, and attribute roles. Keep **Remove that attribute from every brand (recommended)** as the empty-cell policy, then click **Save this data setup**.
3. On **2 · Build the map**, choose the brand to highlight and keep **Equal influence (standardize; recommended)**. Leave bootstrap uncertainty off for this quick run and click **Build perceptual map**.
4. Read the map, variance retained, focus-brand fit, nearest full-profile competitor, distance stress, correlation circle, scree plot, and profile matrix.
5. Click **Interpret this position**. Review the focus-brand comparison and the warning that apparent white space is not proven opportunity.
6. Under **Download the evidence**, choose the Excel, CSV ZIP, JSON, or standalone interactive HTML export.

The demo is deliberately useful but imperfect. It is synthetic, contains no real respondents, and should not be read as evidence about an actual sneaker market.

## The two supported data grains

PositionSignal accepts `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` tables in exactly two wide layouts.

### 1. Aggregated brand profiles

Use one row per brand and one numeric column per attribute:

| brand | quality | good_value | innovative | comfortable |
|---|---:|---:|---:|---:|
| Brand A | 5.8 | 4.7 | 6.1 | 5.5 |
| Brand B | 5.1 | 6.0 | 4.4 | 6.2 |
| Brand C | 6.2 | 4.1 | 5.0 | 5.4 |

This layout is appropriate when a research supplier has already delivered brand means. It supports the full PCA map and fidelity diagnostics, but it cannot support respondent-sampling uncertainty: aggregate means no longer contain the dependence needed for honest bootstrap regions.

### 2. Respondent-brand ratings

Use one row per respondent-brand pair and one numeric column per attribute:

| respondent_id | brand | quality | good_value | innovative | comfortable | sample_weight |
|---|---|---:|---:|---:|---:|---:|
| R0001 | Brand A | 6 | 4 | 6 | 5 | 0.92 |
| R0001 | Brand B | 5 | 6 | 4 | 6 | 0.92 |
| R0002 | Brand A | 7 | 4 | 5 | 6 | 1.14 |

Each respondent-brand pair must be unique. A respondent may rate every brand or a subset. Respondent IDs should be pseudonymous; they are used only to keep one person's rows together during optional bootstrap resampling. Survey weights are optional, positive, finite, and constant across every row belonging to the same respondent.

PositionSignal aggregates respondent rows to one brand mean per attribute before fitting PCA. This makes the axes describe between-brand positioning rather than within-brand response noise. See the [data guide](docs/data_guide.md) for missing-cell policy, rating direction, templates, limits, weights, and file-format details.

## What the app does

- **Guided setup:** suggests brand, respondent, weight, and numeric attribute columns while leaving every role editable.
- **Data audit:** reports missingness, constants, valid cell bases, weighted Kish effective bases, and likely direct-identifier fields.
- **Transparent aggregation:** uses available-case brand means or weighted means; it never silently fills an empty brand-attribute cell.
- **Deliberate scaling:** standardizes attributes across brands by default, with a center-only expert option for genuinely comparable units.
- **Auditable PCA:** uses deterministic full-SVD PCA and a stable sign convention so harmless row reordering does not mirror exports.
- **Correct biplot geometry:** displays ordinary brand scores and attribute coefficients with one reciprocal common scaling factor; the two axes are never stretched independently.
- **Separate correlation circle:** provides actual attribute-component correlations instead of asking users to read main-map arrow angles as literal correlations.
- **Focus-brand interpretation:** ranks the nearest competitors using the complete selected-attribute space, not only the two-dimensional projection.
- **Optional uncertainty:** cluster-bootstraps respondents, rebuilds the profiles and PCA, and aligns maps with orthogonal Procrustes rotation before drawing covariance ellipses.
- **Portable evidence:** produces Excel, CSV ZIP, JSON with an audit trail, a standalone interactive HTML map, and a high-resolution PNG through Plotly's chart toolbar.

## Diagnostics that travel with the map

PositionSignal reports the components needed to decide whether the picture is a useful summary:

- PC1, PC2, and cumulative explained variance;
- brand representation in two dimensions (cos²) and brand contributions;
- attribute correlations, representation, coefficients, and contributions;
- full-space and projected pairwise distances;
- full-versus-map distance correlation and normalized distance error (“stress”);
- PC1–PC2 and PC2–PC3 eigengaps as descriptive stability clues;
- the complete prepared brand-profile matrix and cell bases;
- successful/requested bootstrap iterations and aligned uncertainty points when respondent data are available; and
- source fingerprint, column roles, scaling convention, software versions, settings, and caution text in the export manifest.

No single threshold certifies a map. With exactly three brands, a centered profile matrix has rank at most two, so 100% retained variance is automatic geometry rather than strong evidence.

## Method in brief

1. Aggregate the selected ratings to a complete brand-by-attribute mean matrix.
2. Remove constant attributes and either stop on or explicitly remove attributes with an empty brand cell.
3. Center every attribute and, by default, divide it by its sample standard deviation across brands.
4. Fit principal component analysis with a deterministic full singular-value decomposition.
5. Plot PC1 and PC2 as a row-metric Gabriel biplot: brands are the primary geometry, while attribute arrows show reconstructed directions.
6. Compare the two-dimensional picture with complete-space distances and representation diagnostics.
7. When respondent IDs are present and uncertainty is requested, resample respondents—not rows—then align each refitted map before summarizing the coordinate cloud.

PCA signs and quadrants have no intrinsic meaning. Axis helper text summarizes strong associations but does not turn a component into an objectively named construct. Full equations, conventions, and interpretation rules are in [methods and interpretation](docs/methods.md).

## Run locally

You need Python 3.10 or newer and a local copy of this project folder.

**macOS:** double-click `run_app.command`.

**Windows:** double-click `run_app.bat`.

The first launch creates a private `.venv` and downloads the open-source dependencies. Later launches reuse it. Or use a terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Docker

```bash
docker build -t positionsignal .
docker run --rm -p 8501:8501 positionsignal
```

Then open `http://127.0.0.1:8501`. The container runs the app as a non-root user. This repository does not document or promise a hosted public instance.

## No install? Give this file to an AI

Don't want to install anything? [AI_ANALYST.md](AI_ANALYST.md) is a single copy-paste file that turns a capable AI assistant (Claude, ChatGPT, Gemini, …) into this analysis. Copy the file into a chat, add your data, and the AI follows the same published methods and honesty rules as the app. The app is still the more private option: local mode keeps your data on your computer, while a cloud AI sees whatever you paste.

## Tests and development checks

Install the package with its test tools, then run both checks:

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
```

The test suite checks weighted and unweighted aggregation, missing-data behavior, PCA covariance/eigenvalues, affine and row-order invariance, distance preservation, deterministic bootstrap alignment, export safety, and JSON/Excel/CSV round trips. See [CONTRIBUTING.md](CONTRIBUTING.md) before changing statistical behavior.

## Privacy and responsible use

Local mode reads uploads into the Python process on that computer. PositionSignal adds no accounts, advertising, telemetry, external AI calls, or built-in research-data storage. Exports are created only when requested, and the source file is never modified.

A separately hosted deployment changes the trust boundary: uploads travel to the chosen server, whose operator controls authentication, logs, retention, backups, and jurisdiction. Remove names, email addresses, phone numbers, postal addresses, free text, and unnecessary identifiers before upload. Read [PRIVACY.md](PRIVACY.md) and [SECURITY.md](SECURITY.md).

## Important limitations

- The mathematical minimum is three brands and two varying attributes; five or more relevant brands usually make a more informative competitive frame. The release caps a map at 60 brands and 40 selected attributes.
- Rating-scale steps are treated as approximately interval-scaled so means and PCA are usable. That conventional assumption may not suit every instrument.
- The result is conditional on the chosen respondents, brands, attributes, weights, and preparation. Changing the competitive frame changes the coordinate system.
- PCA describes linear structure. Curved, nonmetric, respondent-specific, or ideal-point spaces may need other methods.
- Correlated or near-duplicate attributes can give one idea extra influence.
- Ordinary survey weights do not reproduce stratification, primary sampling units, replicate-weight variance, or finite-population corrections.
- A perceptual gap is not demand, feasibility, differentiation, profitability, or causality.
- Raw text, images, mention counts, nonmetric proximities, ideal points, longitudinal tracking, choice modeling, and causal analysis are outside version 1.0.

## Relationship to the Signal tools

These apps share a visual language but answer different questions:

- **[WorthSignal](https://github.com/UlrikErlingsen/customer-value-analytics)** asks what customers and customer relationships are worth: targeting, CLV, retention, customer equity, and marketing ROI.
- **[SegmentSignal](https://github.com/UlrikErlingsen/customer-segmentation)** asks whether customers form stable, useful groups and profiles those groups.
- **[ChoiceSignal](https://github.com/UlrikErlingsen/conjoint-analysis)** asks how product attributes drive choice: conjoint part-worth utilities, attribute importance, and preference-share simulation.
- **[AdoptSignal](https://github.com/UlrikErlingsen/adoption-forecasting)** asks when a new product gets adopted: Bass diffusion forecasting from published analogies or real history.
- **[DriverSignal](https://github.com/UlrikErlingsen/survey-driver-analysis)** asks which measured experiences move with satisfaction or recommendation scores.
- **[AllocSignal](https://github.com/UlrikErlingsen/marketing-mix-allocation)** asks where the next marketing budget should go, given response assumptions and constraints.
- **[GateSignal](https://github.com/UlrikErlingsen/launch-decision-gate)** asks whether a concept should receive the next bounded investment: gates, evidence, scenario economics, and risk triage.
- **[ExperimentSignal](https://github.com/UlrikErlingsen/experiment-analysis)** asks whether a randomized treatment caused a change worth acting on.
- **[MeasureSignal](https://github.com/UlrikErlingsen/measurement-validation)** asks whether a multi-item score measures what you think it does.
- **[TextSignal](https://github.com/UlrikErlingsen/open-text-analysis)** asks what recurring language patterns appear in open-ended responses.
- **PositionSignal** asks how brands are perceived relative to competitors on a chosen set of attributes.

Perception is not preference. A brand can occupy a distinctive PositionSignal location without winning ChoiceSignal simulations, and a valuable customer group in WorthSignal or SegmentSignal does not automatically perceive the market in the same way.

## Primary references

- Gabriel, K. R. (1971). [The biplot graphic display of matrices with application to principal component analysis](https://doi.org/10.1093/biomet/58.3.453). *Biometrika, 58*(3), 453–467.
- Jolliffe, I. T., & Cadima, J. (2016). [Principal component analysis: a review and recent developments](https://doi.org/10.1098/rsta.2015.0202). *Philosophical Transactions of the Royal Society A, 374*, 20150202.
- Schönemann, P. H. (1966). [A generalized solution of the orthogonal Procrustes problem](https://doi.org/10.1007/BF02289451). *Psychometrika, 31*, 1–10.
- Josse, J., Wager, S., & Husson, F. (2016). [Confidence areas for fixed-effects PCA](https://doi.org/10.1080/10618600.2014.950871). *Journal of Computational and Graphical Statistics, 25*(1), 28–48.

If PositionSignal supports research or teaching, cite the software metadata in [CITATION.cff](CITATION.cff) and the original method sources relevant to the analysis.

## License

PositionSignal is free software under **AGPL-3.0-or-later**. Commercial use is allowed; distribution and modified network services carry the source-sharing obligations in [LICENSE](LICENSE). The license covers this project's code and documentation, not ownership of the published statistical methods it implements.

This application was developed with AI coding assistance and checked through source review and automated tests. Verify important results independently; no warranty is provided.
