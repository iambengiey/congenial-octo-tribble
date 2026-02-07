# METAR.oncloud.africa

Static aviation briefing site for PPL and ATPL training. This repository builds a GitHub Pages site and JSON API with METAR/TAF decoding, runway wind components, density altitude, and ATPL route briefing packs.

> **Training/augmentation only. Not an official briefing source.** Always obtain official briefings from SAWS/ATC.

## Features

- **PPL mode (Airfields):** METAR/TAF decode, runway wind components, density altitude, and safety flags.
- **ATPL route packs:** METAR/TAF for dep/dest/alternates, NOTAM highlights, upper winds/temps, SIGMET/AIRMET, SIGWX charts, and training-only risk flags.
- **Static output:** `/site` for GitHub Pages + `/site/api` for JSON API.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.build_site
python -m http.server --directory site 8000
```

Then open `http://localhost:8000`.

## Makefile shortcuts

```bash
make build   # builds site
make test    # runs unit tests
make serve   # serves /site
make sample  # rebuilds using sample data
```

## Adding aerodromes

Edit `data/aerodromes.yaml`:

- `ident`, `name`, `elevation_m`
- `latitude_deg`, `longitude_deg` (for route bearings)
- Runway list with `designator`, `magnetic_heading_deg`, `length_m`, `surface`

## Adding routes (ATPL packs)

Edit `data/routes.yaml`:

- `route_id`, `dep`, `dest`, `alternates[]`
- `corridor_nm`, `cruise_levels_ft[]`
- Optional `waypoints[]` can be added later

## Data sources

See [docs/SOURCES.md](docs/SOURCES.md). Sample data is stored under `/data/samples` so the site works immediately.

## Disclaimers

See [docs/DISCLAIMER.md](docs/DISCLAIMER.md) for legal and training use guidance.
