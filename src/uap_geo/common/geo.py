"""Geographic constants shared across the pipeline (pandas-only, no GIS imports)."""

from __future__ import annotations

WGS84 = "EPSG:4326"

# State FIPS codes outside the contiguous US (Alaska, Hawaii, territories).
NON_CONUS_STATE_FIPS = frozenset({"02", "15", "60", "66", "69", "72", "78"})

# Postal codes for the 48 contiguous states plus DC.
CONUS_STATES = frozenset(
    {
        "AL", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FL", "GA", "ID", "IL", "IN", "IA",
        "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH",
        "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
        "UT", "VT", "VA", "WA", "WV", "WI", "WY",
    }
)

COUNTY_ID = "geoid"
M_PER_KM = 1_000.0
M2_PER_KM2 = 1_000_000.0
