# Contributing to PositionSignal

Contributions that make PositionSignal clearer, safer, statistically sounder, or easier for marketers are welcome.

## Development setup

Python 3.10 or newer is required. From the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[test]"
python -m pytest
python -m ruff check .
python -m streamlit run app.py
```

## Project structure

```text
app.py                    Streamlit workflow and presentation
src/positionsignal/       Typed data, mapping, plotting, and export logic
tests/                    Statistical, validation, bootstrap, and I/O tests
docs/                     Data contract and method documentation
examples/                 Synthetic demos and starter templates
```

The split is deliberate. Computation under `src/positionsignal/` must remain importable without Streamlit, session state, or UI side effects.

## Method and data rules

- Preserve the distinction between one-row-per-brand profiles and one-row-per-respondent-brand ratings.
- Fit positioning axes to aggregated brand profiles, not individual rating noise.
- Never silently impute an empty brand-attribute cell.
- Keep brand scores, attribute coefficients, correlation loadings, and display-scaled coordinates conceptually and programmatically distinct.
- Do not stretch PC1 and PC2 independently in the biplot.
- Preserve deterministic component orientation and row-order invariance.
- Rank closest competitors in the complete prepared profile space, not only on the picture.
- Bootstrap respondent IDs as clusters; never resample respondent-brand rows independently.
- Treat diagnostics and heuristic warnings as evidence, not pass/fail truth.
- Add an independently derived or synthetic reference test for every statistical behavior change.
- Update `docs/methods.md` and cite primary literature when changing a method or convention.

## Product and safety rules

- Use plain-language labels and explain technical terms at first use.
- Keep expert diagnostics available without making them prerequisites for the normal workflow.
- Do not claim that whitespace proves demand, differentiation, profitability, or causality.
- Keep spreadsheet-formula neutralization and source/audit metadata intact across exports.
- Never add telemetry, external AI calls, or persistent upload storage without an explicit public design discussion.
- Use only synthetic, public, or properly anonymized data in tests, examples, issues, and screenshots.

## Pull requests

Keep pull requests focused. Explain the user problem, methodological effect, validation, new assumptions or limitations, and any visible UI change. Run the full test and lint commands before requesting review. Security and privacy concerns belong in the private channels described in [SECURITY.md](SECURITY.md), never in a public issue with real data.
