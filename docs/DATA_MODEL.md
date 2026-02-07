# Data Model

## Airfield JSON (`/site/api/airfield/<IDENT>.json`)
- `ident`, `name`, `elevation_m`, `latitude_deg`, `longitude_deg`
- `runways[]`: `designator`, `magnetic_heading_deg`, `length_m`, `surface`
- `night_ops`: `night_ops_allowed`, `lighting`, `ppr_required`, `ops_hours`, `notes`
- `metar`: `raw`, `observed_time_utc`, `wind_dir_deg`, `wind_speed_kt`, `gust_kt`, `variable_wind`, `visibility_m`, `weather_codes`, `cloud_layers`, `ceiling_ft`, `temp_c`, `dewpoint_c`, `qnh_hpa`, `remarks`, `source`
- `taf`: `raw`, `summary.valid_from`, `summary.valid_to`, `summary.key_changes`, `source`
- `computed`: `wind_components_per_runway`, `density_altitude`, `qnh_trend`, `flags`, `severity`, `trends`

## Route JSON (`/site/api/route/<ROUTE_ID>.json`)
- `route_id`, `dep`, `dest`, `alternates`, `corridor_nm`, `cruise_levels_ft`
- `airfields[]` (embedded airfield summaries)
- `track_deg`, `upper_winds[]`, `freezing_level_ft`
- `sigmet_lines[]`, `notams{}`
- `summary.flags[]`, `summary.severity`

## Profiles (`/site/api/profiles.json`)
- `name`, `licence_tier`, `ratings`, `operation_context`
- `thresholds`: `max_crosswind_kt`, `max_tailwind_kt`, `max_gust_spread_kt`, `max_da_ft`, `min_vis_m`, `min_ceiling_ft`, `qnh_fall_fast_hpa_per_hr`

## Aircraft (`/site/api/aircraft.json`)
- `type`, `demonstrated_crosswind_kt`, `notes`
