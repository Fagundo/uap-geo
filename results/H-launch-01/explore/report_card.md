# H-launch-01 report card: Rocket launches seen at twilight

**Split:** explore (2001–2010)  
**Run:** H-launch-01-explore-20261111T114934Z  
**Code:** `df6b6be61655`  
**Spec / impl / filters SHA-256:** `0e6fe26b4d6a` / `e2a5c5165395` / `8b2d4002b6f7`

## Question

Rockets launched in twilight, when the exhaust plume is sunlit above a dark sky, raise UAP reports in counties within 1,200 km of the pad on the night of the launch, compared with the same counties on comparable nights.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Twilight launches (Sun 4-18 degrees below the horizon at the pad), counties within 1,200 km | **exploration (no verdict)** | 2.840 (2.350–3.432) | < 0.001 | 11% |

## Twilight launches (Sun 4-18 degrees below the horizon at the pad), counties within 1,200 km

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 2.846 | 2.359–3.433 | < 0.001 | 94 | 565 |
| Filtered (explainable removed) | 2.840 | 2.350–3.432 | < 0.001 | 94 | 555 |
| High quality | 2.759 | 2.100–3.624 | < 0.001 | 83 | 274 |

Moon illumination (full vs new), primary tier: rate ratio 0.899.

**Discriminating checks (primary tier)**

- Concentrated in the 90 minutes after liftoff: **holds** (90-minute window 16.308 (p < 0.001) vs whole night 2.840; difference p < 0.001)
- Twilight launches raise reports more than daytime launches: **holds** (twilight 2.840 (p < 0.001) vs day 1.062; difference p < 0.001)
- Stronger within 400 km than at 800-1,200 km: **holds** (within 400 km 4.367 (p < 0.001) vs 800-1,200 km 1.687; difference p < 0.001)

## Launches and secondary estimates (primary tier)

Launches in this split by lighting at the pad: day 198, night 129, twilight 35.

| Subset | Rate ratio | 95% CI | p | Events |
| --- | --- | --- | --- | --- |
| twilight launches, all distances | 2.840 | 2.350–3.432 | 3.25e-27 | 555 |
| night launches, all distances | 1.287 | 1.126–1.471 | 0.000224 | 1,755 |
| day launches, all distances | 1.062 | 0.941–1.197 | 0.329 | 2,500 |
| twilight, 0-400 km | 4.367 | 3.219–5.926 | 2.9e-21 | 181 |
| twilight, 400-800 km | 2.815 | 2.028–3.907 | 6.12e-10 | 189 |
| twilight, 800-1,200 km | 1.687 | 1.156–2.461 | 0.00665 | 185 |

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, sky_lantern 56. Reports with only medium-confidence matches (kept): 3,941.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
