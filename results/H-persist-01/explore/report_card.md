# H-persist-01 report card: Persistent county hotspots

**Split:** explore (2006–2010)  
**Run:** H-persist-01-explore-20261111T123954Z  
**Code:** `add562b00966`  
**Spec / impl / filters SHA-256:** `66b435d6d475` / `d42c1f8d5cf7` / `8b2d4002b6f7`

## Question

Counties that report more UAP events than expected in one period, after observer controls, keep reporting more than expected in the next period, once nights with known time-specific causes (holidays, rocket launches) are removed.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Prior-period county excess predicts the next period (per SD) | **exploration (no verdict)** | 1.174 (1.138–1.211) | < 0.001 | 100% |

## Prior-period county excess predicts the next period (per SD)

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.183 | 1.145–1.221 | < 0.001 | 3,100 | 12,777 |
| Filtered (explainable removed) | 1.174 | 1.138–1.211 | < 0.001 | 3,100 | 11,990 |
| High quality | 1.160 | 1.117–1.204 | < 0.001 | 3,100 | 5,261 |

**Discriminating checks (primary tier)**

- Holds with the county's prior rate of explained reports as a control: **holds** (rate ratio 1.155, p < 0.001)
- Holds with the neighbouring counties' prior excess as a control: **holds** (rate ratio 1.173, p < 0.001)

## Periods and removals

Prior period 2001–2005; outcome period 2006–2010. Holiday nights (07-03, 07-04, 07-05, 12-31, 01-01) and twilight/night launch nights within 1,200 km are removed from counts and from each county's nights.

| Version | Persistence rate ratio per SD | 95% CI | p |
| --- | --- | --- | --- |
| with removals (primary) | 1.174 | 1.138–1.211 | 1.09e-23 |
| no removals | 1.177 | 1.141–1.213 | 2.23e-25 |
| + prior explained-report rate | 1.155 | 1.122–1.190 | 5.93e-22 |
| + neighbours' prior excess | 1.173 | 1.135–1.213 | 2.01e-21 |
| (prior explained-report rate itself) | 1.040 | 1.019–1.063 | 0.000257 |
| (neighbours' prior excess itself) | 1.025 | 0.994–1.057 | 0.12 |

## Counties with the largest combined excess (both periods, primary tier, removals applied)

Shrunken excess over the observer-controlled expectation; a descriptive watch list, not a test.

| Rank | County | State FIPS | Events (both periods) | Excess |
| --- | --- | --- | --- | --- |
| 1 | Horry | 45 | 85 | 3.92× |
| 2 | New York | 36 | 210 | 3.75× |
| 3 | Cape May | 34 | 19 | 2.38× |
| 4 | La Paz | 04 | 13 | 2.32× |
| 5 | Klickitat | 53 | 17 | 2.31× |
| 6 | Dare | 37 | 12 | 2.28× |
| 7 | Boone | 29 | 40 | 2.26× |
| 8 | Bates | 29 | 10 | 2.24× |
| 9 | Worcester | 24 | 13 | 2.23× |
| 10 | Curry | 41 | 14 | 2.20× |
| 11 | Monroe | 12 | 19 | 2.17× |
| 12 | New Hanover | 37 | 35 | 2.16× |
| 13 | Clinton | 18 | 11 | 2.07× |
| 14 | Amherst | 51 | 10 | 2.05× |
| 15 | Barnstable | 25 | 37 | 2.04× |
| 16 | Taylor | 48 | 22 | 2.03× |
| 17 | Cabell | 54 | 18 | 2.00× |
| 18 | Lincoln | 41 | 18 | 1.99× |
| 19 | Scioto | 39 | 15 | 1.99× |
| 20 | Charlottesville | 51 | 10 | 1.99× |
| 21 | Henry | 29 | 9 | 1.98× |
| 22 | Columbia | 55 | 13 | 1.94× |
| 23 | Allegany | 24 | 14 | 1.93× |
| 24 | Richmond | 51 | 31 | 1.93× |
| 25 | Calcasieu | 22 | 23 | 1.92× |

## Launch-site counties, rank among all counties by combined excess

| Pad county | Rank with removals | Rank without |
| --- | --- | --- |
| Cape Canaveral: Brevard | 130 | 179 |
| Vandenberg: Santa Barbara | 621 | 541 |

## Data

- Reports 2006–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
