# H-celebrate-01 report card: Celebration nights

**Split:** explore (2001–2010)  
**Run:** H-celebrate-01-explore-20261111T115138Z  
**Code:** `d85722b67992`  
**Spec / impl / filters SHA-256:** `be079322eaf1` / `1f30d2b960ea` / `8b2d4002b6f7`

## Question

Celebration nights raise UAP reports that the filters leave unexplained: reports with no lantern or fireworks wording rise on the Fourth of July and New Year's Eve in every county, and on the night of a championship win in the counties around the winner's home city, compared with the same counties on comparable nights.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Fourth of July night, every county | **exploration (no verdict)** | 3.533 (3.045–4.100) | < 0.001 | 14% |
| New Year's Eve night, every county | **exploration (no verdict)** | 2.452 (2.009–2.991) | < 0.001 | 11% |
| Championship-win night, counties near the winner's city | **exploration (no verdict)** | 0.739 (0.173–3.156) | 0.683 | 5% |

## Fourth of July night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 3.785 | 3.292–4.350 | < 0.001 | 315 | 911 |
| Filtered (explainable removed) | 3.992 | 3.463–4.602 | < 0.001 | 308 | 856 |
| Unexplained (filtered, no lantern or fireworks description) | 3.533 | 3.045–4.100 | < 0.001 | 302 | 819 |
| High quality | 4.900 | 4.022–5.971 | < 0.001 | 198 | 419 |

Moon illumination (full vs new), primary tier: rate ratio 0.829.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **holds** (21:00-02:00 4.358 (p < 0.001) vs whole night 3.533; difference p 0.041)

## New Year's Eve night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 2.351 | 1.941–2.847 | < 0.001 | 240 | 557 |
| Filtered (explainable removed) | 2.557 | 2.102–3.109 | < 0.001 | 234 | 513 |
| Unexplained (filtered, no lantern or fireworks description) | 2.452 | 2.009–2.991 | < 0.001 | 232 | 506 |
| High quality | 3.317 | 2.533–4.344 | < 0.001 | 141 | 244 |

Moon illumination (full vs new), primary tier: rate ratio 1.145.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **holds** (21:00-02:00 6.078 (p < 0.001) vs whole night 2.452; difference p < 0.001)

## Championship-win night, counties near the winner's city

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 0.703 | 0.165–2.994 | 0.634 | 15 | 24 |
| Filtered (explainable removed) | 0.739 | 0.173–3.156 | 0.683 | 15 | 23 |
| Unexplained (filtered, no lantern or fireworks description) | 0.739 | 0.173–3.156 | 0.683 | 15 | 23 |
| High quality | 0.000 | 0.000–81323663889640368304889528320.000 | 0.840 | 9 | 11 |

Moon illumination (full vs new), primary tier: rate ratio 1.131.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **does not hold** (21:00-02:00 1.409 (p 0.656) vs whole night 0.739; difference p 0.273)
- Rises more in the winner's city than the loser's: **does not hold** (winner's city 0.739 (p 0.683) vs loser's city 0.354; difference p 0.280)

## Secondary estimates

Lantern or fireworks wording is matched the same way on every night; the primary tier removes those events, this row counts only them.

| Subset | Rate ratio | 95% CI | p | Events |
| --- | --- | --- | --- | --- |
| july4, lantern or fireworks wording | 91.608 | 27.784–302.043 | 1.16e-13 | 37 |
| new_year, lantern or fireworks wording | 34.333 | 3.982–296.011 | 0.00129 | 7 |
| championship, loser's city | 0.354 | 0.048–2.628 | 0.31 | 24 |
| championship, lantern or fireworks wording | — | — | — | No informative strata with both exposed and control rows |

championship strata: 176; lantern-like events (filtered tier): 853.

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288. Reports with only medium-confidence matches (kept): 4,381.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
