# H-install-01 report card: Proximity to military installations

**Split:** explore (2001–2010)  
**Run:** H-install-01-explore-20261111T133721Z  
**Code:** `4b6c70fcd4eb`  
**Spec / impl / filters SHA-256:** `7167e1cdbc55` / `59c7e037cb0d` / `8b2d4002b6f7`

## Question

Counties closer to a military installation report more UAP events than the observer controls predict, and the real installation map lines up with high-reporting counties better than rigidly shifted copies of it.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Closeness to the nearest military installation (per SD) | **exploration (no verdict)** | 1.006 (0.971–1.043) | 0.733 | 100% |

## Closeness to the nearest military installation (per SD)

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.006 | 0.971–1.041 | 0.758 | 3,100 | 23,077 |
| Filtered (explainable removed) | 1.006 | 0.971–1.043 | 0.733 | 3,100 | 21,798 |
| High quality | 0.987 | 0.945–1.031 | 0.559 | 3,100 | 9,770 |

**Discriminating checks (primary tier)**

- Real site locations beat rigidly shifted copies of the layer (one-sided p < 0.05): **does not hold** (rate ratio 1.006, p 0.328)

## Observed and expected events by distance to the nearest military installation (primary tier)

859 military installation. Expected counts come from the controls-only model; descriptive.

| Distance | Counties | Observed | Expected | Ratio |
| --- | --- | --- | --- | --- |
| 0–25 km | 546 | 8,991 | 9,728 | 0.92 |
| 25–50 km | 760 | 7,013 | 8,137 | 0.86 |
| 50–100 km | 1,164 | 4,327 | 4,395 | 0.98 |
| 100–200 km | 510 | 1,113 | 1,115 | 1.00 |
| 200+ km | 120 | 135 | 145 | 0.93 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
