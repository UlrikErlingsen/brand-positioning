# Changelog

All notable changes to Position Signal are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
