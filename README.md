# METAR.oncloud.africa

Static aviation briefing and training toolkit for PPL → ATPL. This repository builds a GitHub Pages site and JSON API that decode METAR/TAF, compute runway wind components and density altitude, generate route packs, and provide interactive training tools (ISA, TAS, hypoxia, pressurisation, scenario builder).

> **Training/augmentation only. Not an official briefing source.** Always verify with SAWS/ATC/AIP/NOTAM office and POH/AFM.

## Features

- **Airfields:** METAR/TAF decode, runway wind components, density altitude, night ops badges, and flags tied to training profiles.
- **Routes:** ATPL-style briefing packs with METAR/TAF, NOTAM highlights, SIGMET/AIRMET, winds/temps aloft, and SIGWX charts.
- **Tools:** ISA, altimetry, DA, IAS→TAS, gas laws/hypoxia, pressurisation, aircraft reference, scenario builder.
- **Static output:** `/site` for GitHub Pages and `/site/api` JSON files.
- **Modes:** Training (sample/snapshot) vs Live Awareness (beta). Training is deterministic/reproducible.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m src.build.build_site --mode sample
python -m http.server --directory site 8000
```

Open `http://localhost:8000`.

## Makefile shortcuts

```bash
make build   # build site (auto mode)
make sample  # build site (sample mode)
make test    # unit tests
make lint    # ruff
make serve   # serve /site
```

## Data packs

Country packs live in `data/packs/<COUNTRY>/`. The build merges all pack aerodromes/routes.

- `data/packs/ZA/aerodromes.yaml`
- `data/packs/ZA/routes.yaml`

## Profiles and aircraft

- `data/profiles.yaml` defines Student PPL / PPL / CPL / ATPL minima.
- `data/aircraft.yaml` includes demonstrated crosswind and notes.

## Disclaimers

See [docs/DISCLAIMER.md](docs/DISCLAIMER.md). Data sources are described in [docs/SOURCES.md](docs/SOURCES.md).

## Modes and snapshots

- **Training (Sample/Snapshot):** reproducible data for practice and exam-style scenarios.
- **Live Awareness (BETA):** METAR/TAF pulled from AviationWeather.gov with a 5-minute cache; other products still fall back to sample data.
- Snapshots are generated via GitHub Actions workflow_dispatch and stored under `/site/api/snapshots` with a matching `/site/snapshot/<id>.html`.

Workload and stability scores are training aids only; see `docs/DATA_MODEL.md` for details. Route packs are evaluated using the ATPL profile to reflect airline-level minima.
