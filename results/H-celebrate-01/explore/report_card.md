# H-celebrate-01 report card: Celebration nights

**Split:** explore (2001–2010)  
**Run:** H-celebrate-01-explore-20261111T115351Z  
**Code:** `d903b462f592`  
**Spec / impl / filters SHA-256:** `25d526fdc80a` / `99e4e849525f` / `8b2d4002b6f7`

## Question

Celebration nights raise UAP reports that the filters leave unexplained: reports with no lantern, fireworks or fire-coloured-light wording rise on the Fourth of July and New Year's Eve in every county, and on the night of a championship win in the counties around the winner's home city, compared with the same counties on comparable nights.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Fourth of July night, every county | **exploration (no verdict)** | 2.422 (2.013–2.915) | < 0.001 | 12% |
| New Year's Eve night, every county | **exploration (no verdict)** | 1.802 (1.408–2.308) | < 0.001 | 9% |
| Championship-win night, counties near the winner's city | **exploration (no verdict)** | 0.451 (0.060–3.389) | 0.439 | 5% |

## Fourth of July night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 3.785 | 3.292–4.350 | < 0.001 | 315 | 911 |
| Filtered (explainable removed) | 3.992 | 3.463–4.602 | < 0.001 | 308 | 856 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 2.422 | 2.013–2.915 | < 0.001 | 274 | 628 |
| High quality | 4.900 | 4.022–5.971 | < 0.001 | 198 | 419 |

Moon illumination (full vs new), primary tier: rate ratio 0.791.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **does not hold** (21:00-02:00 2.559 (p < 0.001) vs whole night 2.422; difference p 0.363)

## New Year's Eve night, every county

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 2.351 | 1.941–2.847 | < 0.001 | 240 | 557 |
| Filtered (explainable removed) | 2.557 | 2.102–3.109 | < 0.001 | 234 | 513 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 1.802 | 1.408–2.308 | < 0.001 | 201 | 386 |
| High quality | 3.317 | 2.533–4.344 | < 0.001 | 141 | 244 |

Moon illumination (full vs new), primary tier: rate ratio 1.088.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **holds** (21:00-02:00 3.507 (p < 0.001) vs whole night 1.802; difference p 0.002)

## Championship-win night, counties near the winner's city

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 0.703 | 0.165–2.994 | 0.634 | 15 | 24 |
| Filtered (explainable removed) | 0.739 | 0.173–3.156 | 0.683 | 15 | 23 |
| Unexplained (filtered; no lantern, fireworks or fire-coloured light wording) | 0.451 | 0.060–3.389 | 0.439 | 15 | 18 |
| High quality | 0.000 | 0.000–81323676214330192389856034816.000 | 0.840 | 9 | 11 |

Moon illumination (full vs new), primary tier: rate ratio 0.893.

**Discriminating checks (primary tier)**

- Concentrated 21:00-02:00 local time: **does not hold** (21:00-02:00 0.857 (p 0.884) vs whole night 0.451; difference p 0.331)
- Rises more in the winner's city than the loser's: **does not hold** (winner's city 0.451 (p 0.439) vs loser's city 0.405; difference p 0.471)

## Secondary estimates

Lantern, fireworks or fire-coloured-light wording is matched the same way on every night; the primary tier removes those events, the 'wording' rows count only them.

| Subset | Rate ratio | 95% CI | p | Events |
| --- | --- | --- | --- | --- |
| july4, lantern, fireworks or fire-coloured wording | 12.507 | 9.583–16.323 | 3.49e-77 | 228 |
| new_year, lantern, fireworks or fire-coloured wording | 6.028 | 4.234–8.580 | 2.04e-23 | 127 |
| championship, loser's city | 0.405 | 0.054–3.035 | 0.379 | 20 |
| championship, lantern, fireworks or fire-coloured wording | 2.091 | 0.225–19.463 | 0.517 | 5 |

championship strata: 176; lantern-like events (filtered tier): 17,532.

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288. Reports with only medium-confidence matches (kept): 4,381.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
