# H-geo-01 diagnostics, confirm split (2011–2020)

**Post-hoc and exploratory.** Nothing here changes a registered verdict. Patterns found here can only seed new hypotheses, tested on data not yet used. Tier: filtered.

## Storms

Observed events on storm nights against expected from the same storm's matched nights (nights x mean per control night).

### Strongest storms (max Kp >= 7)

| Storm start | Max Kp | Obs | Exp | O/E | North O/E | South O/E | Aurora-mention events obs / exp |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2017-09-07 | 8.33 | 31 | 26.2 | 1.18 | 1.32 | 0.87 | 0 / 0.0 |
| 2015-06-22 | 8.33 | 35 | 26.7 | 1.31 | 1.58 | 0.92 | 0 / 0.0 |
| 2012-03-09 | 8.00 | 23 | 19.5 | 1.18 | 0.96 | 1.59 | 0 / 0.0 |
| 2015-03-17 | 7.67 | 29 | 23.3 | 1.24 | 1.55 | 0.71 | 0 / 0.3 |
| 2013-10-02 | 7.67 | 29 | 31.4 | 0.92 | 1.17 | 0.51 | 0 / 0.0 |
| 2011-08-05 | 7.67 | 35 | 43.6 | 0.80 | 0.75 | 0.90 | 0 / 0.0 |
| 2018-08-26 | 7.33 | 9 | 12.5 | 0.72 | 0.88 | 0.44 | 0 / 0.0 |
| 2015-10-07 | 7.33 | 29 | 27.1 | 1.07 | 1.03 | 1.14 | 0 / 0.0 |
| 2011-10-24 | 7.33 | 27 | 30.8 | 0.88 | 0.84 | 0.94 | 0 / 0.1 |
| 2012-07-15 | 7.00 | 33 | 50.1 | 0.66 | 0.61 | 0.80 | 0 / 0.0 |
| 2013-06-01 | 7.00 | 34 | 37.1 | 0.92 | 0.97 | 0.81 | 0 / 0.0 |
| 2015-09-11 | 7.00 | 39 | 34.8 | 1.12 | 1.27 | 0.83 | 0 / 0.0 |
| 2015-09-20 | 7.00 | 24 | 29.3 | 0.82 | 0.78 | 0.92 | 0 / 0.0 |
| 2017-05-28 | 7.00 | 20 | 17.2 | 1.16 | 1.49 | 0.62 | 0 / 0.0 |

### By storm strength

| Max Kp | Storms | Obs | Exp | O/E | North O/E | South O/E |
| --- | --- | --- | --- | --- | --- | --- |
| 6–7 | 43 | 1047 | 1015.8 | 1.03 | 1.03 | 1.02 |
| 7–8 | 11 | 308 | 337.4 | 0.91 | 0.97 | 0.81 |
| 8–10 | 3 | 89 | 72.4 | 1.23 | 1.31 | 1.08 |

Aurora-mention events on all storm nights: 2 observed vs 0.7 expected.

### Kp >= 8 storms only (conditional Poisson)

| Subset | Rate ratio | p | Events |
| --- | --- | --- | --- |
| north of 37N | 1.37 | 0.029 | 404 |
| south of 37N | 1.08 | 0.707 | 219 |
| all Kp >= 8 storms | 1.26 | 0.049 | 623 |
| without storm 1313 | 1.28 | 0.068 | 454 |
| without storm 1336 | 1.21 | 0.239 | 392 |
| without storm 1356 | 1.28 | 0.089 | 400 |

## Earthquakes

Profile: filtered events in counties within the radius of 533 M >= 4 mainshocks (2153 county-quake pairs), by night relative to the quake's local observing night. Baseline is the mean over nights 15–28 before and after.

| Nights | Events per night | vs baseline |
| --- | --- | --- |
| -28 to -15 | 18.4 | 0.99 |
| -14 to -8 | 22.4 | 1.21 |
| -7 to -1 | 23.3 | 1.25 |
| +0 (quake night) | 11.0 | 0.59 |
| +1 to +3 | 20.0 | 1.07 |
| +4 to +14 | 19.1 | 1.03 |
| +15 to +28 | 18.9 | 1.01 |

### Alternative windows and subsets (conditional Poisson, matched controls)

| Variant | Rate ratio | 95% CI | p | Events | Power for 1.10 |
| --- | --- | --- | --- | --- | --- |
| registered: nights -14..0, UTC date | 1.14 | 0.98–1.33 | 0.091 | 899 | 25% |
| nights -14..0, local night | 1.13 | 0.97–1.32 | 0.116 | 893 | 25% |
| nights -14..-1 (quake night excluded), local | 1.19 | 1.02–1.39 | 0.028 | 877 | 24% |
| nights -7..-1, local | 1.31 | 1.07–1.60 | 0.008 | 502 | 15% |
| nights 0..+3 (after the quake), local | 0.92 | 0.70–1.21 | 0.546 | 303 | 11% |
| within 50 km, -14..-1, local | 1.21 | 0.94–1.57 | 0.142 | 315 | 11% |
| M >= 3.5, -14..-1, local | 1.09 | 0.99–1.19 | 0.080 | 2421 | 56% |
| Oklahoma + Kansas (mostly induced), registered window | 1.91 | 0.91–4.03 | 0.088 | 60 | 7% |
| California + Nevada, registered window | 1.18 | 0.99–1.41 | 0.066 | 618 | 19% |
| all other states, registered window | 0.96 | 0.69–1.33 | 0.807 | 221 | 9% |

