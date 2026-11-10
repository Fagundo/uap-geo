# uap-geo

Do UAP reports in the contiguous US cluster around geologic features (faults, earthquakes, rivers,
magnetic anomalies) **beyond** what observer opportunity explains (population, dark skies, air traffic,
military activity)?

v1 replicates the county-level design of
[Medina, Brewer & Kirkpatrick (2023), *Scientific Reports*](https://doi.org/10.1038/s41598-023-49527-x)
and adds geologic covariates to the same model.

## What v1 does

1. **Ingest** — NUFORC reports from the [TidyTuesday 2023-06-20 extract](https://github.com/rfordatascience/tidytuesday/tree/main/data/2023/2023-06-20)
   (city coordinates from geonames.org), cleaned to 2001–2020 in the lower 48 and deduplicated.
   Reports without coordinates are geocoded offline against the Census Gazetteer.
2. **Build** — one row per county: report count, 2020 population, and covariates.
3. **Analyze**
   - Getis-Ord Gi* hotspots on reports per 10,000 people (k = 8 nearest neighbours).
   - Negative binomial models with a log(population) offset, covariates z-scored:
     **A** = observer covariates, **B** = A + geology. Both fit on the same counties; compare AIC.
   - Moran's I on model B residuals: if residuals still cluster, move to a spatial (BYM2) model.
   - Models A → E add, in turn: observer controls, geology, state fixed effects, settlement density,
     and other water plus terrain.
   - Shift tests: rotate and shift a whole layer (rivers, lakes, reservoirs) many times, refit, and compare
     the real coefficient against the shifted ones (Benjamini–Hochberg adjusted across layers).
   - Report-level test: within each county, are Census places with reports closer to water than places without?

## Covariates

| Column | Source | Status |
| --- | --- | --- |
| `airports_per_km2` | OurAirports (airports, heliports, seaplane bases, balloonports) | on |
| `military_area_share` | Census TIGER 2019 military installations | on |
| `cloud_cover` | EarthEnv MODIS mean annual cloud frequency | on |
| `log_pop_density` | 2020 Census population / county area | on (light-pollution stand-in) |
| `light_pollution` | Falchi et al. World Atlas (GFZ) | **off** — set a direct GeoTIFF URL in `configs/v1.yaml` |
| `tree_canopy` | NLCD/USFS Tree Canopy Cover | **off** — multi-GB; set URL to enable |
| `fault_length_per_km2` | USGS Quaternary Fault and Fold Database | on |
| `log_quake_count`, `log_seismic_moment` | USGS ComCat, M ≥ 2.5, 2001–2020 | on |
| `river_length_per_km2` | Natural Earth 1:10m rivers (coarse) | on |
| `lake_area_share`, `dist_to_lake_km` | Natural Earth 1:10m lakes + North America supplement | on |
| `reservoirs_per_km2` | USACE National Inventory of Dams (normal storage ≥ 1,000 acre-ft) | on |
| `dist_to_coast_km` | Natural Earth 1:10m coastline | on |
| `elevation_relief_m` | EarthEnv 1 km GMTED2010 elevation, max − min per county | on |
| `places_per_km2` | Census Gazetteer places (settlement density) | on |
| `magnetic_anomaly` | USGS / NAMAG magnetic grid | **off** — set URL to enable |

A source that fails to download is logged and its columns are dropped; the run continues.

## Run it

**GitHub Actions (recommended):** Actions → *v1 analysis* → *Run workflow*. Results land in the job
summary and in the `uap-geo-v1-<n>` artifact (`summary.md`, coefficient CSVs, `hotspots_gi_star.png`,
`county_table.csv`). Raw downloads are cached between runs.

**Locally:**

```bash
uv sync --group dev
uv run pytest
uv run uap-geo run --config configs/v1.yaml                    # all stages
uv run uap-geo run --stage analyze --permutations 0             # rerun analysis only
```

## Layout

```
src/uap_geo/
├── common/              # config, downloads, CRS constants, abstract base classes
├── data/
│   ├── scraping/        # one DataSource per dataset + SourceRegistry
│   ├── io/              # Parquet / GeoParquet TableStore
│   └── preprocessing/   # report cleaning, offline geocoding (pandas only)
├── features/            # CovariateBuilder subclasses, CovariateRegistry, county table assembly
├── training/            # NegBinRateModel, ModelSpec
├── evaluation/          # Gi*, Moran's I, fault-shift permutation, report writer
├── pipeline.py          # V1Pipeline: ingest → build → analyze
└── cli.py
```

To add a covariate: write a `DataSource` (if new data) and a `CovariateBuilder`, register them in
`data/scraping/registry.py` and `features/registry.py`, and list the column under `models` in the config.

## Caveats

- NUFORC is self-reported and unverified; city-level geocoding means county is the finest honest grain.
- The NUFORC JSON schema is not documented; `ReportCleaner` resolves likely column names and logs what it found.
- Natural Earth rivers are coarse; swap in NHDPlus HR in phase 2.
