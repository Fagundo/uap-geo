# LLM feature validation (full, features-v2)

Score strangeness-v1; high strangeness = score >= 3 of 7. The extractor saw only the report text (NUFORC notes removed) and duration, never the date or place.

| Group | Reports | Mean strangeness | High strangeness | Expected cause named top | Mean likelihood of expected cause |
| --- | --- | --- | --- | --- | --- |
| launch window | 684 | 0.51 | 2% | 27% | 0.21 |
| Starlink train | 242 | 0.21 | 0% | 88% | 0.69 |
| NUFORC-identified | 2,271 | 0.35 | 1% | — | — |
| meteor rule | 1,461 | 0.25 | 1% | 93% | 0.66 |
| bright planet up | 1,201 | 0.76 | 5% | 46% | 0.33 |
| lantern wording | 20,044 | 0.47 | 2% | 42% | 0.28 |
| holiday night | 3,144 | 0.49 | 2% | — | — |
| residual (no match) | 47,661 | 0.70 | 4% | — | — |

Most likely ordinary cause named for residual reports: aircraft 41%, planet_or_star 12%, drone 11%, meteor 10%, balloon 7%, other_known 4%, satellite 4%, sky_lantern 3%.

Reading: known-cause groups should score clearly lower than the residual and be matched to their cause. If launch-window reports score as strange as the residual, the score measures dramatic description, not anomaly.
