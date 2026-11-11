# H-geo-01 report card: Geophysical triggers (Persinger)

**Split:** confirm (2011–2020)  
**Run:** H-geo-01-confirm-20261111T024731Z  
**Code:** `8f4bc281cd17`  
**Spec / impl / filters SHA-256:** `c2f4e7ae6942` / `bd91649c845d` / `8b2d4002b6f7`

## Question

Unexplained UAP reports rise during geomagnetic storms and in the two weeks before nearby earthquakes, compared with the same place on comparable nights.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Geomagnetic storms (Kp >= 6), storm night and next night | **refuted** | 0.997 (0.943–1.054) | 0.915 | 92% |
| Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake | **underpowered** | 1.140 (0.979–1.328) | 0.182 | 25% |

## Geomagnetic storms (Kp >= 6), storm night and next night

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.036 | 0.983–1.093 | 0.188 | 57 | 12,669 |
| Filtered (explainable removed) | 0.997 | 0.943–1.054 | 0.915 | 57 | 11,984 |
| High quality | 0.930 | 0.856–1.011 | 0.088 | 57 | 5,600 |

Moon illumination (full vs new), primary tier: rate ratio 0.874.

**Discriminating checks (primary tier)**

- Effect present south of 37 N (aurora rarely visible): **does not hold** (rate ratio 0.965, p 0.451)
- Stronger for Kp >= 8 than Kp 6-7: **holds** (strong 1.276 (p 0.034) vs weaker 0.982 (p 0.538))

## Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 1.169 | 1.007–1.356 | 0.040 | 411 | 934 |
| Filtered (explainable removed) | 1.140 | 0.979–1.328 | 0.091 | 397 | 899 |
| High quality | 1.192 | 0.960–1.480 | 0.112 | 242 | 438 |

Moon illumination (full vs new), primary tier: rate ratio 1.248.

**Discriminating checks (primary tier)**

- Stronger for M >= 5.0 than M 4.0-5.0: **does not hold** (strong 1.214 (p 0.472) vs weaker 1.134 (p 0.122))

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: meteor_fireball 1,461, nuforc_note 2,288, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,980.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
