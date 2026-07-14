# Changelog

All notable changes to PositionSignal are documented here. The project follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
