# H-persist-01 report card: Persistent county hotspots

**Split:** explore (2006–2010)  
**Run:** H-persist-01-explore-20261111T130357Z  
**Code:** `0a36aee2445d`  
**Spec / impl / filters SHA-256:** `ec9683a0472e` / `5c15a169c5c1` / `8b2d4002b6f7`

## Question

Counties that report more UAP events than expected in one period, after observer controls, keep reporting more than expected in the next period, once nights with known time-specific causes (holidays, rocket launches) are removed.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Prior-period county excess predicts the next period (per SD) | **exploration (no verdict)** | 1.147 (1.111–1.185) | < 0.001 | 100% |

## Prior-period county excess predicts the next period (per SD)

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.157 | 1.120–1.197 | < 0.001 | 3,100 | 12,777 |
| Filtered (explainable removed) | 1.147 | 1.111–1.185 | < 0.001 | 3,100 | 11,990 |
| High quality | 1.137 | 1.094–1.181 | < 0.001 | 3,100 | 5,261 |

**Discriminating checks (primary tier)**

- Holds with the county's prior rate of explained reports as a control: **holds** (rate ratio 1.133, p < 0.001)
- Holds with the neighbouring counties' prior excess as a control: **holds** (rate ratio 1.147, p < 0.001)

## Periods and removals

Prior period 2001–2005; outcome period 2006–2010. Holiday nights (07-03, 07-04, 07-05, 12-31, 01-01) and twilight/night launch nights within 1,200 km are removed from counts and from each county's nights.

| Version | Persistence rate ratio per SD | 95% CI | p |
| --- | --- | --- | --- |
| with removals (primary) | 1.147 | 1.111–1.185 | 1.1e-16 |
| no removals | 1.149 | 1.114–1.186 | 5.6e-18 |
| + prior explained-report rate | 1.133 | 1.100–1.167 | 1.4e-16 |
| + neighbours' prior excess | 1.147 | 1.109–1.187 | 1.21e-15 |
| (prior explained-report rate itself) | 1.036 | 1.013–1.059 | 0.00185 |
| (neighbours' prior excess itself) | 1.019 | 0.990–1.049 | 0.205 |

## Counties with the largest combined excess (both periods, primary tier, removals applied)

Shrunken excess over the observer-controlled expectation; a descriptive watch list, not a test.

| Rank | County | State FIPS | Events (both periods) | Excess |
| --- | --- | --- | --- | --- |
| 1 | New York | 36 | 210 | 3.26× |
| 2 | Horry | 45 | 85 | 3.08× |
| 3 | Klickitat | 53 | 17 | 2.25× |
| 4 | Bates | 29 | 10 | 2.12× |
| 5 | Boone | 29 | 40 | 2.11× |
| 6 | Curry | 41 | 14 | 2.06× |
| 7 | La Paz | 04 | 13 | 2.01× |
| 8 | New Hanover | 37 | 35 | 2.01× |
| 9 | Clinton | 18 | 11 | 1.99× |
| 10 | Taylor | 48 | 22 | 1.98× |
| 11 | Amherst | 51 | 10 | 1.98× |
| 12 | Scioto | 39 | 15 | 1.93× |
| 13 | Columbia | 55 | 13 | 1.91× |
| 14 | Cabell | 54 | 18 | 1.89× |
| 15 | Henry | 29 | 9 | 1.89× |
| 16 | Dare | 37 | 12 | 1.88× |
| 17 | Calcasieu | 22 | 23 | 1.88× |
| 18 | Allegany | 24 | 14 | 1.86× |
| 19 | Monroe | 12 | 19 | 1.85× |
| 20 | Howard | 18 | 16 | 1.83× |
| 21 | Sullivan | 47 | 22 | 1.81× |
| 22 | Charlottesville | 51 | 10 | 1.79× |
| 23 | Phelps | 29 | 12 | 1.77× |
| 24 | Richmond | 51 | 31 | 1.77× |
| 25 | Wapello | 19 | 9 | 1.77× |

## Launch-site counties, rank among all counties by combined excess

| Pad county | Rank with removals | Rank without |
| --- | --- | --- |
| Cape Canaveral: Brevard | 80 | 112 |
| Vandenberg: Santa Barbara | 458 | 397 |

## Data

- Reports 2006–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
