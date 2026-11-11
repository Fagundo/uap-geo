# H-launch-01 report card: Rocket launches seen at twilight

**Split:** confirm (2011–2020)  
**Run:** H-launch-01-confirm-20261111T045021Z  
**Code:** `6fc368cd759e`  
**Spec / impl / filters SHA-256:** `0e6fe26b4d6a` / `e2a5c5165395` / `8b2d4002b6f7`

## Question

Rockets launched in twilight, when the exhaust plume is sunlit above a dark sky, raise UAP reports in counties within 1,200 km of the pad on the night of the launch, compared with the same counties on comparable nights.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Twilight launches (Sun 4-18 degrees below the horizon at the pad), counties within 1,200 km | **confirmed** | 2.177 (1.901–2.493) | < 0.001 | 19% |

## Twilight launches (Sun 4-18 degrees below the horizon at the pad), counties within 1,200 km

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 2.171 | 1.898–2.483 | < 0.001 | 126 | 1,274 |
| Filtered (explainable removed) | 2.177 | 1.901–2.493 | < 0.001 | 126 | 1,248 |
| High quality | 2.388 | 1.995–2.858 | < 0.001 | 123 | 668 |

Moon illumination (full vs new), primary tier: rate ratio 0.685.

**Discriminating checks (primary tier)**

- Concentrated in the 90 minutes after liftoff: **holds** (90-minute window 9.340 (p < 0.001) vs whole night 2.177; difference p < 0.001)
- Twilight launches raise reports more than daytime launches: **holds** (twilight 2.177 (p < 0.001) vs day 1.132; difference p < 0.001)
- Stronger within 400 km than at 800-1,200 km: **holds** (within 400 km 3.404 (p < 0.001) vs 800-1,200 km 1.511; difference p < 0.001)

## Launches and secondary estimates (primary tier)

Launches in this split by lighting at the pad: day 232, night 138, twilight 43.

| Subset | Rate ratio | 95% CI | p | Events |
| --- | --- | --- | --- | --- |
| twilight launches, all distances | 2.177 | 1.901–2.493 | 2.09e-29 | 1,248 |
| night launches, all distances | 1.341 | 1.220–1.474 | 1.14e-09 | 3,405 |
| day launches, all distances | 1.132 | 1.048–1.222 | 0.00159 | 5,821 |
| twilight, 0-400 km | 3.404 | 2.717–4.265 | 1.88e-26 | 358 |
| twilight, 400-800 km | 1.952 | 1.562–2.440 | 4.13e-09 | 495 |
| twilight, 800-1,200 km | 1.511 | 1.153–1.979 | 0.00276 | 395 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, sky_lantern 56. Reports with only medium-confidence matches (kept): 3,941.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
