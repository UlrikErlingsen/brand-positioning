# Changelog

All notable changes to Position Signal are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [1.3.0] - 2026-10-03

Larger datasets: run locally, Position Signal has no built-in data limits, and the slow steps were rewritten so millions of rating rows stay workable. The statistics, data contract and export contents are unchanged; the same data and seed give the same maps and ellipses.

### Larger datasets

- No built-in limit on file size, rows, cells, brands or attributes when the app runs on your own computer (standalone, local Signal Hub, internal deployment). The old caps (100 MB uploads, 30 MB JSON, 250 MB expanded workbooks, 500,000 rows, 8,000,000 cells, 60 brands, 40 attributes) are gone locally; a running-out-of-memory error becomes a plain message instead of a crash.
- Public demo limits: with `SIGNAL_PUBLIC=1` (Signal Hub's public image) the app caps uploads at 50 MB (30 MB JSON, 250 MB expanded workbooks), 500,000 rows, 8,000,000 cells, 60 brands, 40 attributes and 500 bootstrap iterations. All caps live in the new `positionsignal.limits`, and each message says it is a demo limit that the downloaded app does not have.
- Streamlit's upload cap is 10,000 MB: `.streamlit/config.toml`, `run_app.bat` and `run_app.command` (`POSITIONSIGNAL_MAX_UPLOAD_MB`, default 10000; the Windows launcher now reads it too), and the Dockerfile (`STREAMLIT_SERVER_MAX_UPLOAD_SIZE=10000`).
- CSV files are parsed by pandas' C reader in chunks (the delimiter is still detected from the header line) instead of the slow Python engine; text columns are stored as categories and whole-number columns as the smallest integer type. JSON record lists are parsed record by record into compact columns.
- Brand profiles (weighted and unweighted), wave and segment comparisons, and the column audit use grouped, vectorized calculations; the PII check no longer converts whole columns to text, and page 1 computes its column audit once per file.
- The respondent bootstrap computes each resample as a count-weighted mean of the original rows, in batches of matrix products, instead of copying every sampled respondent's rows. It draws the same random numbers, so a seed gives the same ellipses as before, and it shows a progress bar. On 200,000 rows the old method needed about 10 s per bootstrap map; the new one runs 500 maps on 5,000,000 rows in about 30 s.
- Measured on a 5,000,000-row, 360 MB file (500,000 respondents × 10 brands, 20 attributes, survey weights): read 4.6 s, column audit 2 s, weighted profiles 3 s, comparisons 6 s, 500 bootstrap maps 29 s, about 3 GB peak memory. The 1.2 release refused the file; at its own limits it needed about 50 s to read and 40 s per page-1 rerun.
- Maps with more than about 60 brands or 40 attributes show a readability note; the data preview says it shows the first 30 rows.
- New tests: local mode accepts input beyond the demo caps (including a 520,000-row file), `SIGNAL_PUBLIC=1` enforces them, the vectorized bootstrap matches resampling copied rows, grouped comparison statistics match the per-group formula, delimiter detection, streamed JSON, and launcher/Docker upload settings.

### Suite

- Suite: Rival, Reach, Learn and Blueprint Signal added to the suite table (README and the shared theme).

## [1.2.0] - 2026-10-02

Signal brand refresh and Signal Hub entry point. The analysis, statistics, data contract and export contents are unchanged.

### Brand

- Display name written **Position Signal** (with a space) in the app, README, docs, launchers, export metadata and citation. Package, file and environment-variable names stay `positionsignal` / `POSITIONSIGNAL_*`.
- The app uses the shared `signal_theme` module (Organic Signal design, Brand family colour `#b2622d`, Figtree): sidebar lockup, masthead, hero, cards, notes, page headers, footer and the mark as favicon replace the pasted styles.
- Charts use the per-app Signal Plotly template; the old palette maps to theme tokens with the same meaning (focus brand and retained components in the family colour, other brands muted, below/above-market on the shared diverging scale).
- New banner, social preview and marks in `assets/`; the old banner SVG is removed. `.streamlit/config.toml` uses the family colours.
- README follows the Signal template; bug-report and feature-request issue templates added.
- Embedded Figtree font, no Google Fonts request: the synced theme loads Figtree from `ui/signal_font.py`, so the app makes no outbound font request. Chart colourways follow the shared per-family contrast order.

### Signal Hub contract

- `positionsignal.ui` exposes `APP_INFO` and `render()`, so Signal Hub can embed the app; `app.py` is now a thin standalone entry point.
- All session-state and widget keys are namespaced `position:` (including the page selector); **Clear data and results** clears only this app's state.
- The Plotly views moved from `positionsignal.plotting` to `positionsignal.ui.plotting`. `streamlit` and `plotly` moved to a `ui` extra (also in `test`); the analysis core installs without them. `requirements.txt` still lists everything.
- The fictional demos ship as package data, so they also load from an installed wheel.
- Opens with the fictional demo preloaded: a fresh session loads the fictional sneaker ratings, saves the suggested setup and builds the default map (standardized, no bootstrap), so every page shows results before an upload. **See the fictional market map** on the welcome page and the sidebar demo buttons restore or switch demos; an upload replaces the demo; **Clear data and results** leaves the app empty.
- New tests: no Streamlit/Plotly import outside `positionsignal.ui`, `render()` runs from a script without a page config, every widget key is namespaced, and render and demos work from a copied package outside the repository.

## [1.1.1] - 2026-07-16

### Security

- Brand and attribute names from uploaded data are now HTML-escaped before they are rendered in the interpretation summary and insight cards.
- Excel and CSV exports also neutralize formula-like column headers, the Docker image keeps application code root-owned, and defusedxml hardens workbook XML parsing.

## [1.1.0] - 2026-07-16

### Added

- Declared wave and segment comparisons with transparent independent-sample intervals and repeated-respondent warnings.
- Association-leadership reporting and focus-brand points-of-parity/points-of-difference candidate classifications.
- Configurable descriptive thresholds and privacy-minimized Excel, CSV-ZIP, and JSON comparison evidence packs.

## [1.0.1] - 2026-07-14

### Changed

- Removed the "multidimensional scaling" package keyword: the app implements PCA, not MDS.

## [1.0.0] - 2026-07-14

### Added

- Local-first Streamlit workflow for perceptual mapping from brand-attribute ratings.
- Two wide input grains: aggregated brand profiles and respondent-brand rating rows, with optional respondent-constant survey weights.
- Transparent aggregation, missing-cell policy, rating bases, effective weighted bases, and privacy-oriented data checks.
- Deterministic standardized or center-only PCA with a row-metric Gabriel biplot and separate correlation circle.
- Explained-variance, cos², contribution, eigengap, full-space distance, projected-distance, and normalized-error diagnostics.
- Optional respondent-cluster bootstrap uncertainty with orthogonal Procrustes alignment.
- Focus-brand interpretation that ranks competitors in the complete selected-attribute space.
- Excel, CSV ZIP, JSON/audit, standalone HTML, and chart-image exports.
- Fictional sneaker-rating and aggregate-profile demos, downloadable templates, method/data documentation, and automated tests.
- Signal-family branding, local launchers, non-root Docker runtime, CI, security/privacy policies, citation metadata, and AGPL-3.0-or-later licensing.
