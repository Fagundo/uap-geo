# Robustness assessment (v1)

The observer findings are robust. The river finding is unsettled, and its biggest weakness is
report coverage, not the model.

## Threats, by severity

| Area | Issue | Severity | Fix |
| --- | --- | --- | --- |
| Data | Report extract incomplete: 70,419 reports for 2001–2020 vs 98,724 in the paper; 4,376 for 2021–2023 | High | Fresh NUFORC scrape through 2026; compare per-year counts |
| Data | One self-reported source | High | Second source (MUFON); government cases (AARO, PURSUE) as a qualitative check |
| Inference | ~19 hypotheses tested in sequence; county p-values unadjusted | High | Models A–F are exploratory; confirmation = model R on held-out data, model fixed beforehand |
| Model | Residual spatial clustering (Moran's I 0.06–0.08) | Medium | BYM2 spatial model |
| Model | Offset assumes reports scale 1:1 with population | Medium | Estimate the elasticity (log population as a covariate) |
| Model | County grain only (MAUP) | Medium | Repeat model R on an equal-area grid (H3 resolution 5) |
| Model | 20 years pooled | Medium | County × period panel |
| Measurement | Natural Earth rivers = major rivers only | Medium | NHDPlus HR by stream order |
| Measurement | Covariates from one point in time (light 2015, population 2020, gamma 1970s–80s) | Medium | Decennial population 2000/2010/2020; annual VIIRS lights |
| Measurement | Town population only for incorporated places | Medium | CDP populations from the decennial census |
| Inference | Shifted layers partly land offshore | Low–medium | Accept only shifts keeping ≥ 90% of the layer inside the US |
| Inference | Holdout reuses the same counties | Low–medium | Spatial block cross-validation |
| Engineering | No lockfile; CI uses the latest uv | Medium | Commit `uv.lock`; pin uv and Python |
| Engineering | Upstream data change silently (NID, Census vintages, plant list) | Medium | Per-run data manifest: URL, retrieval date, SHA-256 |
| Engineering | GIS code tested only by full runs | Medium | Synthetic-data integration test in CI |
| Engineering | Results live in logs and expiring artifacts | Low | Commit each run's summary to `results/` |

## Already in place

Replication of the published baseline; same-sample model comparison; state fixed effects; layer-shift
tests with Benjamini–Hochberg adjustment; within-county town test with two size controls; VIF check;
robust negative binomial fitting (Poisson warm start, optimizer fallbacks); a pre-specified
confirmatory model; fixed random seeds; inputs passed to CI through environment variables.

## Power note

The 2021–2023 holdout had a 36% chance of detecting a river effect of the size seen in 2001–2020
(log rate ratio 0.042, holdout SE 0.026). Roughly 13,400 holdout reports are needed for 80% power.
