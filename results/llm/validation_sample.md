# LLM feature validation (sample)

Score strangeness-v1; high strangeness = score >= 3 of 7. The extractor saw only the report text (NUFORC notes removed) and duration, never the date or place.

| Group | Reports | Mean strangeness | High strangeness | Expected cause named top | Mean likelihood of expected cause |
| --- | --- | --- | --- | --- | --- |
| launch window | 46 | 0.54 | 0% | 4% | 0.09 |
| Starlink train | 41 | 0.20 | 0% | 88% | 0.68 |
| NUFORC-identified | 70 | 0.27 | 0% | — | — |
| meteor rule | 41 | 0.29 | 0% | 90% | 0.68 |
| bright planet up | 41 | 1.00 | 0% | 44% | 0.32 |
| lantern wording | 110 | 0.43 | 1% | 29% | 0.23 |
| holiday night | 47 | 0.45 | 2% | — | — |
| residual (no match) | 120 | 0.53 | 1% | — | — |

Most likely ordinary cause named for residual reports: aircraft 39%, meteor 13%, planet_or_star 12%, drone 8%, sky_lantern 7%, starlink_train 5%, other_known 4%, balloon 3%.

Reading: known-cause groups should score clearly lower than the residual and be matched to their cause. If launch-window reports score as strange as the residual, the score measures dramatic description, not anomaly.
