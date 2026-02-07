from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.adapters.sample_metar_taf import SampleMetarTafAdapter
from src.adapters.sample_notam import SampleNotamAdapter
from src.adapters.sample_sigmet import SampleSigmetAdapter
from src.adapters.sample_sigwx import SampleSigwxAdapter
from src.adapters.sample_winds_temps import SampleWindsTempsAdapter
from src.build.render_html import (
    render_airfield_page,
    render_home,
    render_route_page,
    render_routes_index,
    render_tool_page,
    render_tools_index,
)
from src.build.render_json import write_json
from src.build.schema_validate import validate_all
from src.compute.cloud_base import cloud_base_ft
from src.compute.density_altitude import density_altitude
from src.compute.risk_flags import flag_severity
from src.compute.route import bearing_deg, ground_speed_estimate, headwind_component
from src.compute.wind_components import wind_components
from src.parsers.metar import decode_metar
from src.parsers.notam import decode_notam
from src.parsers.sigmet import decode_sigmet
from src.parsers.taf import decode_taf
from src.yaml_loader import load_yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PACKS_DIR = DATA_DIR / "packs"
SAMPLES_DIR = DATA_DIR / "samples"
SITE_DIR = ROOT / "site"
HISTORY_DIR = DATA_DIR / "history"


def load_yaml_file(path: Path) -> dict:
    return load_yaml(path.read_text(encoding="utf-8"))


def load_packs() -> tuple[list[dict], list[dict]]:
    aerodromes: dict[str, dict] = {}
    routes: list[dict] = []

    for pack_path in sorted(PACKS_DIR.glob("*/aerodromes.yaml")):
        data = load_yaml_file(pack_path)
        for item in data.get("aerodromes", []):
            aerodromes[item["ident"]] = item

    for route_path in sorted(PACKS_DIR.glob("*/routes.yaml")):
        data = load_yaml_file(route_path)
        routes.extend(data.get("routes", []))

    if (DATA_DIR / "aerodromes.yaml").exists():
        data = load_yaml_file(DATA_DIR / "aerodromes.yaml")
        for item in data.get("aerodromes", []):
            aerodromes.setdefault(item["ident"], item)

    if (DATA_DIR / "routes.yaml").exists():
        data = load_yaml_file(DATA_DIR / "routes.yaml")
        routes.extend(data.get("routes", []))

    return list(aerodromes.values()), routes


def load_profiles() -> list[dict]:
    return load_yaml_file(DATA_DIR / "profiles.yaml")["profiles"]


def load_aircraft() -> list[dict]:
    return load_yaml_file(DATA_DIR / "aircraft.yaml")["aircraft"]


def load_history(ident: str) -> list[dict]:
    path = HISTORY_DIR / f"{ident}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_history(ident: str, history: list[dict]) -> None:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    path = HISTORY_DIR / f"{ident}.json"
    path.write_text(json.dumps(history[-200:], indent=2), encoding="utf-8")


def qnh_trend(history: list[dict]) -> str:
    if len(history) < 2:
        return "steady"
    prev = history[-2]
    curr = history[-1]
    if not prev.get("qnh_hpa") or not curr.get("qnh_hpa"):
        return "steady"
    delta = curr["qnh_hpa"] - prev["qnh_hpa"]
    if delta > 1:
        return "rising"
    if delta < -1:
        return "falling"
    return "steady"


def qnh_falling_fast(history: list[dict], threshold: float) -> bool:
    if len(history) < 2:
        return False
    prev = history[-2]
    curr = history[-1]
    if not prev.get("qnh_hpa") or not curr.get("qnh_hpa"):
        return False
    delta = curr["qnh_hpa"] - prev["qnh_hpa"]
    return delta <= -threshold


def compute_flags(metar: dict, da: dict, components: list[dict], profile: dict, trend_fast: bool) -> list[str]:
    flags: list[str] = []
    thresholds = profile["thresholds"]

    crosswind_limit = thresholds["max_crosswind_kt"]
    tailwind_limit = thresholds["max_tailwind_kt"]
    gust_spread_limit = thresholds["max_gust_spread_kt"]
    max_da = thresholds["max_da_ft"]
    min_vis = thresholds["min_vis_m"]
    min_ceiling = thresholds["min_ceiling_ft"]

    crosswind = max((c["crosswind_kt"] or 0 for c in components), default=0)
    tailwind = max((c["tailwind_kt"] or 0 for c in components), default=0)

    if crosswind > crosswind_limit:
        flags.append("CROSSWIND_HIGH")
    if tailwind > tailwind_limit:
        flags.append("TAILWIND")

    if metar.get("gust_kt") and metar.get("wind_speed_kt"):
        gust_spread = metar["gust_kt"] - metar["wind_speed_kt"]
        if gust_spread > gust_spread_limit:
            flags.append("GUSTY")

    if da.get("da_ft") and da["da_ft"] > max_da:
        flags.append("HIGH_DA")

    if metar.get("visibility_m") is not None and metar["visibility_m"] < min_vis:
        flags.append("LOW_VIS")

    ceiling = metar.get("ceiling_ft")
    if ceiling is not None and ceiling < min_ceiling:
        flags.append("LOW_CEILING")

    if any("TS" in code for code in metar.get("weather_codes", [])):
        flags.append("TS_RISK")

    if trend_fast:
        flags.append("QNH_FALLING_FAST")

    return flags


def night_ready(airfield: dict) -> bool:
    lighting = airfield.get("lighting", {})
    return airfield.get("night_ops_allowed") == "yes" and lighting.get("runway_edge") == "yes"


def build_airfields(mode: str) -> tuple[list[dict], dict, list[dict]]:
    profiles = load_profiles()
    default_profile = next((p for p in profiles if p["licence_tier"] == "PPL"), profiles[0])

    aerodromes, _ = load_packs()
    metar_adapter = SampleMetarTafAdapter(SAMPLES_DIR / "metar", SAMPLES_DIR / "taf")

    airfields = []
    for airfield in aerodromes:
        ident = airfield["ident"]
        metar_raw = metar_adapter.fetch_metar(ident)
        taf_raw = metar_adapter.fetch_taf(ident)
        metar_decoded = decode_metar(metar_raw.raw)
        taf_decoded = decode_taf(taf_raw.raw)

        components = []
        for runway in airfield["runways"]:
            comp = wind_components(metar_decoded["wind_dir_deg"], metar_decoded["wind_speed_kt"], runway["magnetic_heading_deg"])
            components.append({"runway": runway["designator"], **comp})

        da = density_altitude(airfield["elevation_m"], metar_decoded["qnh_hpa"], metar_decoded["temp_c"])
        ceiling_est = metar_decoded.get("ceiling_ft") or cloud_base_ft(metar_decoded.get("temp_c"), metar_decoded.get("dewpoint_c"))

        history = load_history(ident)
        history.append(
            {
                "timestamp": metar_decoded["observed_time_utc"],
                "wind_speed_kt": metar_decoded["wind_speed_kt"],
                "wind_dir_deg": metar_decoded["wind_dir_deg"],
                "qnh_hpa": metar_decoded["qnh_hpa"],
                "temp_c": metar_decoded["temp_c"],
                "dewpoint_c": metar_decoded["dewpoint_c"],
                "visibility_m": metar_decoded["visibility_m"],
                "ceiling_ft_est": ceiling_est,
            }
        )
        save_history(ident, history)
        trend_fast = qnh_falling_fast(history, default_profile["thresholds"]["qnh_fall_fast_hpa_per_hr"])
        flags = compute_flags(metar_decoded, da, components, default_profile, trend_fast)
        severity = flag_severity(flags, default_profile.get("severity", {}))

        airfields.append(
            {
                **airfield,
                "night_ops": {
                    "night_ops_allowed": airfield["night_ops_allowed"],
                    "lighting": airfield["lighting"],
                    "ppr_required": airfield["ppr_required"],
                    "ops_hours": airfield["ops_hours"],
                    "notes": airfield["notes"],
                },
                "night_ready": night_ready(airfield),
                "metar": metar_decoded | {"source": metar_raw.source},
                "taf": taf_decoded | {"source": taf_raw.source},
                "computed": {
                    "wind_components_per_runway": components,
                    "density_altitude": da,
                    "qnh_trend": qnh_trend(history),
                    "flags": flags,
                    "severity": severity,
                    "trends": {
                        "wind_speed": [item.get("wind_speed_kt") for item in history][-20:],
                        "qnh": [item.get("qnh_hpa") for item in history][-20:],
                        "temp": [item.get("temp_c") for item in history][-20:],
                    },
                },
            }
        )

    return airfields, default_profile, profiles


def build_routes(airfields: list[dict], profile: dict) -> list[dict]:
    _, routes = load_packs()
    airfield_map = {airfield["ident"]: airfield for airfield in airfields}

    notam_adapter = SampleNotamAdapter(SAMPLES_DIR / "notam")
    sigmet_adapter = SampleSigmetAdapter(SAMPLES_DIR / "sigmet" / "sigmet.txt")
    winds_adapter = SampleWindsTempsAdapter(SAMPLES_DIR / "winds_temps" / "winds_temps.json")

    sigmet_lines = sigmet_adapter.fetch()
    sigmet_decoded = decode_sigmet(sigmet_lines)
    winds = winds_adapter.fetch()

    built_routes = []
    for route in routes:
        dep = airfield_map.get(route["dep"])
        dest = airfield_map.get(route["dest"])
        alternates = [airfield_map[ident] for ident in route.get("alternates", []) if ident in airfield_map]

        track = None
        if dep and dest:
            track = bearing_deg(dep["latitude_deg"], dep["longitude_deg"], dest["latitude_deg"], dest["longitude_deg"])

        wind_levels = []
        for level in winds["levels"]:
            if level["level_ft"] not in route["cruise_levels_ft"]:
                continue
            if track is None:
                wind_levels.append({**level, "headwind_kt": None, "ground_speed_kt": None})
                continue
            headwind = headwind_component(level["wind_dir_deg"], level["wind_speed_kt"], track)
            gs = ground_speed_estimate(120, level["wind_dir_deg"], level["wind_speed_kt"], track)
            wind_levels.append({**level, "headwind_kt": headwind, "ground_speed_kt": gs})

        freezing_level = None
        for level in winds["levels"]:
            if level["temp_c"] <= 0:
                freezing_level = level["level_ft"]
                break

        convective_risk = any("TS" in line for line in sigmet_lines)
        turbulence_risk = any("TURB" in line for line in sigmet_lines)
        icing_possible = any(0 >= level["temp_c"] >= -20 for level in wind_levels)

        flags = []
        if convective_risk:
            flags.append("CONVECTIVE_RISK_HIGH")
        if turbulence_risk:
            flags.append("TURB_POSSIBLE (TRAINING)")
        if icing_possible:
            flags.append("ICING_POSSIBLE (TRAINING)")

        severity = flag_severity(flags, profile.get("severity", {}))

        notams = {
            route["dep"]: decode_notam(notam_adapter.fetch(route["dep"]).lines),
            route["dest"]: decode_notam(notam_adapter.fetch(route["dest"]).lines),
        }

        built_routes.append(
            {
                **route,
                "airfields": [item for item in [dep, dest, *alternates] if item],
                "track_deg": track,
                "upper_winds": wind_levels,
                "freezing_level_ft": freezing_level,
                "sigmet_lines": [item["raw"] for item in sigmet_decoded],
                "notams": {ident: [entry["text"] for entry in entries] for ident, entries in notams.items()},
                "summary": {
                    "flags": flags,
                    "severity": severity,
                },
            }
        )

    return built_routes


def copy_sigwx(sigwx: dict) -> dict:
    assets_dir = SITE_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    low_dest = assets_dir / sigwx["low"].name
    high_dest = assets_dir / sigwx["high"].name
    low_dest.write_text(sigwx["low"].read_text(encoding="utf-8"), encoding="utf-8")
    high_dest.write_text(sigwx["high"].read_text(encoding="utf-8"), encoding="utf-8")
    return {"low": sigwx["low"].name, "high": sigwx["high"].name}


def write_assets() -> None:
    assets_dir = SITE_DIR / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "style.css").write_text(_style_css(), encoding="utf-8")
    (assets_dir / "app.js").write_text(_app_js(), encoding="utf-8")


def build_tools_pages() -> None:
    tools_dir = SITE_DIR / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    (tools_dir / "index.html").write_text(render_tools_index(), encoding="utf-8")

    isa_content = """
    <label>Altitude (ft) <input id="isa-alt" type="number" value="5000" /></label>
    <label>OAT (°C) <input id="isa-oat" type="number" value="15" /></label>
    <button data-action="calc-isa">Calculate</button>
    <div id="isa-output" class="result"></div>
    """

    altimetry_content = """
    <label>Field elevation (m) <input id="alt-elev" type="number" value="1500" /></label>
    <label>QNH (hPa) <input id="alt-qnh" type="number" value="1013" /></label>
    <button data-action="calc-altimetry">Calculate</button>
    <div id="alt-output" class="result"></div>
    <p class="note">Use AIP for transition altitude/level.</p>
    """

    da_content = """
    <label>Elevation (m) <input id="da-elev" type="number" value="1500" /></label>
    <label>QNH (hPa) <input id="da-qnh" type="number" value="1013" /></label>
    <label>OAT (°C) <input id="da-oat" type="number" value="20" /></label>
    <button data-action="calc-da">Calculate</button>
    <div id="da-output" class="result"></div>
    """

    tas_content = """
    <label>IAS (kt) <input id="tas-ias" type="number" value="100" /></label>
    <label>Altitude (ft) <input id="tas-alt" type="number" value="8000" /></label>
    <label>ISA deviation (°C) <input id="tas-dev" type="number" value="0" /></label>
    <button data-action="calc-tas">Calculate</button>
    <div id="tas-output" class="result"></div>
    """

    hypoxia_content = """
    <label>Altitude (ft) <input id="hypoxia-alt" type="number" value="12000" /></label>
    <button data-action="calc-hypoxia">Calculate</button>
    <div id="hypoxia-output" class="result"></div>
    <p class="note">Includes Boyle/Dalton/Gay-Lussac/Charles law notes.</p>
    """

    press_content = """
    <label>Cruise level (ft) <input id="press-cruise" type="number" value="25000" /></label>
    <label>Destination elevation (ft) <input id="press-dest" type="number" value="1500" /></label>
    <label>Cabin rate (fpm) <input id="press-rate" type="number" value="500" /></label>
    <label>Max differential (psi) <input id="press-diff" type="number" value="7" /></label>
    <button data-action="calc-press">Calculate</button>
    <div id="press-output" class="result"></div>
    """

    aircraft_content = """
    <div id="aircraft-list"></div>
    """

    scenario_content = """
    <label>Profile <select id="scenario-profile"></select></label>
    <label>Airfield <select id="scenario-airfield"></select></label>
    <label>Route <select id="scenario-route"></select></label>
    <label>Aircraft <select id="scenario-aircraft"></select></label>
    <button data-action="build-scenario">Build briefing card</button>
    <div id="scenario-output" class="result"></div>
    """

    (tools_dir / "isa.html").write_text(render_tool_page("ISA Tool", isa_content), encoding="utf-8")
    (tools_dir / "altimetry.html").write_text(render_tool_page("Altimetry Tool", altimetry_content), encoding="utf-8")
    (tools_dir / "density-altitude.html").write_text(render_tool_page("Density Altitude Tool", da_content), encoding="utf-8")
    (tools_dir / "tas.html").write_text(render_tool_page("IAS → TAS Tool", tas_content), encoding="utf-8")
    (tools_dir / "hypoxia.html").write_text(render_tool_page("Gas laws & Hypoxia", hypoxia_content), encoding="utf-8")
    (tools_dir / "pressurisation.html").write_text(render_tool_page("Pressurisation Simulator", press_content), encoding="utf-8")
    (tools_dir / "aircraft.html").write_text(render_tool_page("Training Aircraft Reference", aircraft_content), encoding="utf-8")
    (tools_dir / "scenario.html").write_text(render_tool_page("Scenario Builder", scenario_content), encoding="utf-8")


def build_site(mode: str = "sample") -> None:
    validate_all()

    airfields, default_profile, profiles = build_airfields(mode)
    routes = build_routes(airfields, default_profile)

    sigwx_adapter = SampleSigwxAdapter(SAMPLES_DIR / "sigwx")
    sigwx_paths = copy_sigwx(sigwx_adapter.fetch())

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    write_assets()
    build_tools_pages()

    (SITE_DIR / "index.html").write_text(render_home(airfields, default_profile["name"]), encoding="utf-8")
    (SITE_DIR / "routes.html").write_text(render_routes_index(routes), encoding="utf-8")

    airfield_dir = SITE_DIR / "airfield"
    airfield_dir.mkdir(parents=True, exist_ok=True)
    for airfield in airfields:
        (airfield_dir / f"{airfield['ident']}.html").write_text(render_airfield_page(airfield), encoding="utf-8")

    route_dir = SITE_DIR / "route"
    route_dir.mkdir(parents=True, exist_ok=True)
    for route in routes:
        (route_dir / f"{route['route_id']}.html").write_text(render_route_page(route, sigwx_paths), encoding="utf-8")

    write_json(SITE_DIR / "api" / "latest.json", {"airfields": airfields, "routes": routes})
    write_json(SITE_DIR / "api" / "profiles.json", profiles)
    write_json(SITE_DIR / "api" / "aircraft.json", load_aircraft())

    for airfield in airfields:
        write_json(SITE_DIR / "api" / "airfield" / f"{airfield['ident']}.json", airfield)
    for route in routes:
        write_json(SITE_DIR / "api" / "route" / f"{route['route_id']}.json", route)


def _style_css() -> str:
    return """
:root { font-family: 'Inter', system-ui, sans-serif; color: #0f172a; }
body { margin: 0; background: #f8fafc; }
header { background: #0f172a; color: #fff; padding: 20px; }
nav a { color: #cbd5f5; margin-right: 16px; text-decoration: none; font-weight: 600; }
nav a.active { color: #fff; border-bottom: 2px solid #38bdf8; padding-bottom: 4px; }
.container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; }
.card { background: #fff; border-radius: 12px; padding: 16px; box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08); }
.card-header { display: flex; justify-content: space-between; align-items: center; }
.badge-row { display: flex; gap: 8px; margin: 8px 0; }
.badge { display: inline-block; background: #e2e8f0; color: #1e293b; padding: 4px 8px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.badge.night { background: #c7d2fe; }
.pill { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: 700; }
.icon { font-size: 10px; }
.status-ok { background: #e0f2fe; color: #0f172a; }
.status-caution { background: #fef3c7; color: #92400e; }
.status-warning { background: #fee2e2; color: #991b1b; }
.status-unknown { background: #e5e7eb; color: #374151; }
.summary { background: #e0f2fe; border-radius: 12px; padding: 16px; }
.table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.table th, .table td { text-align: left; padding: 8px; border-bottom: 1px solid #e5e7eb; font-size: 14px; }
.section { margin-top: 24px; }
.flag-list { margin: 8px 0; padding-left: 18px; }
.note { font-size: 13px; color: #475569; }
.result { margin-top: 12px; padding: 12px; background: #f1f5f9; border-radius: 8px; }
footer { padding: 24px; text-align: center; font-size: 12px; color: #475569; }
input, select { padding: 6px 8px; margin: 6px 8px 6px 0; }
button { padding: 6px 10px; background: #0ea5e9; color: #fff; border: none; border-radius: 6px; cursor: pointer; }
"""


def _app_js() -> str:
    return """
const toNumber = (id) => parseFloat(document.getElementById(id).value || 0);
const basePath = document.querySelector('meta[name=\"base-path\"]')?.getAttribute('content') || '';

function isaTemp(altFt) { return 15 - 2 * (altFt / 1000); }

document.addEventListener('click', (event) => {
  const action = event.target.getAttribute('data-action');
  if (!action) return;

  if (action === 'calc-isa') {
    const alt = toNumber('isa-alt');
    const oat = toNumber('isa-oat');
    const isa = isaTemp(alt);
    const dev = (oat - isa).toFixed(1);
    document.getElementById('isa-output').textContent = `ISA temp: ${isa.toFixed(1)}°C | ISA deviation: ${dev}°C`;
  }
  if (action === 'calc-altimetry') {
    const elevM = toNumber('alt-elev');
    const qnh = toNumber('alt-qnh');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    document.getElementById('alt-output').textContent = `Pressure altitude: ${pressureAlt.toFixed(0)} ft (${(pressureAlt/3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-da') {
    const elevM = toNumber('da-elev');
    const qnh = toNumber('da-qnh');
    const oat = toNumber('da-oat');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    const isa = isaTemp(pressureAlt);
    const da = pressureAlt + 120 * (oat - isa);
    document.getElementById('da-output').textContent = `Density altitude: ${da.toFixed(0)} ft (${(da/3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-tas') {
    const ias = toNumber('tas-ias');
    const alt = toNumber('tas-alt');
    const dev = toNumber('tas-dev');
    const tas = ias * (1 + alt / 1000 * 0.02) * (1 + dev / 100);
    document.getElementById('tas-output').textContent = `Estimated TAS: ${tas.toFixed(1)} kt (training approximation)`;
  }
  if (action === 'calc-hypoxia') {
    const alt = toNumber('hypoxia-alt');
    const index = Math.max(10, 100 - alt / 300);
    document.getElementById('hypoxia-output').textContent = `Oxygen index: ${index.toFixed(1)} (training scale). Beware trapped gas at altitude.`;
  }
  if (action === 'calc-press') {
    const cruise = toNumber('press-cruise');
    const dest = toNumber('press-dest');
    const rate = toNumber('press-rate');
    const diff = toNumber('press-diff');
    const cabin = Math.min(cruise * 0.6, dest + diff * 2000);
    document.getElementById('press-output').textContent = `Estimated cabin altitude: ${cabin.toFixed(0)} ft at ${rate} fpm (training only)`;
  }
  if (action === 'build-scenario') {
    buildScenarioCard();
  }
});

function filterCards(inputId, selector) {
  const input = document.getElementById(inputId);
  if (!input) return;
  input.addEventListener('input', () => {
    const term = input.value.toLowerCase();
    document.querySelectorAll(selector).forEach(card => {
      const text = card.textContent.toLowerCase();
      card.style.display = text.includes(term) ? 'block' : 'none';
    });
  });
}

filterCards('airfield-search', '.card[data-ident]');
filterCards('route-search', '.card[data-route]');

async function buildScenarioCard() {
  const profileId = document.getElementById('scenario-profile').value;
  const airfieldId = document.getElementById('scenario-airfield').value;
  const routeId = document.getElementById('scenario-route').value;
  const aircraftId = document.getElementById('scenario-aircraft').value;

  const latest = await fetch(`${basePath}api/latest.json`).then(r => r.json());
  const profiles = await fetch(`${basePath}api/profiles.json`).then(r => r.json());
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());

  const profile = profiles.find(p => p.name === profileId);
  const aircraftInfo = aircraft.find(a => a.type === aircraftId);
  const airfield = latest.airfields.find(a => a.ident === airfieldId);
  const route = latest.routes.find(r => r.route_id === routeId);

  const output = document.getElementById('scenario-output');
  const title = route ? `Route ${route.route_id}` : `Airfield ${airfield.ident}`;
  const flags = route ? route.summary.flags : airfield.computed.flags;
  const da = airfield ? airfield.computed.density_altitude.da_ft : '—';

  output.innerHTML = `
    <h4>${title}</h4>
    <p><strong>Profile:</strong> ${profile ? profile.name : ''}</p>
    <p><strong>Aircraft:</strong> ${aircraftInfo ? aircraftInfo.type : ''} (${aircraftInfo ? aircraftInfo.demonstrated_crosswind_kt : ''} kt demo crosswind)</p>
    <p><strong>Density altitude:</strong> ${da} ft</p>
    <p><strong>Flags:</strong> ${flags.join(', ') || 'LOW_RISK'}</p>
    <p><strong>Questions:</strong> How will crosswind/tailwind affect your performance? Are you within personal minima?</p>
  `;
}

async function populateScenario() {
  const latest = await fetch(`${basePath}api/latest.json`).then(r => r.json());
  const profiles = await fetch(`${basePath}api/profiles.json`).then(r => r.json());
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());

  const profileSelect = document.getElementById('scenario-profile');
  const airfieldSelect = document.getElementById('scenario-airfield');
  const routeSelect = document.getElementById('scenario-route');
  const aircraftSelect = document.getElementById('scenario-aircraft');

  if (profileSelect) {
    profiles.forEach(p => profileSelect.add(new Option(p.name, p.name)));
    latest.airfields.forEach(a => airfieldSelect.add(new Option(a.ident, a.ident)));
    latest.routes.forEach(r => routeSelect.add(new Option(r.route_id, r.route_id)));
    aircraft.forEach(a => aircraftSelect.add(new Option(a.type, a.type)));
  }
}

populateScenario();

async function populateAircraft() {
  const container = document.getElementById('aircraft-list');
  if (!container) return;
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());
  container.innerHTML = aircraft.map(a => `<div class="card"><h4>${a.type}</h4><p>Demo crosswind: ${a.demonstrated_crosswind_kt} kt</p><p>${a.notes}</p></div>`).join('');
}

populateAircraft();
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="sample", choices=["sample", "auto"], help="Sample mode only")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    build_site(args.mode)
