from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.enrich import compute_flags, density_altitude_ft, load_history, qnh_trend, save_history, wind_components
from src.fetch import SampleJsonAdapter, SampleMetarTafAdapter, SampleTextAdapter, SampleUpperWindsAdapter
from src.parse_metar import decode_metar
from src.parse_taf import decode_taf
from src.routes import bearing_deg, ground_speed_estimate, headwind_component
from src.yaml_loader import load_yaml as parse_yaml

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
SAMPLES_DIR = DATA_DIR / "samples"
SIGWX_DIR = DATA_DIR / "sigwx_samples"
HISTORY_DIR = DATA_DIR / "history"


def load_yaml(path: Path) -> dict:
    return parse_yaml(path.read_text(encoding="utf-8"))


def build_aerodromes() -> tuple[list[dict], dict]:
    config = load_yaml(DATA_DIR / "aerodromes.yaml")
    thresholds = config["thresholds"]
    aerodromes = config["aerodromes"]
    adapter = SampleMetarTafAdapter(SAMPLES_DIR)
    results = []

    for aerodrome in aerodromes:
        ident = aerodrome["ident"]
        metar_raw = adapter.fetch_metar(ident)
        taf_raw = adapter.fetch_taf(ident)
        metar_decoded = decode_metar(metar_raw.raw)
        taf_decoded = decode_taf(taf_raw.raw)

        components = []
        for runway in aerodrome["runways"]:
            comp = wind_components(metar_decoded["wind_dir"], metar_decoded["wind_speed_kt"], runway["magnetic_heading_deg"])
            components.append({"runway": runway["designator"], **comp})

        da = density_altitude_ft(aerodrome["elevation_m"], metar_decoded["qnh_hpa"], metar_decoded["temp_c"])
        history = load_history(HISTORY_DIR, ident)
        if metar_decoded["qnh_hpa"]:
            history.append({"timestamp": metar_decoded["observed_time_utc"], "qnh_hpa": metar_decoded["qnh_hpa"]})
        trend = qnh_trend(history)
        save_history(HISTORY_DIR, ident, history)

        flags = compute_flags(
            wind_components_per_runway=components,
            density_altitude=da,
            visibility_m=metar_decoded["vis_m"],
            cloud_layers=metar_decoded["cloud_layers"],
            thresholds=thresholds,
        )

        results.append(
            {
                **aerodrome,
                "metar": metar_decoded | {"source": metar_raw.source},
                "taf": taf_decoded | {"source": taf_raw.source},
                "computed": {
                    "wind_components_per_runway": components,
                    "density_altitude_ft": da["density_altitude_ft"],
                    "density_altitude_m": da["density_altitude_m"],
                    "qnh_trend": trend,
                    "flags": flags,
                },
            }
        )

    return results, thresholds


def build_routes(aerodromes: list[dict]) -> list[dict]:
    routes_config = load_yaml(DATA_DIR / "routes.yaml")
    routes = routes_config["routes"]
    aerodrome_lookup = {item["ident"]: item for item in aerodromes}

    notam_adapter = SampleTextAdapter(SAMPLES_DIR, "notam")
    sigmet_adapter = SampleJsonAdapter(SAMPLES_DIR / "sigmet.json")
    airmet_adapter = SampleJsonAdapter(SAMPLES_DIR / "airmet.json")
    upper_adapter = SampleUpperWindsAdapter(SAMPLES_DIR / "upper_winds.json")

    sigmets = sigmet_adapter.fetch()
    airmets = airmet_adapter.fetch()
    upper = upper_adapter.fetch()

    built_routes = []
    for route in routes:
        dep = aerodrome_lookup.get(route["dep"])
        dest = aerodrome_lookup.get(route["dest"])
        alternates = [aerodrome_lookup[ident] for ident in route.get("alternates", []) if ident in aerodrome_lookup]

        track = None
        if dep and dest:
            track = bearing_deg(dep["latitude_deg"], dep["longitude_deg"], dest["latitude_deg"], dest["longitude_deg"])

        wind_levels = []
        for level in upper["levels"]:
            if level["level_ft"] not in route["cruise_levels_ft"]:
                continue
            if track is None:
                wind_levels.append({**level, "headwind_kt": None, "ground_speed_kt": None})
                continue
            headwind = headwind_component(level["wind_dir_deg"], level["wind_speed_kt"], track)
            gs = ground_speed_estimate(120, level["wind_dir_deg"], level["wind_speed_kt"], track)
            wind_levels.append({**level, "headwind_kt": headwind, "ground_speed_kt": gs})

        freezing_level = None
        for level in upper["levels"]:
            if level["temp_c"] <= 0:
                freezing_level = level["level_ft"]
                break

        icing_possible = any(level["temp_c"] <= 0 for level in wind_levels)
        turbulence_possible = any(item["type"] == "TURB" for item in sigmets)
        convective_risk = any(item["type"] in {"TS", "CB"} for item in sigmets)

        route_flags = []
        if icing_possible:
            route_flags.append("ICING_POSSIBLE (TRAINING)")
        if turbulence_possible:
            route_flags.append("TURB_POSSIBLE (TRAINING)")
        if convective_risk:
            route_flags.append("CONVECTIVE_RISK_HIGH")

        dep_notam = notam_adapter.fetch(route["dep"])
        dest_notam = notam_adapter.fetch(route["dest"])
        built_routes.append(
            {
                **route,
                "dep_data": dep,
                "dest_data": dest,
                "alternate_data": alternates,
                "notams": {
                    "dep": {"ident": dep_notam.ident, "lines": dep_notam.lines, "source": dep_notam.source},
                    "dest": {
                        "ident": dest_notam.ident,
                        "lines": dest_notam.lines,
                        "source": dest_notam.source,
                    },
                },
                "sigmets": sigmets,
                "airmets": airmets,
                "upper_winds": wind_levels,
                "upper_winds_source": upper.get("source", "SAMPLE"),
                "track_deg": track,
                "freezing_level_ft": freezing_level,
                "route_flags": route_flags,
            }
        )

    return built_routes


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def copy_sigwx(site_assets: Path) -> dict:
    site_assets.mkdir(parents=True, exist_ok=True)
    low = SIGWX_DIR / "low_sigwx.svg"
    high = SIGWX_DIR / "high_sigwx.svg"
    low_dest = site_assets / low.name
    high_dest = site_assets / high.name
    low_dest.write_text(low.read_text(encoding="utf-8"), encoding="utf-8")
    high_dest.write_text(high.read_text(encoding="utf-8"), encoding="utf-8")
    return {
        "low": f"assets/{low.name}",
        "high": f"assets/{high.name}",
    }


def build_site() -> None:
    aerodromes, thresholds = build_aerodromes()
    routes = build_routes(aerodromes)
    sigwx_paths = copy_sigwx(SITE_DIR / "assets")

    write_json(SITE_DIR / "api" / "latest.json", {"aerodromes": aerodromes, "routes": routes})
    for aerodrome in aerodromes:
        write_json(SITE_DIR / "api" / f"{aerodrome['ident']}.json", aerodrome)

    for route in routes:
        write_json(SITE_DIR / "api" / "route" / f"{route['route_id']}.json", route)

    (SITE_DIR / "assets").mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "assets" / "style.css").write_text(_style_css(), encoding="utf-8")

    (SITE_DIR / "index.html").write_text(
        render_home(aerodromes, thresholds),
        encoding="utf-8",
    )
    (SITE_DIR / "routes.html").write_text(
        render_routes_index(routes),
        encoding="utf-8",
    )
    for aerodrome in aerodromes:
        (SITE_DIR / "aerodrome").mkdir(parents=True, exist_ok=True)
        (SITE_DIR / "aerodrome" / f"{aerodrome['ident']}.html").write_text(
            render_aerodrome_page(aerodrome),
            encoding="utf-8",
        )

    for route in routes:
        (SITE_DIR / "route").mkdir(parents=True, exist_ok=True)
        (SITE_DIR / "route" / f"{route['route_id']}.html").write_text(
            render_route_page(route, sigwx_paths),
            encoding="utf-8",
        )


def _style_css() -> str:
    return """
:root { font-family: 'Inter', system-ui, sans-serif; color: #111827; }
body { margin: 0; background: #f9fafb; }
header { background: #0f172a; color: #fff; padding: 24px; }
nav a { color: #cbd5f5; margin-right: 16px; text-decoration: none; font-weight: 600; }
nav a.active { color: #fff; border-bottom: 2px solid #38bdf8; padding-bottom: 4px; }
.container { padding: 24px; max-width: 1100px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 8px 24px rgba(15, 23, 42, 0.06); }
.badge { display: inline-block; background: #fee2e2; color: #b91c1c; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; margin-right: 6px; }
.table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.table th, .table td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
.footer { margin-top: 32px; font-size: 12px; color: #6b7280; }
.section { margin-top: 24px; }
.summary { background: #e0f2fe; border-radius: 12px; padding: 16px; }
.flag-list { margin: 8px 0; padding-left: 18px; }
.tag { background: #e2e8f0; color: #334155; border-radius: 6px; padding: 2px 6px; font-size: 12px; margin-right: 4px; }
"""


def render_home(aerodromes: list[dict], thresholds: dict) -> str:
    cards = "".join(
        f"""
        <div class="card">
          <h3>{a['ident']} — {a.get('name','')}</h3>
          <p><strong>METAR:</strong> {a['metar']['observed_time_utc'] or 'Unknown'} ({a['metar']['source']})</p>
          <p>Wind: {a['metar']['wind_dir'] or 'VRB'}° {a['metar']['wind_speed_kt'] or '--'} kt</p>
          <p>QNH: {a['metar']['qnh_hpa'] or '--'} hPa ({a['computed']['qnh_trend']})</p>
          <p>Temp/Dew: {a['metar']['temp_c'] or '--'}°C / {a['metar']['dewpoint_c'] or '--'}°C</p>
          <p>DA: {a['computed']['density_altitude_ft'] or '--'} ft</p>
          <div>
            {''.join(f'<span class="badge">{flag}</span>' for flag in (a['computed']['flags'][:1] or ['NONE']))}
          </div>
          <p><a href="aerodrome/{a['ident']}.html">Open briefing</a></p>
        </div>
        """
        for a in aerodromes
    )

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>METAR.oncloud.africa — Airfields</title>
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>
  <header>
    <h1>METAR.oncloud.africa</h1>
    <p>Training/augmentation only. Not an official briefing source.</p>
    <nav>
      <a class="active" href="index.html">Airfields</a>
      <a href="routes.html">Routes</a>
    </nav>
  </header>
  <main class="container">
    <section class="summary">
      <h2>Airfields overview</h2>
      <p>Thresholds: crosswind ≥ {thresholds['crosswind_high_kt']} kt, tailwind ≥ {thresholds['tailwind_kt']} kt, DA ≥ {thresholds['high_da_ft']} ft.</p>
    </section>
    <section class="section">
      <div class="grid">{cards}</div>
    </section>
    <div class="footer">
      Training/augmentation only. Official briefings remain SAWS/ATC.
    </div>
  </main>
</body>
</html>
"""


def render_routes_index(routes: list[dict]) -> str:
    cards = "".join(
        f"""
        <div class="card">
          <h3>{r['route_id']}</h3>
          <p>{r['dep']} → {r['dest']}</p>
          <p>Corridor: {r['corridor_nm']} NM</p>
          <p>Levels: {', '.join(str(l) for l in r['cruise_levels_ft'])}</p>
          <p><a href="route/{r['route_id']}.html">Open route pack</a></p>
        </div>
        """
        for r in routes
    )

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>METAR.oncloud.africa — Routes</title>
  <link rel="stylesheet" href="assets/style.css" />
</head>
<body>
  <header>
    <h1>METAR.oncloud.africa</h1>
    <p>Training/augmentation only. Not an official briefing source.</p>
    <nav>
      <a href="index.html">Airfields</a>
      <a class="active" href="routes.html">Routes</a>
    </nav>
  </header>
  <main class="container">
    <section class="summary">
      <h2>ATPL route packs</h2>
      <p>Generated from sample data. Each pack includes METAR/TAF, NOTAM highlights, upper winds, SIGMET/AIRMET, and SIGWX charts.</p>
    </section>
    <section class="section">
      <div class="grid">{cards}</div>
    </section>
    <div class="footer">Training/augmentation only. Official briefings remain SAWS/ATC.</div>
  </main>
</body>
</html>
"""


def render_aerodrome_page(a: dict) -> str:
    metar = a["metar"]
    taf = a["taf"]
    runway_rows = "".join(
        f"""
        <tr>
          <td>{c['runway']}</td>
          <td>{c['headwind_kt']}</td>
          <td>{c['crosswind_kt']} ({c['crosswind_direction']})</td>
          <td>{c['tailwind_kt']}</td>
        </tr>
        """
        for c in a["computed"]["wind_components_per_runway"]
    )

    flags = a["computed"]["flags"] or ["NONE"]
    flags_html = "".join(f"<li>{flag}</li>" for flag in flags)

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{a['ident']} briefing</title>
  <link rel="stylesheet" href="../assets/style.css" />
</head>
<body>
  <header>
    <h1>{a['ident']} — {a.get('name','')}</h1>
    <p>Training/augmentation only. Not an official briefing source.</p>
    <nav>
      <a href="../index.html">Airfields</a>
      <a href="../routes.html">Routes</a>
    </nav>
  </header>
  <main class="container">
    <section class="summary">
      <h2>Latest METAR</h2>
      <p>{metar['raw']}</p>
      <p>Observed: {metar['observed_time_utc'] or 'Unknown'} ({metar['source']})</p>
    </section>

    <section class="section">
      <h3>Decoded METAR</h3>
      <table class="table">
        <tr><th>Wind</th><td>{metar['wind_dir'] or 'VRB'}° {metar['wind_speed_kt'] or '--'} kt</td></tr>
        <tr><th>Gust</th><td>{metar['gust_kt'] or '--'} kt</td></tr>
        <tr><th>Visibility</th><td>{metar['vis_m'] or '--'} m</td></tr>
        <tr><th>Temperature</th><td>{metar['temp_c'] or '--'} °C</td></tr>
        <tr><th>Dewpoint</th><td>{metar['dewpoint_c'] or '--'} °C</td></tr>
        <tr><th>QNH</th><td>{metar['qnh_hpa'] or '--'} hPa</td></tr>
      </table>
    </section>

    <section class="section">
      <h3>TAF summary</h3>
      <p>{taf['raw']}</p>
      <p>Valid: {taf['summary']['valid_from']} → {taf['summary']['valid_to']}</p>
      <p>Key changes: {', '.join(taf['summary']['key_changes']) or 'None'}</p>
    </section>

    <section class="section">
      <h3>Runway wind components</h3>
      <table class="table">
        <tr><th>Runway</th><th>Headwind (kt)</th><th>Crosswind (kt)</th><th>Tailwind (kt)</th></tr>
        {runway_rows}
      </table>
    </section>

    <section class="section">
      <h3>Flags</h3>
      <ul class="flag-list">{flags_html}</ul>
    </section>

    <div class="footer">
      Training/augmentation only. Official briefings remain SAWS/ATC.
    </div>
  </main>
</body>
</html>
"""


def render_route_page(route: dict, sigwx_paths: dict) -> str:
    def _metar_line(item: dict | None) -> str:
        if not item:
            return "Unknown"
        return f"{item['ident']}: {item['metar']['raw']}"

    dep = route["dep_data"]
    dest = route["dest_data"]
    alternates = route["alternate_data"]

    metar_rows = "".join(
        f"<tr><td>{item['ident']}</td><td>{item['metar']['raw']}</td>"
        f"<td>{item['metar']['observed_time_utc'] or 'Unknown'} ({item['metar']['source']})</td>"
        f"<td>{item['taf']['raw']}</td></tr>"
        for item in [dep, dest, *alternates]
        if item
    )

    upper_rows = "".join(
        f"<tr><td>{level['level_ft']}</td><td>{level['wind_dir_deg']}/{level['wind_speed_kt']} kt</td><td>{level['temp_c']} °C</td><td>{level['headwind_kt']}</td><td>{level['ground_speed_kt']}</td></tr>"
        for level in route["upper_winds"]
    )

    sigmet_cards = "".join(
        f"<div class='card'><strong>{item['type']}</strong><p>{item['details']}</p><p>{item['valid_from']} → {item['valid_to']}</p><p>{item['area']}</p></div>"
        for item in route["sigmets"]
    )
    airmet_cards = "".join(
        f"<div class='card'><strong>{item['type']}</strong><p>{item['details']}</p><p>{item['valid_from']} → {item['valid_to']}</p><p>{item['area']}</p></div>"
        for item in route["airmets"]
    )

    flags_html = "".join(f"<span class='badge'>{flag}</span>" for flag in route["route_flags"]) or "<span class='tag'>NONE</span>"

    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>{route['route_id']} route pack</title>
  <link rel="stylesheet" href="../assets/style.css" />
</head>
<body>
  <header>
    <h1>Route pack {route['route_id']}</h1>
    <p>Training/augmentation only. Not an official briefing source.</p>
    <nav>
      <a href="../index.html">Airfields</a>
      <a class="active" href="../routes.html">Routes</a>
    </nav>
  </header>
  <main class="container">
    <section class="summary">
      <h2>{route['dep']} → {route['dest']}</h2>
      <p>Track: {route['track_deg'] or 'Unknown'}° | Corridor: {route['corridor_nm']} NM</p>
      <div>{flags_html}</div>
    </section>

    <section class="section">
      <h3>Weather summary</h3>
      <table class="table">
        <tr><th>Aerodrome</th><th>METAR</th><th>METAR time/source</th><th>TAF</th></tr>
        {metar_rows}
      </table>
    </section>

    <section class="section">
      <h3>NOTAM highlights</h3>
      <div class="grid">
        <div class="card"><strong>{route['dep']}</strong><p>{'<br/>'.join(route['notams']['dep']['lines'])}</p><p>Source: {route['notams']['dep']['source']}</p></div>
        <div class="card"><strong>{route['dest']}</strong><p>{'<br/>'.join(route['notams']['dest']['lines'])}</p><p>Source: {route['notams']['dest']['source']}</p></div>
      </div>
    </section>

    <section class="section">
      <h3>Upper winds & temperatures</h3>
      <table class="table">
        <tr><th>Level (ft)</th><th>Wind</th><th>Temp</th><th>Headwind (kt)</th><th>Ground speed (kt)</th></tr>
        {upper_rows}
      </table>
      <p>Freezing level estimate: {route['freezing_level_ft'] or 'Unknown'} ft</p>
    </section>

    <section class="section">
      <h3>SIGMET / AIRMET</h3>
      <div class="grid">{sigmet_cards}{airmet_cards}</div>
    </section>

    <section class="section">
      <h3>SIGWX charts</h3>
      <div class="grid">
        <div class="card"><img src="../{sigwx_paths['low']}" alt="Low-level SIGWX sample" style="width:100%" /></div>
        <div class="card"><img src="../{sigwx_paths['high']}" alt="High-level SIGWX sample" style="width:100%" /></div>
      </div>
    </section>

    <div class="footer">
      Training/augmentation only. Official briefings remain SAWS/ATC. Never use this for go/no-go decisions.
    </div>
  </main>
</body>
</html>
"""


if __name__ == "__main__":
    build_site()
