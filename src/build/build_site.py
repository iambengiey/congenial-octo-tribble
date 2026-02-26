from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path

from src.adapters.live_metar_taf import LiveMetarTafAdapter
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
from src.compute.change_detection import detect_changes
from src.compute.cloud_base import cloud_base_ft
from src.compute.compound_flags import compound_flags
from src.compute.density_altitude import density_altitude
from src.compute.route import bearing_deg, ground_speed_estimate, headwind_component
from src.compute.risk_flags import flag_severity
from src.compute.stability import stability_score
from src.compute.sun import civil_twilight, is_night, sun_times
from src.compute.workload import workload_score
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


def _parse_iso(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))


def hours_between(prev_ts: str | None, curr_ts: str | None) -> float | None:
    prev = _parse_iso(prev_ts)
    curr = _parse_iso(curr_ts)
    if not prev or not curr:
        return None
    delta = curr - prev
    return max(delta.total_seconds() / 3600.0, 0.0)


def parse_taf_valid_to(valid_to: str, reference: dt.datetime) -> dt.datetime | None:
    if not valid_to or len(valid_to) != 4:
        return None
    day = int(valid_to[:2])
    hour = int(valid_to[2:])
    month = reference.month
    year = reference.year
    if day < reference.day:
        month = month + 1 if month < 12 else 1
        year = year + 1 if month == 1 else year
    return dt.datetime(year, month, day, hour, 0, tzinfo=dt.timezone.utc)


def time_to_expiry(end_time: dt.datetime | None, now: dt.datetime) -> dict:
    if not end_time:
        return {"hours": None, "urgency": "unknown"}
    hours = (end_time - now).total_seconds() / 3600.0
    urgency = "ok"
    if hours <= 1:
        urgency = "red"
    elif hours <= 2:
        urgency = "amber"
    return {"hours": round(hours, 1), "urgency": urgency}


def build_mode_info(mode: str) -> dict:
    if mode == "live_beta":
        return {
            "label": "LIVE (BETA)",
            "text": "Not an official briefing source",
            "class": "mode-live",
        }
    return {
        "label": "TRAINING (Sample)",
        "text": "Reproducible training data",
        "class": "mode-training",
    }


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


def compute_flags(
    metar: dict,
    da: dict,
    components: list[dict],
    profile: dict,
    trend_fast: bool,
) -> tuple[list[str], dict]:
    flags: list[str] = []
    explanations: dict[str, dict] = {}
    thresholds = profile["thresholds"]

    crosswind_limit = thresholds["max_crosswind_kt"]
    tailwind_limit = thresholds["max_tailwind_kt"]
    gust_spread_limit = thresholds["max_gust_spread_kt"]
    max_da = thresholds["max_da_ft"]
    min_vis = thresholds["min_vis_m"]
    min_ceiling = thresholds["min_ceiling_ft"]

    max_crosswind_comp = max(components, key=lambda c: c["crosswind_kt"] or 0, default=None)
    max_tailwind_comp = max(components, key=lambda c: c["tailwind_kt"] or 0, default=None)
    crosswind = max((c["crosswind_kt"] or 0 for c in components), default=0)
    tailwind = max((c["tailwind_kt"] or 0 for c in components), default=0)

    if crosswind > crosswind_limit:
        flags.append("CROSSWIND_HIGH")
        explanations["CROSSWIND_HIGH"] = {
            "input": f"{metar.get('wind_dir_deg')}/{metar.get('wind_speed_kt')}kt",
            "runway": max_crosswind_comp.get("runway") if max_crosswind_comp else None,
            "crosswind_kt": crosswind,
            "threshold_kt": crosswind_limit,
            "note": "Crosswind affects controllability; headwind is typically helpful.",
        }
    if tailwind > tailwind_limit:
        flags.append("TAILWIND")
        explanations["TAILWIND"] = {
            "input": f"{metar.get('wind_dir_deg')}/{metar.get('wind_speed_kt')}kt",
            "runway": max_tailwind_comp.get("runway") if max_tailwind_comp else None,
            "tailwind_kt": tailwind,
            "threshold_kt": tailwind_limit,
            "note": "Tailwind reduces performance and increases landing distance.",
        }

    if metar.get("gust_kt") and metar.get("wind_speed_kt"):
        gust_spread = metar["gust_kt"] - metar["wind_speed_kt"]
        if gust_spread > gust_spread_limit:
            flags.append("GUSTY")
            explanations["GUSTY"] = {
                "gust_spread_kt": gust_spread,
                "threshold_kt": gust_spread_limit,
                "note": "Gust spread increases workload and variability.",
            }

    if da.get("da_ft") and da["da_ft"] > max_da:
        flags.append("HIGH_DA")
        explanations["HIGH_DA"] = {
            "density_altitude_ft": da["da_ft"],
            "threshold_ft": max_da,
            "note": "High DA reduces aircraft performance.",
        }

    if metar.get("visibility_m") is not None and metar["visibility_m"] < min_vis:
        flags.append("LOW_VIS")
        explanations["LOW_VIS"] = {
            "visibility_m": metar["visibility_m"],
            "threshold_m": min_vis,
            "note": "Visibility below training minima.",
        }

    ceiling = metar.get("ceiling_ft")
    if ceiling is not None and ceiling < min_ceiling:
        flags.append("LOW_CEILING")
        explanations["LOW_CEILING"] = {
            "ceiling_ft": ceiling,
            "threshold_ft": min_ceiling,
            "note": "Ceiling below training minima.",
        }

    if any("TS" in code for code in metar.get("weather_codes", [])):
        flags.append("TS_RISK")
        explanations["TS_RISK"] = {
            "note": "Thunderstorm code in METAR.",
            "input": metar.get("weather_codes", []),
        }

    if trend_fast:
        flags.append("QNH_FALLING_FAST")
        explanations["QNH_FALLING_FAST"] = {
            "threshold_hpa_per_hr": thresholds["qnh_fall_fast_hpa_per_hr"],
            "note": "Rapid QNH fall can indicate deteriorating conditions.",
        }

    return flags, explanations


def night_ready(airfield: dict) -> bool:
    lighting = airfield.get("lighting", {})
    return airfield.get("night_ops_allowed") == "yes" and lighting.get("runway_edge") == "yes"


def _build_metar_taf_adapter(mode: str) -> tuple[SampleMetarTafAdapter, LiveMetarTafAdapter | None]:
    sample = SampleMetarTafAdapter(SAMPLES_DIR / "metar", SAMPLES_DIR / "taf")
    if mode == "live_beta":
        return sample, LiveMetarTafAdapter()
    return sample, None


def _source_detail(label: str) -> str:
    if label == "LIVE_BETA":
        return "AviationWeather.gov (NOAA)"
    if label == "SAMPLE_FALLBACK":
        return "Bundled training samples"
    return "Bundled training samples"


def _runway_condition_from_notams(runway_ident: str, notam_lines: list[str]) -> str:
    text = " ".join(notam_lines).upper()
    runway_key = runway_ident.upper().replace(" ", "")
    runway_scope = runway_key in text

    condition_keywords = [
        ("CLOSED", "Closed"),
        ("CLSD", "Closed"),
        ("WET", "Wet"),
        ("WATER", "Standing water reported"),
        ("SNOW", "Contaminated (snow)"),
        ("ICE", "Icy"),
        ("RUBBER", "Rubber deposits reported"),
        ("BRAKING ACTION", "Braking action advisory"),
    ]
    for keyword, label in condition_keywords:
        if keyword in text and (runway_scope or "RWY" in text or "RUNWAY" in text):
            return label
    return "Not reported"


def _fetch_with_fallback(
    ident: str,
    adapter: LiveMetarTafAdapter | None,
    fallback: SampleMetarTafAdapter,
    kind: str,
) -> tuple[dict, str]:
    try:
        if adapter:
            if kind == "metar":
                return adapter.fetch_metar(ident), "LIVE_BETA"
            return adapter.fetch_taf(ident), "LIVE_BETA"
    except Exception:
        pass
    if kind == "metar":
        return fallback.fetch_metar(ident), "SAMPLE_FALLBACK"
    return fallback.fetch_taf(ident), "SAMPLE_FALLBACK"


def build_airfields(mode: str, record_history: bool = True) -> tuple[list[dict], dict, list[dict]]:
    profiles = load_profiles()
    default_profile = next((p for p in profiles if p["licence_tier"] == "PPL"), profiles[0])

    aerodromes, _ = load_packs()
    sample_adapter, live_adapter = _build_metar_taf_adapter(mode)
    notam_adapter = SampleNotamAdapter(SAMPLES_DIR / "notam")

    airfields = []
    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    for airfield in aerodromes:
        ident = airfield["ident"]
        metar_raw, metar_source = _fetch_with_fallback(ident, live_adapter, sample_adapter, "metar")
        taf_raw, taf_source = _fetch_with_fallback(ident, live_adapter, sample_adapter, "taf")
        try:
            notam_entries = decode_notam(notam_adapter.fetch(ident).lines)
        except FileNotFoundError:
            notam_entries = []
        notam_lines = [entry["text"] for entry in notam_entries]
        metar_decoded = decode_metar(metar_raw.raw)
        if mode == "live_beta":
            fetch_time = now.isoformat().replace("+00:00", "Z")
            obs_time = _parse_iso(metar_decoded.get("observed_time_utc"))
            latency = round((now - obs_time).total_seconds() / 60.0, 1) if obs_time else None
            metar_decoded["fetch_time_utc"] = fetch_time
            metar_decoded["latency_min"] = latency
        taf_decoded = decode_taf(taf_raw.raw)

        components = []
        runway_surface_conditions = []
        for runway in airfield["runways"]:
            comp = wind_components(
                metar_decoded["wind_dir_deg"],
                metar_decoded["wind_speed_kt"],
                runway["magnetic_heading_deg"],
            )
            components.append({"runway": runway["designator"], **comp})
            runway_surface_conditions.append(
                {
                    "runway": runway["designator"],
                    "surface": runway.get("surface", "--"),
                    "condition": _runway_condition_from_notams(runway["designator"], notam_lines),
                }
            )

        crosswind = max((c["crosswind_kt"] or 0 for c in components), default=0)
        da = density_altitude(
            airfield["elevation_m"],
            metar_decoded["qnh_hpa"],
            metar_decoded["temp_c"],
        )
        ceiling_est = metar_decoded.get("ceiling_ft") or cloud_base_ft(
            metar_decoded.get("temp_c"),
            metar_decoded.get("dewpoint_c"),
        )

        history = load_history(ident)
        previous = history[-1] if history else None
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
        if record_history:
            save_history(ident, history)

        changes = detect_changes(previous, history[-1])
        qnh_rate = None
        hours = hours_between(
            previous.get("timestamp") if previous else None,
            history[-1]["timestamp"],
        )
        if hours and previous and previous.get("qnh_hpa") and history[-1].get("qnh_hpa"):
            qnh_rate = round((history[-1]["qnh_hpa"] - previous["qnh_hpa"]) / hours, 2)

        taf_valid_to = parse_taf_valid_to(taf_decoded["summary"]["valid_to"], now)
        taf_expiry = time_to_expiry(taf_valid_to, now)

        sun = sun_times(now.date(), airfield["latitude_deg"], airfield["longitude_deg"])
        twilight = civil_twilight(now.date(), airfield["latitude_deg"], airfield["longitude_deg"])
        night = is_night(now, twilight.get("sunset"), twilight.get("sunrise"))

        trend_fast = qnh_falling_fast(
            history,
            default_profile["thresholds"]["qnh_fall_fast_hpa_per_hr"],
        )
        flags, flag_explanations = compute_flags(
            metar_decoded,
            da,
            components,
            default_profile,
            trend_fast,
        )
        runway_short = any(
            runway["length_m"] < default_profile["thresholds"]["short_runway_m"]
            for runway in airfield["runways"]
        )
        taf_deteriorating = "TS" in taf_decoded["raw"] or "TEMPO" in taf_decoded["raw"]
        compounds = compound_flags(flags, runway_short, night, taf_deteriorating, trend_fast)
        for compound in compounds:
            if compound == "HIGH_DA_SHORT_RWY":
                flag_explanations[compound] = {
                    "density_altitude_ft": da.get("da_ft"),
                    "short_runway_threshold_m": default_profile["thresholds"]["short_runway_m"],
                    "note": "High DA combined with short runway increases performance risk.",
                }
            elif compound == "CROSSWIND_HIGH_GUSTY":
                flag_explanations[compound] = {
                    "crosswind_kt": crosswind,
                    "gust_kt": metar_decoded.get("gust_kt"),
                    "note": "Crosswind with gusts increases workload.",
                }
            elif compound == "LOW_CEILING_NIGHT":
                flag_explanations[compound] = {
                    "ceiling_ft": metar_decoded.get("ceiling_ft"),
                    "night": night,
                    "note": "Low ceiling during night conditions.",
                }
            elif compound == "RAPID_QNH_FALL_TAF_DETERIORATING":
                flag_explanations[compound] = {
                    "qnh_change_rate_hpa_per_hr": qnh_rate,
                    "taf_hint": taf_decoded.get("raw"),
                    "note": "Rapid QNH fall with deteriorating TAF.",
                }
            else:
                flag_explanations[compound] = {
                    "note": "Compound flag based on multiple conditions."
                }
        all_flags = flags + compounds
        severity = flag_severity(all_flags, default_profile.get("severity", {}))

        workload = workload_score(
            {
                "crosswind_ratio": crosswind
                / default_profile["thresholds"]["max_crosswind_kt"]
                if default_profile["thresholds"]["max_crosswind_kt"]
                else 0,
                "gust_ratio": (
                    metar_decoded.get("gust_kt", 0)
                    - metar_decoded.get("wind_speed_kt", 0)
                )
                / default_profile["thresholds"]["max_gust_spread_kt"]
                if metar_decoded.get("gust_kt") and metar_decoded.get("wind_speed_kt")
                else 0,
                "da_ratio": (da.get("da_ft") or 0)
                / default_profile["thresholds"]["max_da_ft"]
                if default_profile["thresholds"]["max_da_ft"]
                else 0,
                "convective": 1.0 if "TS" in taf_decoded["raw"] else 0.0,
                "night": 1.0 if night else 0.0,
                "rapid_change": 1.0
                if abs(changes["details"].get("wind_speed_delta_kt", 0)) >= 10
                else 0.0,
            }
        )
        stability = stability_score(
            {
                "wind_shift": min(abs(changes["details"].get("wind_dir_shift_deg", 0)) / 60.0, 1.0),
                "gust_spread": min(
                    (
                        metar_decoded.get("gust_kt", 0)
                        - metar_decoded.get("wind_speed_kt", 0)
                    )
                    / default_profile["thresholds"]["max_gust_spread_kt"]
                    if metar_decoded.get("gust_kt") and metar_decoded.get("wind_speed_kt")
                    else 0,
                    1.0,
                ),
                "metar_taf_mismatch": 1.0
                if (
                    "TS" in taf_decoded["raw"]
                    and "TS" not in metar_decoded.get("weather_codes", [])
                )
                else 0.0,
                "qnh_fall": 1.0 if trend_fast else 0.0,
                "speci": 0.0,
            }
        )

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
                "metar": metar_decoded
                | {"source": metar_source, "source_detail": _source_detail(metar_source)},
                "taf": taf_decoded
                | {"source": taf_source, "source_detail": _source_detail(taf_source)},
                "notams": notam_entries,
                "computed": {
                    "wind_components_per_runway": components,
                    "runway_surface_conditions": runway_surface_conditions,
                    "density_altitude": da,
                    "qnh_trend": qnh_trend(history),
                    "flags": all_flags,
                    "flag_explanations": flag_explanations,
                    "severity": severity,
                    "changes": changes,
                    "qnh_change_rate_hpa_per_hr": qnh_rate,
                    "taf_time_to_expiry": taf_expiry,
                    "sun": {
                        "sunrise": sun.get("sunrise"),
                        "sunset": sun.get("sunset"),
                        "civil_twilight_start": twilight.get("sunrise"),
                        "civil_twilight_end": twilight.get("sunset"),
                        "is_night": night,
                    },
                    "workload": workload,
                    "stability": stability,
                    "trends": {
                        "wind_speed": [item.get("wind_speed_kt") for item in history][-20:],
                        "qnh": [item.get("qnh_hpa") for item in history][-20:],
                        "temp": [item.get("temp_c") for item in history][-20:],
                        "dewpoint": [item.get("dewpoint_c") for item in history][-20:],
                        "visibility": [item.get("visibility_m") for item in history][-20:],
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

    now = dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    sigmet_lines = sigmet_adapter.fetch()
    sigmet_decoded = decode_sigmet(sigmet_lines)
    winds = winds_adapter.fetch()

    built_routes = []
    for route in routes:
        dep = airfield_map.get(route["dep"])
        dest = airfield_map.get(route["dest"])
        alternates = [
            airfield_map[ident]
            for ident in route.get("alternates", [])
            if ident in airfield_map
        ]

        track = None
        if dep and dest:
            track = bearing_deg(
                dep["latitude_deg"],
                dep["longitude_deg"],
                dest["latitude_deg"],
                dest["longitude_deg"],
            )

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

        route_workload = workload_score(
            {
                "crosswind_ratio": 0.0,
                "gust_ratio": 0.0,
                "da_ratio": 0.0,
                "convective": 1.0 if convective_risk else 0.0,
                "night": 1.0 if (dep and dep["computed"]["sun"]["is_night"]) else 0.0,
                "rapid_change": 1.0 if turbulence_risk else 0.0,
            }
        )
        route_stability = stability_score(
            {
                "wind_shift": 0.0,
                "gust_spread": 0.0,
                "metar_taf_mismatch": 1.0 if convective_risk else 0.0,
                "qnh_fall": 0.0,
                "speci": 0.0,
            }
        )

        def _taf_expiry(item: dict | None) -> dict:
            if not item:
                return {"hours": None, "urgency": "unknown"}
            taf_valid_to = parse_taf_valid_to(item["taf"]["summary"]["valid_to"], now)
            return time_to_expiry(taf_valid_to, now)

        built_routes.append(
            {
                **route,
                "airfields": [item for item in [dep, dest, *alternates] if item],
                "track_deg": track,
                "upper_winds": wind_levels,
                "freezing_level_ft": freezing_level,
                "sigmet_lines": [item["raw"] for item in sigmet_decoded],
                "sigmet_time_to_expiry": time_to_expiry(None, now),
                "notams": {
                    ident: [entry["text"] for entry in entries]
                    for ident, entries in notams.items()
                },
                "taf_time_to_expiry": {
                    "dep": _taf_expiry(dep),
                    "dest": _taf_expiry(dest),
                },
                "summary": {
                    "flags": flags,
                    "severity": severity,
                    "workload": route_workload,
                    "stability": route_stability,
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


def build_tools_pages(mode_info: dict) -> None:
    tools_dir = SITE_DIR / "tools"
    tools_dir.mkdir(parents=True, exist_ok=True)

    (tools_dir / "index.html").write_text(render_tools_index(mode_info), encoding="utf-8")

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

    (tools_dir / "isa.html").write_text(
        render_tool_page("ISA Tool", isa_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "altimetry.html").write_text(
        render_tool_page("Altimetry Tool", altimetry_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "density-altitude.html").write_text(
        render_tool_page("Density Altitude Tool", da_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "tas.html").write_text(
        render_tool_page("IAS → TAS Tool", tas_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "hypoxia.html").write_text(
        render_tool_page("Gas laws & Hypoxia", hypoxia_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "pressurisation.html").write_text(
        render_tool_page("Pressurisation Simulator", press_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "aircraft.html").write_text(
        render_tool_page("Training Aircraft Reference", aircraft_content, mode_info),
        encoding="utf-8",
    )
    (tools_dir / "scenario.html").write_text(
        render_tool_page("Scenario Builder", scenario_content, mode_info),
        encoding="utf-8",
    )


def build_site(mode: str = "sample") -> None:
    validate_all()

    mode_key = "sample" if mode in ("sample", "auto") else "live_beta"
    mode_info = build_mode_info(mode_key)
    airfields, default_profile, profiles = build_airfields(mode)
    routes = build_routes(airfields, default_profile)

    sigwx_adapter = SampleSigwxAdapter(SAMPLES_DIR / "sigwx")
    sigwx_paths = copy_sigwx(sigwx_adapter.fetch())

    SITE_DIR.mkdir(parents=True, exist_ok=True)
    write_assets()
    build_tools_pages(mode_info)

    (SITE_DIR / "index.html").write_text(
        render_home(airfields, default_profile["name"], mode_info),
        encoding="utf-8",
    )
    (SITE_DIR / "routes.html").write_text(render_routes_index(routes, mode_info), encoding="utf-8")

    airfield_dir = SITE_DIR / "airfield"
    airfield_dir.mkdir(parents=True, exist_ok=True)
    for airfield in airfields:
        (airfield_dir / f"{airfield['ident']}.html").write_text(
            render_airfield_page(airfield, mode_info),
            encoding="utf-8",
        )

    route_dir = SITE_DIR / "route"
    route_dir.mkdir(parents=True, exist_ok=True)
    for route in routes:
        (route_dir / f"{route['route_id']}.html").write_text(
            render_route_page(route, sigwx_paths, mode_info),
            encoding="utf-8",
        )

    write_json(
        SITE_DIR / "api" / "latest.json",
        {"mode": mode_info, "airfields": airfields, "routes": routes},
    )
    write_json(SITE_DIR / "api" / "profiles.json", profiles)
    write_json(SITE_DIR / "api" / "aircraft.json", load_aircraft())

    for airfield in airfields:
        write_json(SITE_DIR / "api" / "airfield" / f"{airfield['ident']}.json", airfield)
    for route in routes:
        write_json(SITE_DIR / "api" / "route" / f"{route['route_id']}.json", route)


def render_snapshot_page(snapshot_id: str, mode_info: dict) -> str:
    return f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <meta name="base-path" content="../" />
  <title>Snapshot {snapshot_id}</title>
  <link rel="stylesheet" href="../assets/style.css" />
</head>
<body>
  <header>
    <h1>METAR.oncloud.africa Snapshot</h1>
    <p class="disclaimer">Training/augmentation only. Not an official briefing source.</p>
    <div class="mode-row">
      <span class="mode-banner {mode_info['class']}">
        <span class="icon">●</span>{mode_info['label']} — {mode_info['text']}
      </span>
      <button id="copy-link">Copy link</button>
    </div>
  </header>
  <main class="container">
    <div id="snapshot-content" class="card">Loading snapshot...</div>
  </main>
  <script>
    const snapshotId = "{snapshot_id}";
    async function loadSnapshot() {{
      const res = await fetch(`../api/snapshots/${{snapshotId}}.json`);
      const data = await res.json();
      const content = document.getElementById('snapshot-content');
      content.innerHTML = `
        <h3>Snapshot ${{snapshotId}}</h3>
        <p><strong>Generated:</strong> ${{data.generated_at}}</p>
        <p><strong>Profile:</strong> ${{data.profile.name}}</p>
        <pre>${{JSON.stringify(data.payload, null, 2)}}</pre>
      `;
    }}
    document.getElementById('copy-link').addEventListener('click', () => {{
      navigator.clipboard.writeText(window.location.href);
    }});
    loadSnapshot();
  </script>
</body>
</html>
"""


def build_snapshot(
    snapshot_type: str,
    ident: str,
    profile_name: str,
    source: str,
    snapshot_id: str,
) -> None:
    mode_key = "live_beta" if source == "live_beta" else "sample"
    mode_info = build_mode_info(mode_key)
    airfields, _, profiles = build_airfields(mode_key, record_history=False)
    routes = build_routes(airfields, profiles[0])

    profile = next((p for p in profiles if p["name"] == profile_name), profiles[0])

    payload: dict
    if snapshot_type == "airfield":
        target = next((a for a in airfields if a["ident"] == ident), None)
        if not target:
            raise ValueError("Unknown airfield for snapshot")
        payload = {"airfield": target}
    else:
        target = next((r for r in routes if r["route_id"] == ident), None)
        if not target:
            raise ValueError("Unknown route for snapshot")
        payload = {"route": target}

    snapshot = {
        "id": snapshot_id,
        "generated_at": dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc).isoformat(),
        "mode": mode_info,
        "profile": profile,
        "payload": payload,
    }

    write_json(SITE_DIR / "api" / "snapshots" / f"{snapshot_id}.json", snapshot)
    (SITE_DIR / "snapshot").mkdir(parents=True, exist_ok=True)
    (SITE_DIR / "snapshot" / f"{snapshot_id}.html").write_text(
        render_snapshot_page(snapshot_id, mode_info),
        encoding="utf-8",
    )


def _style_css() -> str:
    return """
:root {
  font-family: 'Inter', system-ui, sans-serif;
  color: #0f172a;
}
body { margin: 0; background: #f8fafc; }
header { background: #0f172a; color: #fff; padding: 20px; }
nav a {
  color: #cbd5f5;
  margin-right: 16px;
  text-decoration: none;
  font-weight: 600;
}
nav a.active {
  color: #fff;
  border-bottom: 2px solid #38bdf8;
  padding-bottom: 4px;
}
.mode-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 12px;
  flex-wrap: wrap;
  gap: 12px;
}
.mode-banner {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 6px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.mode-training { background: #e0f2fe; color: #0f172a; }
.mode-live { background: #fee2e2; color: #991b1b; }
.mode-select select { padding: 4px 6px; }
.container { padding: 24px; max-width: 1200px; margin: 0 auto; }
.grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 16px;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.08);
}
.card-header { display: flex; justify-content: space-between; align-items: center; }
.card-header h3 { margin: 0; font-size: 1rem; }
.badge-row { display: flex; gap: 8px; margin: 8px 0; }
.badge {
  display: inline-block;
  background: #e2e8f0;
  color: #1e293b;
  padding: 4px 8px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.badge.night { background: #c7d2fe; }
.pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 700;
}
.icon { font-size: 10px; }
.status-ok { background: #e0f2fe; color: #0f172a; }
.status-caution { background: #fef3c7; color: #92400e; }
.status-warning { background: #fee2e2; color: #991b1b; }
.status-unknown { background: #e5e7eb; color: #374151; }
.summary { background: #e0f2fe; border-radius: 12px; padding: 16px; }
.table { width: 100%; border-collapse: collapse; margin-top: 12px; }
.table th,
.table td {
  text-align: left;
  padding: 8px;
  border-bottom: 1px solid #e5e7eb;
  font-size: 14px;
}
.section { margin-top: 24px; }
.flag-list { margin: 8px 0; padding-left: 18px; }
.note { font-size: 13px; color: #475569; }
.result {
  margin-top: 12px;
  padding: 12px;
  background: #f1f5f9;
  border-radius: 8px;
}
footer { padding: 24px; text-align: center; font-size: 12px; color: #475569; }
input,
select {
  padding: 6px 8px;
  margin: 6px 8px 6px 0;
  max-width: 100%;
}
button {
  padding: 6px 10px;
  background: #0ea5e9;
  color: #fff;
  border: none;
  border-radius: 6px;
  cursor: pointer;
}
.urgency-amber { color: #b45309; font-weight: 700; }
.urgency-red { color: #b91c1c; font-weight: 700; }
.sparkline { width: 140px; height: 40px; }
.timeline { display: flex; gap: 12px; align-items: center; font-size: 12px; }
@media (max-width: 900px) {
  header { padding: 16px; }
  .container { padding: 16px; }
  .mode-row { flex-direction: column; align-items: flex-start; }
  .card-header { flex-direction: column; align-items: flex-start; gap: 8px; }
  .badge-row { flex-wrap: wrap; }
  .table { display: block; overflow-x: auto; white-space: nowrap; }
  .timeline { flex-direction: column; align-items: flex-start; }
}
@media (max-width: 600px) {
  nav { display: flex; flex-direction: column; gap: 6px; }
  nav a { margin-right: 0; }
  input, select, button { width: 100%; }
  .grid { grid-template-columns: 1fr; }
}
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
    document.getElementById('isa-output').textContent =
      `ISA temp: ${isa.toFixed(1)}°C | ISA deviation: ${dev}°C`;
  }
  if (action === 'calc-altimetry') {
    const elevM = toNumber('alt-elev');
    const qnh = toNumber('alt-qnh');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    document.getElementById('alt-output').textContent =
      `Pressure altitude: ${pressureAlt.toFixed(0)} ft `
      + `(${(pressureAlt / 3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-da') {
    const elevM = toNumber('da-elev');
    const qnh = toNumber('da-qnh');
    const oat = toNumber('da-oat');
    const elevFt = elevM * 3.28084;
    const pressureAlt = elevFt + (1013.25 - qnh) * 30;
    const isa = isaTemp(pressureAlt);
    const da = pressureAlt + 120 * (oat - isa);
    document.getElementById('da-output').textContent =
      `Density altitude: ${da.toFixed(0)} ft `
      + `(${(da / 3.28084).toFixed(0)} m)`;
  }
  if (action === 'calc-tas') {
    const ias = toNumber('tas-ias');
    const alt = toNumber('tas-alt');
    const dev = toNumber('tas-dev');
    const tas = ias * (1 + alt / 1000 * 0.02) * (1 + dev / 100);
    document.getElementById('tas-output').textContent =
      `Estimated TAS: ${tas.toFixed(1)} kt (training approximation)`;
  }
  if (action === 'calc-hypoxia') {
    const alt = toNumber('hypoxia-alt');
    const index = Math.max(10, 100 - alt / 300);
    document.getElementById('hypoxia-output').textContent =
      `Oxygen index: ${index.toFixed(1)} (training scale). `
      + 'Beware trapped gas at altitude.';
  }
  if (action === 'calc-press') {
    const cruise = toNumber('press-cruise');
    const dest = toNumber('press-dest');
    const rate = toNumber('press-rate');
    const diff = toNumber('press-diff');
    const cabin = Math.min(cruise * 0.6, dest + diff * 2000);
    document.getElementById('press-output').textContent =
      `Estimated cabin altitude: ${cabin.toFixed(0)} ft `
      + `at ${rate} fpm (training only)`;
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
    <p><strong>Aircraft:</strong> ${aircraftInfo ? aircraftInfo.type : ''} `
      + `(${aircraftInfo ? aircraftInfo.demonstrated_crosswind_kt : ''} `
      + 'kt demo crosswind)</p>
    <p><strong>Density altitude:</strong> ${da} ft</p>
    <p><strong>Flags:</strong> ${flags.join(', ') || 'LOW_RISK'}</p>
    <p><strong>Questions:</strong> How will crosswind/tailwind affect `
      + 'your performance? Are you within personal minima?</p>
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

async function initGoNoGo() {
  const output = document.getElementById('go-no-go-output');
  const profileSelect = document.getElementById('profile-select');
  const aircraftSelect = document.getElementById('aircraft-select');
  if (!output || !profileSelect || !aircraftSelect) return;

  const latest = await fetch(`${basePath}api/latest.json`).then(r => r.json());
  const profiles = await fetch(`${basePath}api/profiles.json`).then(r => r.json());
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());
  const ident = output.getAttribute('data-airfield');
  const airfield = latest.airfields.find(a => a.ident === ident);
  if (!airfield) {
    output.textContent = 'Unable to load selected airfield.';
    return;
  }

  profiles.forEach(p => profileSelect.add(new Option(p.name, p.name)));
  aircraft.forEach(a => aircraftSelect.add(new Option(a.type, a.type)));

  const evaluate = () => {
    const profile = profiles.find(p => p.name === profileSelect.value) || profiles[0];
    const selectedAircraft = aircraft.find(a => a.type === aircraftSelect.value) || aircraft[0];
    const limits = profile.thresholds;
    const maxCrosswind = Math.min(
      limits.max_crosswind_kt || 0,
      selectedAircraft.demonstrated_crosswind_kt || limits.max_crosswind_kt || 0,
    );
    const metar = airfield.metar;
    const densityAltitude = airfield.computed.density_altitude.da_ft || 0;
    const maxCrosswindSeen = Math.max(
      ...airfield.computed.wind_components_per_runway.map(c => c.crosswind_kt || 0),
      0,
    );
    const reasons = [];

    if (maxCrosswindSeen > maxCrosswind) {
      reasons.push(`Crosswind ${maxCrosswindSeen} kt > limit ${maxCrosswind} kt`);
    }
    if ((metar.visibility_m || 99999) < (limits.min_vis_m || 0)) {
      reasons.push(`Visibility ${metar.visibility_m} m < profile min ${limits.min_vis_m} m`);
    }
    if (metar.ceiling_ft !== null && metar.ceiling_ft < (limits.min_ceiling_ft || 0)) {
      reasons.push(`Ceiling ${metar.ceiling_ft} ft < profile min ${limits.min_ceiling_ft} ft`);
    }
    if ((densityAltitude || 0) > (limits.max_da_ft || 99999)) {
      reasons.push(`DA ${densityAltitude} ft > profile max ${limits.max_da_ft} ft`);
    }

    const verdict = reasons.length ? 'NO-GO' : 'GO (training advisory)';
    const mtowNote = selectedAircraft.notes || 'Verify actual MTOW and POH limits.';
    output.innerHTML = `
      <p><strong>Verdict:</strong> ${verdict}</p>
      <p><strong>Profile:</strong> ${profile.name} (${profile.licence_tier})</p>
      <p><strong>Aircraft:</strong> ${selectedAircraft.type}</p>
      <p><strong>Crosswind limit used:</strong> ${maxCrosswind} kt</p>
      <p><strong>Density altitude now:</strong> ${densityAltitude} ft</p>
      <p><strong>MTOW/POH note:</strong> ${mtowNote}</p>
      <p><strong>Reasons:</strong> ${reasons.join('; ')
        || 'Within selected profile/aircraft limits.'}</p>
    `;
  };

  profileSelect.addEventListener('change', evaluate);
  aircraftSelect.addEventListener('change', evaluate);
  evaluate();
}

populateScenario();
initGoNoGo();

async function populateAircraft() {
  const container = document.getElementById('aircraft-list');
  if (!container) return;
  const aircraft = await fetch(`${basePath}api/aircraft.json`).then(r => r.json());
  container.innerHTML = aircraft.map(a => (
    `<div class="card"><h4>${a.type}</h4>`
      + `<p>Demo crosswind: ${a.demonstrated_crosswind_kt} kt</p>`
      + `<p>${a.notes}</p></div>`
  )).join('');
}

populateAircraft();

function renderSparkline() {
  document.querySelectorAll('[data-spark]').forEach(el => {
    const data = JSON.parse(el.getAttribute('data-spark'));
    if (!data.length) return;
    const max = Math.max(...data.filter(v => v !== null));
    const min = Math.min(...data.filter(v => v !== null));
    const width = 140;
    const height = 40;
    const points = data.map((v, idx) => {
      const x = (idx / (data.length - 1)) * width;
      const y = height - ((v - min) / (max - min || 1)) * height;
      return `${x},${y}`;
    }).join(' ');
    el.innerHTML = (
      `<svg width=\"${width}\" height=\"${height}\" `
        + `viewBox=\"0 0 ${width} ${height}\">`
        + `<polyline fill=\"none\" stroke=\"#0ea5e9\" `
        + `stroke-width=\"2\" points=\"${points}\"/>`
        + '</svg>'
    );
  });
}

renderSparkline();
"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        default="sample",
        choices=["sample", "auto", "live_beta"],
        help="Build mode",
    )
    parser.add_argument("--snapshot", action="store_true", help="Create snapshot artifacts only")
    parser.add_argument("--snapshot-type", choices=["airfield", "route"], default="airfield")
    parser.add_argument("--snapshot-ident", default="")
    parser.add_argument("--snapshot-profile", default="PPL")
    parser.add_argument("--snapshot-source", choices=["sample", "live_beta"], default="sample")
    parser.add_argument("--snapshot-id", default="")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.snapshot:
        snap_id = args.snapshot_id or f"snap-{dt.datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        build_snapshot(
            args.snapshot_type,
            args.snapshot_ident,
            args.snapshot_profile,
            args.snapshot_source,
            snap_id,
        )
    else:
        build_site(args.mode)
