# H-volcano-01 report card: Proximity to young volcanoes

**Split:** confirm (2021–latest)  
**Run:** H-volcano-01-confirm-20261111T152404Z  
**Code:** `b642a90a2d1b`  
**Spec / impl / filters SHA-256:** `62a188b1befb` / `1790c230e7db` / `8b2d4002b6f7`

## Question

Counties closer to a Holocene volcano report more UAP events than the observer controls predict, including terrain relief, and the real volcano locations line up with high-reporting counties better than rigidly shifted copies of them.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Closeness to the nearest Holocene volcano (per SD), with terrain relief controlled | **underpowered** | 1.072 (0.861–1.335) | 0.534 | 9% |

## Closeness to the nearest Holocene volcano (per SD), with terrain relief controlled

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.066 | 0.859–1.322 | 0.562 | 3,100 | 3,957 |
| Filtered (explainable removed) | 1.072 | 0.861–1.335 | 0.534 | 3,100 | 3,909 |
| High quality | 1.094 | 0.883–1.356 | 0.409 | 3,100 | 1,633 |

**Discriminating checks (primary tier)**

- Real site locations beat rigidly shifted copies of the layer (one-sided p < 0.05): **does not hold** (rate ratio 1.072, p 0.313)

## Observed and expected events by distance to the nearest Holocene volcano (primary tier)

43 Holocene volcano. Expected counts come from the controls-only model; descriptive.

| Distance | Counties | Observed | Expected | Ratio |
| --- | --- | --- | --- | --- |
| 0–25 km | 9 | 23 | 21 | 1.11 |
| 25–50 km | 27 | 124 | 150 | 0.83 |
| 50–100 km | 73 | 230 | 268 | 0.86 |
| 100–200 km | 124 | 474 | 494 | 0.96 |
| 200+ km | 2,867 | 2,981 | 3,159 | 0.94 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
