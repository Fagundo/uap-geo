# Results (v1, November 2026)

Data: 70,419 NUFORC reports, 2001–2020, contiguous US (TidyTuesday 2023 extract), aggregated to
3,100 counties. Holdout: 4,376 reports, 2021–2023. Rate ratios are per +1 SD within states
(state fixed effects) unless noted.

## Summary

| Status | Finding |
| --- | --- |
| Robust | Fewer reports under bright skies (light pollution 0.92; holdout 0.87) |
| Robust | More reports near airports (1.07; holdout 1.12) |
| Robust | More reports in high-relief terrain (1.11; holdout 1.12) |
| Tentative | Rivers, county level: 1.04, shift p = 0.008 (1,000 shifts); holdout 1.04, p = 0.18, underpowered (36%) |
| Tentative | Town level: towns nearer the ocean coast and rail lines report more, both periods |
| Rejected | Faults, earthquakes: regional, not tied to real locations |
| Rejected | Lakes, reservoirs: null, not location-specific |
| Rejected | Nuclear plants within 50 km (0.95, p = 0.10); weapons sites within 100 km (1.00, p = 0.94) |
| Inconclusive | Gamma-ray thorium 0.89, potassium 1.07, uranium 0.96: collinear, opposite signs, not shift-tested |

## Model fit (2001–2020)

| Model | ΔAIC vs A | Residual Moran's I |
| --- | --- | --- |
| A observer | 0 | — |
| B + geology | −184 | 0.20 |
| C + state fixed effects | −802 | 0.08 |
| D + settlements, roads, rail | −810 | 0.08 |
| E + water and terrain | −840 | 0.07 |
| F + radiation | −902 | 0.06 |
| R confirmatory | −845 | 0.07 |

Most of the improvement comes from state fixed effects: much of what looked like geology in model B is regional.

## Rivers in detail

- County level, 2001–2020: 1.043 (95% CI 1.019–1.067). Real river network beats 99.2% of 1,000 shifted copies.
- County level, 2021–2023: 1.036 (0.984–1.091). Same size; the two periods do not differ (z = 0.23).
  About 13,400 holdout reports would give 80% power.
- Town level, sized by population: no river effect in either period (odds ratio 0.98 and 1.00).
  The earlier town-level river effect came from sizing towns by land area.
- Reading: river-rich counties report more, but river towns within them do not, which fits a
  landscape or reporting-culture difference better than a local physical effect.

## Replication of Medina et al. (2023)

Light pollution −7% per SD (paper −7.7%), airports +9.4% (paper +9.9%), military area weak, cloud
cover unstable. Hotspots in the West and far Northeast, cold spots in the plains and Southeast.
