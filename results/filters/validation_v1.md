# Filter rule validation (v1)

Labels written by Claude (an AI) on a stratified sample; not human-reviewed.

| Rule | Labelled | Correct | Precision | Passes (>= 80%) |
| --- | --- | --- | --- | --- |
| aurora | 30 | 1 | 3% | no |
| fireworks | 30 | 1 | 3% | no |
| meteor_fireball | 33 | 26 | 79% | no |
| nuforc_note | 33 | 33 | 100% | yes |
| sky_lantern | 30 | 27 | 90% | yes |

Explainable reports the rules missed, in the random part of the sample: {'sky_lantern': 7, 'starlink_train': 3, 'nuforc_note': 3, 'meteor_fireball': 3, 'planet': 2, 'iss_satellite_flare': 2}.
