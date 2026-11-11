# Hypotheses

One YAML file per pre-registered hypothesis. A file is written and committed **before** the
hypothesis touches confirmation data; the commit timestamp is the registration record.

Rules:

- Registered files are never edited. A changed hypothesis gets a new ID.
- Exploration years (2001-2010) are for pipeline checks and power estimates only, not tuning.
- Every confirmation run is recorded in `results/`, including nulls and underpowered results.
- Explanation filters are defined in `configs/filters.yaml`; a hypothesis lists in
  `filters_disabled` any rule that keys on its own exposure.

| ID | Title | Status |
| --- | --- | --- |
| H-geo-01 | Geophysical triggers (Persinger) | registered 2026-11-10 |
