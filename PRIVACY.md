# PositionSignal privacy notes

PositionSignal is designed to run locally. It includes no user accounts, advertising, product analytics, telemetry, external AI calls, or built-in research-data database.

## When you run it on your computer

- Uploaded files are read into the Streamlit process running on that computer.
- Analysis happens in memory; PositionSignal does not intentionally send uploaded ratings to the project maintainer or a third-party API.
- The source file is never modified.
- Excel, CSV ZIP, JSON, and HTML exports are created only when you request them.
- Closing the process clears the in-memory session. The app itself does not persist the upload.

The launchers may contact Python package indexes on first use to install open-source dependencies. That installation traffic does not include uploaded research data.

## Data minimization

PositionSignal does not need names, email addresses, telephone numbers, postal addresses, customer account IDs, or open-text responses. If respondent-level uncertainty is required, use a pseudonymous study key that cannot identify a person on its own. Remove direct identifiers and unnecessary columns before upload; automated identifier warnings are incomplete.

Optional survey weights and rating records may still be confidential or personal data depending on the study. Apply the study's consent, access, retention, and deletion rules.

## Exports

Exports contain aggregated brand profiles, coordinates, diagnostics, labels, settings, a source fingerprint, and—in bootstrap runs—aligned coordinate samples. The standalone HTML map embeds its chart data and the Plotly viewer. Treat every export as potentially sensitive market-research material even when it contains no direct identifiers.

## When someone hosts it

A hosted deployment changes the trust boundary: uploaded files travel to and are processed by the selected server. The deployment operator—not this source tree—controls and is responsible for:

- authentication and authorization;
- TLS and network controls;
- infrastructure and application logs;
- backups, retention, deletion, and incident response;
- hosting jurisdiction; and
- privacy notices, consent, contracts, and applicable law.

The PositionSignal code does not add persistent upload storage, but a host or its surrounding infrastructure may. Do not upload confidential, personal, or regulated data until the operator has documented those controls.

## Reporting a privacy or security concern

Email [code.modular578@passmail.net](mailto:code.modular578@passmail.net) with the subject `[PositionSignal privacy]`. If private vulnerability reporting is enabled at the planned GitHub repository, its [private security advisory form](https://github.com/UlrikErlingsen/brand-positioning/security/advisories/new) is also suitable. Never put sensitive data or an exploitable report in a public issue.
