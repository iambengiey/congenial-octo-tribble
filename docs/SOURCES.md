# Data Sources

## METAR / TAF
- **Mode:** Sample data (stored under `/data/samples`).
<<<<<<< HEAD
- **Live adapter:** `src/adapters/live_metar_taf.py` uses aviationweather.gov (beta). Falls back to sample on failure.

## NOTAM / SIGMET / AIRMET
- **Mode:** Sample data in `/data/samples/notam` and `/data/samples/sigmet`.
- **Live adapter:** Stub classes under `src/adapters/live_stub_*`.

## Upper winds / temperatures
- **Mode:** Sample data in `/data/samples/winds_temps`.
- **Live adapter:** Stub classes under `src/adapters/live_stub_*`.
=======
- **Live adapter:** AviationWeather.gov raw endpoints with a 5-minute cache in `/data/live_cache`.

## NOTAM / SIGMET / AIRMET
- **Mode:** Sample data in `/data/samples/notam` and `/data/samples/sigmet`.
- **Live adapter:** Not yet implemented; sample data is used as fallback.

## Upper winds / temperatures
- **Mode:** Sample data in `/data/samples/winds_temps`.
- **Live adapter:** Not yet implemented; sample data is used as fallback.
>>>>>>> main

## SIGWX charts
- **Mode:** Sample SVG charts in `/data/samples/sigwx`.

> Official briefing sources remain SAWS/ATC. This project is for training/augmentation only.
