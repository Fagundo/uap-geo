# H-persist-01 report card: Persistent county hotspots

**Split:** confirm (2011–2020)  
**Run:** H-persist-01-confirm-20261111T131252Z  
**Code:** `c6c6b7fe5459`  
**Spec / impl / filters SHA-256:** `7947b086955f` / `5c15a169c5c1` / `8b2d4002b6f7`

## Question

Counties that report more UAP events than expected in one period, after observer controls, keep reporting more than expected in the next period, once nights with known time-specific causes (holidays, rocket launches) are removed.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Prior-period county excess predicts the next period (per SD) | **confirmed** | 1.192 (1.151–1.235) | < 0.001 | 100% |

## Prior-period county excess predicts the next period (per SD)

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.195 | 1.154–1.238 | < 0.001 | 3,100 | 38,555 |
| Filtered (explainable removed) | 1.192 | 1.151–1.235 | < 0.001 | 3,100 | 36,684 |
| High quality | 1.125 | 1.090–1.162 | < 0.001 | 3,100 | 17,541 |

**Discriminating checks (primary tier)**

- Holds with the county's prior rate of explained reports as a control: **holds** (rate ratio 1.178, p < 0.001)
- Holds with the neighbouring counties' prior excess as a control: **holds** (rate ratio 1.189, p < 0.001)

## Periods and removals

Prior period 2001–2010; outcome period 2011–2020. Holiday nights (07-03, 07-04, 07-05, 12-31, 01-01) and twilight/night launch nights within 1,200 km are removed from counts and from each county's nights.

| Version | Persistence rate ratio per SD | 95% CI | p |
| --- | --- | --- | --- |
| with removals (primary) | 1.192 | 1.151–1.235 | 3.31e-22 |
| no removals | 1.192 | 1.152–1.234 | 2.87e-23 |
| + prior explained-report rate | 1.178 | 1.138–1.220 | 3.37e-20 |
| + neighbours' prior excess | 1.189 | 1.148–1.231 | 4.63e-22 |
| (prior explained-report rate itself) | 1.027 | 1.012–1.043 | 0.000403 |
| (neighbours' prior excess itself) | 1.042 | 1.014–1.071 | 0.00329 |

## Counties with the largest combined excess (both periods, primary tier, removals applied)

Shrunken excess over the observer-controlled expectation; a descriptive watch list, not a test.

| Rank | County | State FIPS | Events (both periods) | Excess |
| --- | --- | --- | --- | --- |
| 1 | Dare | 37 | 58 | 4.22× |
| 2 | Horry | 45 | 309 | 4.02× |
| 3 | Fredericksburg | 51 | 38 | 3.01× |
| 4 | Fairfax | 51 | 20 | 2.98× |
| 5 | Monroe | 12 | 58 | 2.61× |
| 6 | Brunswick | 37 | 87 | 2.49× |
| 7 | New York | 36 | 426 | 2.40× |
| 8 | La Paz | 04 | 28 | 2.35× |
| 9 | Charlottesville | 51 | 27 | 2.35× |
| 10 | Klickitat | 53 | 30 | 2.32× |
| 11 | Harrison | 28 | 51 | 2.26× |
| 12 | Falls Church | 51 | 13 | 2.22× |
| 13 | Lincoln | 41 | 60 | 2.11× |
| 14 | Columbia | 55 | 30 | 2.09× |
| 15 | Worcester | 24 | 44 | 2.08× |
| 16 | La Salle | 48 | 8 | 2.08× |
| 17 | Bates | 29 | 12 | 2.05× |
| 18 | Roosevelt | 30 | 13 | 2.02× |
| 19 | Thomas | 20 | 9 | 2.00× |
| 20 | Virginia Beach | 51 | 114 | 1.99× |
| 21 | Johnson | 05 | 14 | 1.96× |
| 22 | Henry | 29 | 13 | 1.96× |
| 23 | Cape May | 34 | 58 | 1.95× |
| 24 | Cabell | 54 | 41 | 1.94× |
| 25 | Sarasota | 12 | 172 | 1.94× |

## Launch-site counties, rank among all counties by combined excess

| Pad county | Rank with removals | Rank without |
| --- | --- | --- |
| Cape Canaveral: Brevard | 72 | 70 |
| Vandenberg: Santa Barbara | 778 | 816 |

## Data

- Reports 2006–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
