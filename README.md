# uap-geo

Do UAP reports in the contiguous US cluster around geologic or environmental features (faults,
earthquakes, rivers, lakes, terrain, natural radiation, nuclear sites) **beyond** what observer
opportunity explains (population, dark skies, air traffic, military activity)?

The design extends the county-level model of
[Medina, Brewer & Kirkpatrick (2023), *Scientific Reports*](https://doi.org/10.1038/s41598-023-49527-x).

**Current answer (v1, Nov 2026):** no geologic or radiation factor holds up. Only observer effects
replicate on held-out years: fewer reports under bright skies, more near airports and in high-relief
terrain. A river signal is unconfirmed. See [docs/RESULTS.md](docs/RESULTS.md) and
[docs/ROBUSTNESS.md](docs/ROBUSTNESS.md).

## Pipeline

1. **Ingest:** NUFORC reports from the
   [TidyTuesday 2023-06-20 extract](https://github.com/rfordatascience/tidytuesday/tree/main/data/2023/2023-06-20)
   (city coordinates from geonames.org), filtered to the study years and the lower 48, deduplicated.
   Reports without coordinates are geocoded offline against the Census Gazetteer.
2. **Build:** one row per county with the report count, population, and every covariate.
3. **Analyze:**
   - Getis-Ord Gi* hotspots on reports per 10,000 people (k = 8 nearest neighbours).
   - Negative binomial rate models with a log(population) offset. Continuous covariates are
     z-scored (rate ratio per SD); 0/1 band indicators are not. All models are fit on the same counties.
   - Moran's I on residuals.
   - **Shift tests:** a whole layer (rivers, lakes, reservoirs) is rotated and shifted many times
     and the model refit; the real coefficient is compared against the shifted ones
     (Benjamini–Hochberg adjusted across layers).
   - **Town-level test:** within each county, are Census places with reports closer to rivers,
     lakes, coast, roads or rail than places without? Conditional logit, sized by land area and by population.
   - Collinearity (VIF) for the widest model.

### Models

| Model | Adds | Role |
| --- | --- | --- |
| A | Light pollution, cloud cover, airports, military area, population density | Replicates the paper |
| B | Fault length, earthquake count, river length | Geology, national |
| C | State fixed effects | Geology within states |
| D | Town density, primary roads, rail | Settlement and corridor controls |
| E | Lakes, reservoirs, coast distance, elevation relief | Other water and terrain |
| F | Gamma-ray uranium/thorium/potassium, nuclear plant within 50 km, weapons site within 100 km | Radiation |
| R | Light, airports, town density, roads, rail, relief, coast, rivers + state FE | Lean, pre-specified **confirmatory** model |

Models A–F are exploratory. Only model R evaluated on held-out data counts as confirmation.

## Covariates

| Column | Source | Status |
| --- | --- | --- |
| `light_pollution` | Falchi et al. (2016) World Atlas of artificial sky brightness (GFZ) | on |
| `cloud_cover` | EarthEnv MODIS mean annual cloud frequency | on |
| `airports_per_km2` | OurAirports (airports, heliports, seaplane bases, balloonports) | on |
| `military_area_share` | Census TIGER 2019 military installations | on |
| `log_pop_density` | Census 2020 county population / area | on |
| `places_per_km2` | Census Gazetteer places | on |
| `primary_road_length_per_km2`, `rail_length_per_km2` | Census TIGER 2020 primary roads, rail | on |
| `fault_length_per_km2` | USGS Quaternary Fault and Fold Database | on |
| `log_quake_count`, `log_seismic_moment` | USGS ComCat, M ≥ 2.5, study years | on |
| `river_length_per_km2` | Natural Earth 1:10m rivers (major rivers only) | on |
| `lake_area_share`, `dist_to_lake_km` | Natural Earth 1:10m lakes + North America supplement | on |
| `reservoirs_per_km2` | USACE National Inventory of Dams (normal storage ≥ 1,000 acre-ft) | on |
| `dist_to_coast_km` | Natural Earth 1:10m coastline | on |
| `elevation_relief_m` | EarthEnv 1 km GMTED2010 elevation, max − min per county | on |
| `gamma_uranium`, `gamma_thorium`, `gamma_potassium` | USGS Bayesian NURE predictions (regional point CSVs, ScienceBase) | on |
| `nuclear_power_within_50km` | US commercial reactor sites (michaelminn.net GeoJSON) | on |
| `weapons_site_within_100km` | 19 weapons-complex sites listed in `configs/v1.yaml` | on |
| `tree_canopy` | NLCD/USFS Tree Canopy Cover | off: multi-GB 30 m tiles |
| `magnetic_anomaly` | USGS / NAMAG magnetic grid | off: no direct GeoTIFF link |

A source that fails to download is logged and its columns are dropped; the run continues.

## Run it

**GitHub Actions (recommended):** Actions → *v1 analysis* → *Run workflow*. Inputs:

- `stages`: `ingest build analyze` (default)
- `permutations`: shifted copies per layer; `0` skips shift tests. Per-layer overrides (rivers: 1,000)
  are in the config.
- `extra_args`: anything the CLI accepts, e.g. the holdout run below.

Results are printed in the job log, written to the job summary, and uploaded as the
`uap-geo-v1-<n>` artifact. Raw downloads are cached between runs.

**Holdout run** (model R on years the exploration never used):

```
--start-year 2021 --end-year 2023 --tag holdout --shift-models R_confirmatory
```

`--tag` writes interim, processed and output files to a sub-folder so a holdout never overwrites the main run.

**Locally:**

```bash
uv sync --group dev
uv run pytest
uv run uap-geo run --config configs/v1.yaml                         # all stages, 2001–2020
uv run uap-geo run --stage analyze --permutations 0                  # rerun analysis only
uv run uap-geo run --start-year 2021 --end-year 2023 --tag holdout   # holdout
```

## Layout

```
src/uap_geo/
├── common/              # config, downloads, CRS constants, abstract base classes
├── data/
│   ├── scraping/        # one DataSource per dataset, SourceRegistry, pure-pandas parsers
│   ├── io/              # Parquet / GeoParquet TableStore
│   └── preprocessing/   # report cleaning, offline geocoding (pandas only)
├── features/            # CovariateBuilder subclasses, CovariateRegistry, county table assembly
├── training/            # NegBinRateModel (robust NB fitting), ModelSpec
├── evaluation/          # Gi*, Moran's I, shift tests, town-level test, BH/VIF helpers, report writer
├── pipeline.py          # V1Pipeline: ingest → build → analyze
└── cli.py               # overrides: years, tag, shift models, per-layer permutations
docs/
├── RESULTS.md           # findings so far
└── ROBUSTNESS.md        # threats to validity and planned fixes
```

To add a covariate: write a `DataSource` (if new data) and a `CovariateBuilder`, register them in
`data/scraping/registry.py` and `features/registry.py`, and list the column under `models` in the config.
To shift-test a layer, add it to `ShiftLayer` factories in `pipeline.py` and to `study.shift_layers`.

## Limitations

- NUFORC is self-reported and unverified; results describe **reporting**, not phenomena.
- The TidyTuesday extract holds 71% of the reports the paper used for 2001–2020, and few after 2020.
- City-level geocoding makes the county the finest honest grain for rate models.
- Residual spatial clustering remains, so ordinary p-values are optimistic; rely on shift tests and holdouts.
- Dependencies are not yet pinned with a lockfile. See [docs/ROBUSTNESS.md](docs/ROBUSTNESS.md) for the full list.
