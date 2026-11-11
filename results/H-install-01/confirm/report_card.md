# H-install-01 report card: Proximity to military installations

**Split:** confirm (2021–latest)  
**Run:** H-install-01-confirm-20261111T151819Z  
**Code:** `b791e42ca170`  
**Spec / impl / filters SHA-256:** `d74fb83d1d96` / `7277d1368a61` / `8b2d4002b6f7`

## Question

Counties closer to a military installation report more UAP events than the observer controls predict, and the real installation map lines up with high-reporting counties better than rigidly shifted copies of it.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Closeness to the nearest military installation (per SD) | **inconclusive** | 1.020 (0.976–1.066) | 0.384 | 60% |

## Closeness to the nearest military installation (per SD)

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.018 | 0.973–1.065 | 0.441 | 3,100 | 3,957 |
| Filtered (explainable removed) | 1.020 | 0.976–1.066 | 0.384 | 3,100 | 3,909 |
| High quality | 1.026 | 0.972–1.083 | 0.354 | 3,100 | 1,633 |

**Discriminating checks (primary tier)**

- Real site locations beat rigidly shifted copies of the layer (one-sided p < 0.05): **does not hold** (rate ratio 1.020, p 0.254)

## Observed and expected events by distance to the nearest military installation (primary tier)

859 military installation. Expected counts come from the controls-only model; descriptive.

| Distance | Counties | Observed | Expected | Ratio |
| --- | --- | --- | --- | --- |
| 0–25 km | 546 | 1,630 | 1,721 | 0.95 |
| 25–50 km | 760 | 1,198 | 1,369 | 0.88 |
| 50–100 km | 1,164 | 805 | 772 | 1.04 |
| 100–200 km | 510 | 179 | 201 | 0.89 |
| 200+ km | 120 | 20 | 28 | 0.72 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
