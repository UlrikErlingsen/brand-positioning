# Contributing to Position Signal

Contributions that make Position Signal clearer, safer, statistically sounder, or easier for marketers are welcome.

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
app.py                    Thin standalone entry point (page config, then render())
src/positionsignal/       Typed data, mapping, comparison, and export logic (no Streamlit or Plotly)
src/positionsignal/ui/    Streamlit workflow, Plotly views, the synced Signal theme, packaged demos
tests/                    Statistical, validation, bootstrap, I/O, app, and Signal Hub contract tests
docs/                     Data contract and method documentation
examples/                 Synthetic demos and starter templates
```

The split is deliberate. Computation under `src/positionsignal/` must remain importable without Streamlit, Plotly, session state, or UI side effects; only `src/positionsignal/ui/` may import them, and a test enforces it. `ui.render()` never calls `st.set_page_config` or `st.navigation`, and every session-state and widget key goes through `k()` (`"position:..."`) so the app can share a [Signal Hub](https://github.com/UlrikErlingsen/signal-hub) session. `src/positionsignal/ui/signal_theme.py` and `ui/assets/marks/` are synced from Signal Hub; change them there, not here. After changing the generator, run `python scripts/generate_examples.py` so the packaged demo copies stay identical to `examples/`.

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
