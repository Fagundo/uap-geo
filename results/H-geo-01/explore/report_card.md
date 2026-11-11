# H-geo-01 report card: Geophysical triggers (Persinger)

**Split:** explore (2001–2010)  
**Run:** H-geo-01-explore-20261111T021509Z  
**Code:** `f4a2fb9472d1`  
**Spec / impl / filters SHA-256:** `c2f4e7ae6942` / `08b647819389` / `3745ee2dc539`

## Question

Unexplained UAP reports rise during geomagnetic storms and in the two weeks before nearby earthquakes, compared with the same place on comparable nights.

This is an **exploration** run: it checks the pipeline and estimates power. Its estimates are shown for completeness and change nothing in the registered tests.

## Verdicts

| Test | Verdict | Primary rate ratio (95% CI) | BH-adjusted p | Power for RR 1.10 |
| --- | --- | --- | --- | --- |
| Geomagnetic storms (Kp >= 6), storm night and next night | **exploration (no verdict)** | 0.939 (0.887–0.993) | 0.057 | 92% |
| Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake | **exploration (no verdict)** | 0.844 (0.704–1.011) | 0.066 | 21% |

## Geomagnetic storms (Kp >= 6), storm night and next night

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 0.961 | 0.909–1.015 | 0.156 | 95 | 11,090 |
| Filtered (explainable removed) | 0.939 | 0.887–0.993 | 0.029 | 95 | 10,617 |
| High quality | 0.935 | 0.859–1.018 | 0.123 | 95 | 4,780 |

Moon illumination (full vs new), primary tier: rate ratio 0.862.

**Discriminating checks (primary tier)**

- Effect present south of 37 N (aurora rarely visible): **does not hold** (rate ratio 0.961, p 0.382)
- Stronger for Kp >= 8 than Kp 6-7: **does not hold** (strong 0.890 (p 0.075) vs weaker 0.951 (p 0.120))

## Mainshocks M >= 4.0 within 100 km, 14 nights before through the quake

| Tier | Rate ratio | 95% CI | p | Strata | Events |
| --- | --- | --- | --- | --- | --- |
| All events | 0.856 | 0.720–1.019 | 0.080 | 350 | 775 |
| Filtered (explainable removed) | 0.844 | 0.704–1.011 | 0.066 | 339 | 728 |
| High quality | 0.989 | 0.774–1.264 | 0.931 | 211 | 360 |

Moon illumination (full vs new), primary tier: rate ratio 0.885.

**Discriminating checks (primary tier)**

- Stronger for M >= 5.0 than M 4.0-5.0: **does not hold** (strong 1.343 (p 0.374) vs weaker 0.814 (p 0.032))

## Data

- Reports 2001–latest after cleaning: 74,795; merged into 69,348 events (69,333 located in a county).
- Events explained at high confidence, by rule: aurora 151, fireworks 248, meteor_fireball 1,506, nuforc_note 1,668, sky_lantern 56. Reports with only medium-confidence matches (kept): 4,970.

## Caveats

- Reports are self-selected and unverified; results describe reporting, not phenomena.
- Filter precision was checked against labels written by Claude (an AI), not by a human.
- Planet and ISS rules are not yet implemented; launch-matched rules run on text only (medium confidence).
- A rate ratio describes reporting on exposed nights versus the same places on matched nights; it does not identify a mechanism.
