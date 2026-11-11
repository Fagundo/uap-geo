# LLM feature validation (sample2, features-v2)

Score strangeness-v1; high strangeness = score >= 3 of 7. The extractor saw only the report text (NUFORC notes removed) and duration, never the date or place.

| Group | Reports | Mean strangeness | High strangeness | Expected cause named top | Mean likelihood of expected cause |
| --- | --- | --- | --- | --- | --- |
| launch window | 43 | 0.42 | 0% | 30% | 0.22 |
| Starlink train | 41 | 0.22 | 0% | 78% | 0.64 |
| NUFORC-identified | 73 | 0.33 | 0% | — | — |
| meteor rule | 42 | 0.19 | 0% | 98% | 0.68 |
| bright planet up | 47 | 0.94 | 13% | 60% | 0.37 |
| lantern wording | 116 | 0.41 | 3% | 28% | 0.23 |
| holiday night | 46 | 0.37 | 0% | — | — |
| residual (no match) | 120 | 0.82 | 4% | — | — |

Most likely ordinary cause named for residual reports: aircraft 43%, drone 10%, planet_or_star 9%, balloon 8%, satellite 8%, meteor 7%, rocket_launch 4%, other_known 4%.

Reading: known-cause groups should score clearly lower than the residual and be matched to their cause. If launch-window reports score as strange as the residual, the score measures dramatic description, not anomaly.
