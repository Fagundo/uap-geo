# H-volcano-01 report card: Proximity to young volcanoes

**Split:** explore (2001–2010)  
**Run:** H-volcano-01-explore-20261111T134308Z  
**Code:** `8685729cfb15`  
**Spec / impl / filters SHA-256:** `e7f9ff819a02` / `c0dbffb0deb1` / `8b2d4002b6f7`

## Question

Counties closer to a Holocene volcano report more UAP events than the observer controls predict, including terrain relief, and the real volcano locations line up with high-reporting counties better than rigidly shifted copies of them.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Closeness to the nearest Holocene volcano (per SD), with terrain relief controlled | **exploration (no verdict)** | 1.062 (0.935–1.208) | 0.354 | 100% |

## Closeness to the nearest Holocene volcano (per SD), with terrain relief controlled

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.074 | 0.947–1.217 | 0.266 | 3,100 | 23,077 |
| Filtered (explainable removed) | 1.062 | 0.935–1.208 | 0.354 | 3,100 | 21,798 |
| High quality | 1.008 | 0.912–1.115 | 0.871 | 3,100 | 9,770 |

**Discriminating checks (primary tier)**

- Real site locations beat rigidly shifted copies of the layer (one-sided p < 0.05): **does not hold** (rate ratio 1.062, p 0.637)

## Observed and expected events by distance to the nearest Holocene volcano (primary tier)

43 Holocene volcano. Expected counts come from the controls-only model; descriptive.

| Distance | Counties | Observed | Expected | Ratio |
| --- | --- | --- | --- | --- |
| 0–25 km | 9 | 84 | 110 | 0.76 |
| 25–50 km | 27 | 654 | 801 | 0.82 |
| 50–100 km | 73 | 1,478 | 1,541 | 0.96 |
| 100–200 km | 124 | 2,715 | 3,237 | 0.84 |
| 200+ km | 2,867 | 16,648 | 17,832 | 0.93 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
