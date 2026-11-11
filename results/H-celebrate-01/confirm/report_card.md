# H-celebrate-01 report card: Celebration nights

**Split:** confirm (2011–2020)  
**Run:** H-celebrate-01-confirm-20261111T120400Z  
**Code:** `618b49bed54e`  
**Spec / impl / filters SHA-256:** `b770deec65f8` / `99e4e849525f` / `8b2d4002b6f7`

## Question

Celebration nights raise UAP reports that the filters leave unexplained: reports with no lantern, fireworks or fire-coloured-light wording rise on the Fourth of July and New Year's Eve in every county, and on the night of a championship win in the counties around the winner's home city, compared with the same counties on comparable nights.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Fourth of July night, every county | **confirmed** | 2.479 (2.110–2.913) | < 0.001 | 14% |
| New Year's Eve night, every county | **confirmed** | 1.801 (1.456–2.227) | < 0.001 | 11% |
| Championship-win night, counties near the winner's city | **underpowered** | 0.656 (0.154–2.800) | 0.569 | 5% |

## Fourth of July night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 5.975 | 5.420–6.588 | < 0.001 | 404 | 1,661 |
| Filtered (explainable removed) | 6.101 | 5.530–6.732 | < 0.001 | 403 | 1,630 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 2.479 | 2.110–2.913 | < 0.001 | 342 | 821 |
| High quality | 8.346 | 7.319–9.518 | < 0.001 | 324 | 902 |

Moon illumination (full vs new), primary tier: rate ratio 0.963.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **holds** (21:00-02:00 3.215 (p < 0.001) vs whole night 2.479; difference p 0.022)

## New Year's Eve night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 4.691 | 4.140–5.315 | < 0.001 | 334 | 1,028 |
| Filtered (explainable removed) | 4.855 | 4.275–5.514 | < 0.001 | 330 | 982 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 1.801 | 1.456–2.227 | < 0.001 | 250 | 523 |
| High quality | 6.394 | 5.386–7.592 | < 0.001 | 238 | 524 |

Moon illumination (full vs new), primary tier: rate ratio 1.065.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **holds** (21:00-02:00 4.123 (p < 0.001) vs whole night 1.801; difference p < 0.001)

## Championship-win night, counties near the winner's city

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.152 | 0.448–2.961 | 0.770 | 22 | 38 |
| Filtered (explainable removed) | 1.203 | 0.467–3.095 | 0.702 | 22 | 37 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 0.656 | 0.154–2.800 | 0.569 | 16 | 25 |
| High quality | 2.103 | 0.695–6.363 | 0.188 | 16 | 19 |

Moon illumination (full vs new), primary tier: rate ratio 1.416.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **does not hold** (21:00-02:00 0.891 (p 0.913) vs whole night 0.656; difference p 0.406)
- Rises more in the winner's city than the loser's: **does not hold** (winner's city 0.656 (p 0.569) vs loser's city 0.887; difference p 0.613)

## Secondary estimates

Lantern, fireworks or fire-coloured-light wording is matched the same way on every night; the primary tier removes those events, the 'wording' rows count only them.

| Subset | Rate ratio | 95% CI | p | Events |
| --- | --- | --- | --- | --- |
| july4, lantern, fireworks or fire-coloured wording | 13.770 | 11.922–15.904 | 1.4e-278 | 809 |
| new_year, lantern, fireworks or fire-coloured wording | 12.657 | 10.447–15.335 | 3.44e-148 | 459 |
| championship, loser's city | 0.887 | 0.205–3.836 | 0.873 | 20 |
| championship, lantern, fireworks or fire-coloured wording | 2.942 | 0.762–11.352 | 0.117 | 12 |

championship strata: 176; lantern-like events (filtered tier): 17,532.

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288. Reports with only medium-confidence matches (kept): 4,381.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
