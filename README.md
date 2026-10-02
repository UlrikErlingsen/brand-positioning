<p align="center">
  <img src="assets/positionsignal-banner.png" alt="Position Signal: Where do brands sit relative to competitors?" width="100%">
</p>

<p align="center">
  <a href="https://github.com/UlrikErlingsen/brand-positioning/actions"><img alt="Tests" src="https://github.com/UlrikErlingsen/brand-positioning/actions/workflows/tests.yml/badge.svg"></a>
  <a href="https://github.com/UlrikErlingsen/signal-hub"><img alt="Signal · Brand" src="https://img.shields.io/badge/Signal-Brand-b2622d?labelColor=2e2b25"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-2e2b25?logo=python&logoColor=f9f4ed">
  <img alt="Streamlit" src="https://img.shields.io/badge/Streamlit-app-b2622d?logo=streamlit&logoColor=f9f4ed">
  <a href="LICENSE"><img alt="License: AGPL-3.0-or-later" src="https://img.shields.io/badge/License-AGPL--3.0--or--later-645c50"></a>
</p>

<p align="center"><strong>Open perceptual mapping for marketers — brand-attribute ratings in, an auditable two-dimensional positioning map out.</strong></p>

**Position Signal** turns brand ratings into a point-and-click PCA biplot. It shows where a focus brand sits relative to competitors, which attributes create separation, how much information the two-dimensional picture retains, and which conclusions still require caution. It combines guided data setup, one auditable PCA map with full-space diagnostics, declared wave and segment comparisons, association-leadership and POP/POD reporting, and exports that carry the evidence needed to audit the map.

> Where do brands sit relative to competitors, which attributes create the separation, and how much does the two-dimensional picture leave out?

Everything runs locally with open-source Python packages. There is no account, telemetry, advertising, external AI call, remote database, or built-in persistence.

## Read this first

> **Treat the map as decision support, not objective market truth.** It depends on the respondents, competitors, attributes, scaling, and missing-data choices. A two-dimensional view necessarily leaves information out.

Position Signal does not label empty map space as demand, turn association into causation, or treat a visually close competitor as definitive when the complete profile says otherwise. It keeps the full-space diagnostics beside the picture so users can challenge the map.

No single threshold certifies a map. With exactly three brands, a centered profile matrix has rank at most two, so 100% retained variance is automatic geometry rather than strong evidence.

## Scope

**Version 1.2 supports:**

- **Guided setup:** suggests brand, respondent, weight, and numeric attribute columns while leaving every role editable.
- **Data audit:** reports missingness, constants, valid cell bases, weighted Kish effective bases, and likely direct-identifier fields.
- **Transparent aggregation:** uses available-case brand means or weighted means; it never silently fills an empty brand-attribute cell.
- **Deliberate scaling:** standardizes attributes across brands by default, with a center-only expert option for genuinely comparable units.
- **Auditable PCA:** uses deterministic full-SVD PCA and a stable sign convention so harmless row reordering does not mirror exports.
- **Correct biplot geometry:** displays ordinary brand scores and attribute coefficients with one reciprocal common scaling factor; the two axes are never stretched independently.
- **Separate correlation circle:** provides actual attribute-component correlations instead of asking users to read main-map arrow angles as literal correlations.
- **Focus-brand interpretation:** ranks the nearest competitors using the complete selected-attribute space, not only the two-dimensional projection.
- **Tracking comparisons:** compares declared waves and segments, with independent-sample intervals and repeated-respondent warnings.
- **Position claims:** reports descriptive association leadership plus configurable points-of-parity/points-of-difference candidates.
- **Optional uncertainty:** cluster-bootstraps respondents, rebuilds the profiles and PCA, and aligns maps with orthogonal Procrustes rotation before drawing covariance ellipses.
- **Portable evidence:** produces Excel, CSV ZIP, JSON with an audit trail, a standalone interactive HTML map, and a high-resolution PNG through Plotly's chart toolbar.

**It does not:** forecast demand, prove that empty map space is an opportunity, identify why perception changed, establish legal "ownership" of an association, model choice, segment customers, track brand measures with multiple-comparison control, or estimate causal effects. Where a sibling app covers it, use **[Track Signal](https://github.com/UlrikErlingsen/brand-tracking)** for separate brand measures across tracking waves, **[Choice Signal](https://github.com/UlrikErlingsen/conjoint-analysis)** for attribute-driven choice, **[Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation)** for customer groups, **[Text Signal](https://github.com/UlrikErlingsen/open-text-analysis)** for open-ended language, and **[Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis)** for randomized causal effects.

Important limitations:

- The mathematical minimum is three brands and two varying attributes; five or more relevant brands usually make a more informative competitive frame. The release caps a map at 60 brands and 40 selected attributes.
- Rating-scale steps are treated as approximately interval-scaled so means and PCA are usable. That conventional assumption may not suit every instrument.
- The result is conditional on the chosen respondents, brands, attributes, weights, and preparation. Changing the competitive frame changes the coordinate system.
- PCA describes linear structure. Curved, nonmetric, respondent-specific, or ideal-point spaces may need other methods.
- Correlated or near-duplicate attributes can give one idea extra influence.
- Ordinary survey weights do not reproduce stratification, primary sampling units, replicate-weight variance, or finite-population corrections.
- A perceptual gap is not demand, feasibility, differentiation, profitability, or causality.
- Raw text, images, mention counts, nonmetric proximities, ideal points, choice modeling, and causal analysis remain outside the current release. Wave comparisons are descriptive unless supported by a suitable research design.

## Try the demo in three minutes

The app opens with a **fictional** sneaker market already loaded: 180 made-up respondents, six made-up brands, and eight 1-to-7 attributes, with the suggested data setup saved and a default map built. No upload is needed to see results.

1. Start the app. The welcome page confirms the preloaded demo; click **See the fictional market map** (or open **2 · Build the map** in the sidebar).
2. Read the map, variance retained, focus-brand fit, nearest full-profile competitor, distance stress, correlation circle, scree plot, and profile matrix. To change the highlighted brand, scaling, or bootstrap uncertainty, adjust the controls and click **Build perceptual map** again.
3. Open **1 · Data & setup** to see the roles the demo uses: the suggested brand, respondent ID, sample-weight, and attribute columns, with **Remove that attribute from every brand (recommended)** as the empty-cell policy.
4. Click **Interpret this position** (or open **4 · Interpret & export**). Review the focus-brand comparison and the warning that apparent white space is not proven opportunity.
5. Under **Download the evidence**, choose the Excel, CSV ZIP, JSON, or standalone interactive HTML export.
6. On **3 · Compare waves & segments**, click **Run position comparisons** for association ownership and POP/POD candidates.

The demo is deliberately useful but imperfect. It is deterministic synthetic data, contains no real respondents, and should not be read as evidence about an actual sneaker market. **Demo · sneaker ratings** in the sidebar reloads it; **Demo · brand summary** loads the same six fictional brands as aggregate profiles. Uploading your own file replaces the demo, and **Clear data and results** empties the app.

## Data contract

Position Signal accepts `.csv`, `.xlsx`, `.xls`, `.xlsm`, and `.json` tables in exactly two wide layouts. The loader limits file size (100 MB by default, configurable with `POSITIONSIGNAL_MAX_UPLOAD_MB`), expanded workbook size, row count, and total cells. A map uses at most 60 brands and 40 selected attributes.

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

Position Signal aggregates respondent rows to one brand mean per attribute before fitting PCA. This makes the axes describe between-brand positioning rather than within-brand response noise. The fictional demos and starter templates are in [`examples/`](examples/). See the [data guide](docs/data_guide.md) for missing-cell policy, rating direction, templates, limits, weights, and file-format details.

## Analysis contract

The app records these declarations before it fits anything, and every export carries them:

- **Column roles** for brand, optional respondent ID, and optional survey weight, plus the attributes that define the map. Ratings should all point in the same direction: higher means more of the named attribute.
- **Empty-cell policy:** remove an attribute that has no usable rating for some brand (recommended), or stop and fix the data. No empty brand-attribute cell is ever imputed.
- **Scaling:** equal influence (standardize across brands; the default) or keep observed dispersion (center only).
- **Uncertainty settings**, when respondent IDs exist: bootstrap iterations, ellipse level, and random seed.
- **Comparison roles and thresholds** on the comparison page: optional wave and segment columns with reference and comparison values, a focus brand, a POP/POD difference threshold, and a parity tolerance. These thresholds are declared decision rules, not universal academic cut-offs or significance tests.

## Methods

1. Aggregate the selected ratings to a complete brand-by-attribute mean matrix.
2. Remove constant attributes and either stop on or explicitly remove attributes with an empty brand cell.
3. Center every attribute and, by default, divide it by its sample standard deviation across brands.
4. Fit principal component analysis with a deterministic full singular-value decomposition.
5. Plot PC1 and PC2 as a row-metric Gabriel biplot: brands are the primary geometry, while attribute arrows show reconstructed directions.
6. Compare the two-dimensional picture with complete-space distances and representation diagnostics.
7. When respondent IDs are present and uncertainty is requested, resample respondents—not rows—then align each refitted map before summarizing the coordinate cloud.
8. When wave or segment fields are declared, compare brand-attribute means and classify association ownership/POP/POD candidates under explicit descriptive thresholds.

PCA signs and quadrants have no intrinsic meaning. Axis helper text summarizes strong associations but does not turn a component into an objectively named construct.

Diagnostics that travel with the map:

- PC1, PC2, and cumulative explained variance;
- brand representation in two dimensions (cos²) and brand contributions;
- attribute correlations, representation, coefficients, and contributions;
- full-space and projected pairwise distances;
- full-versus-map distance correlation and normalized distance error (“stress”);
- PC1–PC2 and PC2–PC3 eigengaps as descriptive stability clues;
- the complete prepared brand-profile matrix and cell bases;
- successful/requested bootstrap iterations and aligned uncertainty points when respondent data are available; and
- source fingerprint, column roles, scaling convention, software versions, settings, and caution text in the export manifest.

Full equations, conventions, and interpretation rules are in [methods and interpretation](docs/methods.md).

## Decision statuses

The app labels evidence descriptively; every label sits beside the numbers it summarizes.

Map read (share of profile variance retained in two dimensions; descriptive bands, not a test):

- **CLEAR TWO-DIMENSIONAL SUMMARY** (“Clear in 2-D”): at least 70% retained.
- **USEFUL BUT COMPRESSED** (“Compressed”): 50% to under 70% retained; read the map with the brand-level representation scores.
- **STRONGLY COMPRESSED VIEW** (“Highly compressed”): under 50% retained; rely on full-profile distances and diagnostics.

Association leadership (per attribute, among the selected brands):

- **DESCRIPTIVE LEADER**: the focus brand has the highest mean on the attribute.
- **NOT LEADING**: another selected brand has a higher mean.

Points of parity and difference (focus brand minus the competitor average, on the attribute's scale):

- **POINT OF DIFFERENCE CANDIDATE**: the lead reaches the declared difference threshold.
- **POINT OF PARITY CANDIDATE**: the absolute gap is within the declared parity tolerance.
- **COMPETITIVE DEFICIT**: the focus brand trails by at least the difference threshold.
- **INDETERMINATE**: the gap falls between the parity tolerance and the difference threshold.

Wave/segment differences, association leadership, and POP/POD labels remain conditional on the sampled respondents, competitor set, attributes, weights, and thresholds. They do not establish why perception changed, that an association is legally “owned,” or that a difference affects choice. Candidates should still be checked for customer importance, credibility, distinctiveness, and business value. See [methods and interpretation](docs/methods.md).

## Exports

The map evidence pack (Excel, CSV-ZIP, and JSON with an audit trail) includes:

- source filename, table and SHA-256 fingerprint;
- the column roles, attributes, scaling and PCA conventions, and the software version;
- brand profiles, cell bases, brand coordinates, attribute directions, explained variance, pairwise distances, and preprocessing centers and divisors;
- bootstrap ellipses and aligned points, when uncertainty was estimated;
- the diagnostics, exact reproducibility settings (bootstrap iterations, confidence, seed), software versions, and caution language.

The comparison page exports its own Excel, CSV-ZIP, and JSON pack: the manifest and comparison configuration, current profiles, association ownership, POP/POD candidates, wave and segment comparisons when declared, and interpretation warnings. The interactive map is also available as a standalone HTML file, and Plotly's chart toolbar saves a high-resolution PNG.

Exports are created only when requested, the source file is never modified, and spreadsheet exports neutralize formula-like text and column headers.

## Run locally

You need Python 3.10 or newer and a local copy of this folder.

**macOS:** double-click `run_app.command`. **Windows:** double-click `run_app.bat`.

The first launch creates a private `.venv` and downloads the open-source dependencies. Later launches reuse it. Or use a terminal:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Position Signal prefers local port `8501` and falls back to another free port on macOS. The launchers accept `POSITIONSIGNAL_PORT`; the macOS launcher also accepts `POSITIONSIGNAL_MAX_UPLOAD_MB` and `POSITIONSIGNAL_NO_BROWSER=1`. Set `POSITIONSIGNAL_DEBUG=1` to reveal unexpected technical error details.

### Docker

```bash
docker build -t positionsignal .
docker run --rm -p 8501:8501 positionsignal
```

Then open `http://127.0.0.1:8501`. The container runs the app as a non-root user and includes a health check. This repository does not document or promise a hosted public instance.

## Privacy

Local mode reads uploads into the Python process on that computer. Position Signal adds no accounts, advertising, telemetry, external AI calls, or built-in research-data storage. Exports are created only when requested, and the source file is never modified.

A separately hosted deployment changes the trust boundary: uploads travel to the chosen server, whose operator controls authentication, logs, retention, backups, and jurisdiction. Remove names, email addresses, phone numbers, postal addresses, free text, and unnecessary identifiers before upload. Read [PRIVACY.md](PRIVACY.md) and [SECURITY.md](SECURITY.md).

## No install? Give this file to an AI

[AI_ANALYST.md](AI_ANALYST.md) is a single copy-paste file that turns a capable AI assistant (Claude, ChatGPT, Gemini, …) into this analysis. Copy the file into a chat, add your data, and the AI follows the same published methods, scope limits, and honesty rules as the app. The local app is the more private option: local mode keeps your data on your computer, while a cloud AI sees whatever you upload or paste.

## Development

```bash
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m build
```

The analysis core (`positionsignal`) installs without Streamlit or Plotly; the app needs the `ui` extra (`python -m pip install -e ".[ui]"`), and `requirements.txt` lists everything for the launchers and Docker. [Signal Hub](https://github.com/UlrikErlingsen/signal-hub) embeds the app through `positionsignal.ui.render()`.

The test suite checks weighted and unweighted aggregation, missing-data behavior, PCA covariance/eigenvalues, affine and row-order invariance, distance preservation, deterministic bootstrap alignment, wave/segment and POP/POD comparisons, deterministic examples, export safety, JSON/Excel/CSV round trips, every Streamlit page, the shared Signal shell, and the Signal Hub contract (no Streamlit or Plotly import outside `ui/`, `render()` without a page config, namespaced keys). See [CONTRIBUTING.md](CONTRIBUTING.md) before changing statistical behavior.

## Where this fits in Signal

Position Signal asks how brands are perceived relative to competitors on a chosen set of attributes. The Signal apps share a visual language but answer different questions:

- **[Worth Signal](https://github.com/UlrikErlingsen/customer-value-analytics)** asks what customers and customer relationships are worth: targeting, CLV, retention, customer equity, and marketing ROI.
- **[Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation)** asks whether customers form stable, useful groups and profiles those groups.
- **[Choice Signal](https://github.com/UlrikErlingsen/conjoint-analysis)** asks how product attributes drive choice: conjoint part-worth utilities, attribute importance, and preference-share simulation.
- **[Adopt Signal](https://github.com/UlrikErlingsen/adoption-forecasting)** asks when a new product gets adopted: Bass diffusion forecasting from published analogies or real history.
- **[Driver Signal](https://github.com/UlrikErlingsen/survey-driver-analysis)** asks which measured experiences move with satisfaction or recommendation scores.
- **[Alloc Signal](https://github.com/UlrikErlingsen/marketing-mix-allocation)** asks where the next marketing budget should go, given response assumptions and constraints.
- **[Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate)** asks whether a concept should receive the next bounded investment: gates, evidence, scenario economics, and risk triage.
- **[Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis)** asks whether a randomized treatment caused a change worth acting on.
- **[Measure Signal](https://github.com/UlrikErlingsen/measurement-validation)** asks whether a multi-item score measures what you think it does.
- **[Text Signal](https://github.com/UlrikErlingsen/open-text-analysis)** asks what recurring language patterns appear in open-ended responses.
- **[Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis)** asks what price range is supported and how contribution moves, from assigned-price, historical, or willingness-to-pay evidence.
- **[Recommend Signal](https://github.com/UlrikErlingsen/recommender-evaluation)** asks which recommendation policy survives honest temporal replay.
- **[Trace Signal](https://github.com/UlrikErlingsen/journey-path-analysis)** asks how logged customer journeys actually unfold: transitions, path support, drop-off, and Markov removal sensitivity, with no causal channel credit.
- **[Track Signal](https://github.com/UlrikErlingsen/brand-tracking)** asks whether brand measures moved across tracking waves, with intervals, multiple-comparison control, and declared practical thresholds.
- **Position Signal** asks how brands are perceived relative to competitors on a chosen set of attributes.

Perception is not preference. A brand can occupy a distinctive Position Signal location without winning Choice Signal simulations, and a valuable customer group in Worth Signal or Segment Signal does not automatically perceive the market in the same way.

<!-- signal-suite:start (generated from signal-hub/apps.yaml by scripts/sync_readme_suite.py) -->
| Family | App | Asks |
|---|---|---|
| Brand | [Track Signal](https://github.com/UlrikErlingsen/brand-tracking) | Is the brand moving, or is the tracker just noisy? |
| Brand | **Position Signal** (this app) | Where do brands sit relative to competitors? |
| Market | [Prospect Signal](https://github.com/UlrikErlingsen/b2b-prospecting) | Which Norwegian companies fit your ideal customer, and which first? |
| Market | [Listen Signal](https://github.com/UlrikErlingsen/media-listening) | Who is talking about the brand in Norwegian media, and in what tone? |
| Market | [Influence Signal](https://github.com/UlrikErlingsen/influencer-campaigns) | Which creators delivered, and was every post labelled properly? |
| Market | [Season Signal](https://github.com/UlrikErlingsen/marketing-calendar) | What does the Norwegian marketing year look like, worked backwards? |
| Market | [Adopt Signal](https://github.com/UlrikErlingsen/adoption-forecasting) | When will a new product be adopted? |
| Customer | [Worth Signal](https://github.com/UlrikErlingsen/customer-value-analytics) | What are customers and relationships worth? |
| Customer | [Segment Signal](https://github.com/UlrikErlingsen/customer-segmentation) | Do customers form stable, useful groups? |
| Customer | [Trace Signal](https://github.com/UlrikErlingsen/journey-path-analysis) | How do logged customer journeys actually unfold? |
| Customer | [Recommend Signal](https://github.com/UlrikErlingsen/recommender-evaluation) | Which recommendation policy should be tested live? |
| Research | [Choice Signal](https://github.com/UlrikErlingsen/conjoint-analysis) | How do product attributes drive choice? |
| Research | [Driver Signal](https://github.com/UlrikErlingsen/survey-driver-analysis) | Which measured experiences move with satisfaction? |
| Research | [Measure Signal](https://github.com/UlrikErlingsen/measurement-validation) | Does a multi-item score have a defensible structure? |
| Research | [Text Signal](https://github.com/UlrikErlingsen/open-text-analysis) | What recurring patterns appear in open-ended responses? |
| Research | [Tag Signal](https://github.com/UlrikErlingsen/pricing-analysis) | What price range is supported, and how does profit move? |
| Decide | [Experiment Signal](https://github.com/UlrikErlingsen/experiment-analysis) | Did the treatment cause a practically meaningful change? |
| Decide | [Gate Signal](https://github.com/UlrikErlingsen/launch-decision-gate) | Does a concept deserve the next investment? |
| Decide | [Shift Signal](https://github.com/UlrikErlingsen/cannibalization-analysis) | Does a launch grow the portfolio, or move existing demand around? |
| Decide | [Alloc Signal](https://github.com/UlrikErlingsen/marketing-mix-allocation) | Where should the next marketing budget go? |

All 20 apps run side by side in [Signal Hub](https://github.com/UlrikErlingsen/signal-hub), each opening with fictional demo data. Every repo carries the [`signal-suite`](https://github.com/topics/signal-suite) topic, and the suite is listed at [ulrikerlingsen.com](https://ulrikerlingsen.com). Freddo CRM is a separate product.
<!-- signal-suite:end -->

## References

- Gabriel, K. R. (1971). [The biplot graphic display of matrices with application to principal component analysis](https://doi.org/10.1093/biomet/58.3.453). *Biometrika, 58*(3), 453–467.
- Jolliffe, I. T., & Cadima, J. (2016). [Principal component analysis: a review and recent developments](https://doi.org/10.1098/rsta.2015.0202). *Philosophical Transactions of the Royal Society A, 374*, 20150202.
- Schönemann, P. H. (1966). [A generalized solution of the orthogonal Procrustes problem](https://doi.org/10.1007/BF02289451). *Psychometrika, 31*, 1–10.
- Josse, J., Wager, S., & Husson, F. (2016). [Confidence areas for fixed-effects PCA](https://doi.org/10.1080/10618600.2014.950871). *Journal of Computational and Graphical Statistics, 25*(1), 28–48.

If Position Signal supports research or teaching, cite the software metadata in [CITATION.cff](CITATION.cff) and the original method sources relevant to the analysis.

## Originality and license

Position Signal is an independent implementation based on public statistical literature and original synthetic examples. All bundled data are fictional and generated by code ([`scripts/generate_examples.py`](scripts/generate_examples.py)).

Position Signal is free software under **AGPL-3.0-or-later**. Commercial use is allowed; distribution and modified network services carry the source-sharing obligations in [LICENSE](LICENSE). The license covers this project's code and documentation, not ownership of the published statistical methods it implements.

This application was developed with AI coding assistance and checked through source review and automated tests. Verify important results independently; no warranty is provided.

---

<p>
  <img src="assets/positionsignal-mark-64.png" width="20" height="20" alt="" align="absmiddle">
  <strong>Position Signal</strong> is part of <a href="https://github.com/UlrikErlingsen/signal-hub"><strong>Signal</strong></a>, open marketing-evidence tools by <a href="https://ulrikerlingsen.com">Ulrik Erlingsen</a>.
</p>
