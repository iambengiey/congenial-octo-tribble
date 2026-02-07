from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


@dataclass
class Runway:
    designator: str
    magnetic_heading_deg: int
    length_m: int
    surface: str


def wind_components(wind_dir: int | None, wind_speed: int | None, runway_heading: int) -> dict:
    if wind_dir is None or wind_speed is None:
        return {
            "headwind_kt": None,
            "crosswind_kt": None,
            "tailwind_kt": None,
            "crosswind_direction": None,
        }
    diff = math.radians((wind_dir - runway_heading + 360) % 360)
    headwind = wind_speed * math.cos(diff)
    crosswind = wind_speed * math.sin(diff)
    headwind_kt = round(headwind, 1)
    crosswind_kt = round(abs(crosswind), 1)
    tailwind_kt = 0.0
    if headwind_kt < 0:
        tailwind_kt = abs(headwind_kt)
        headwind_kt = 0.0
    crosswind_direction = "right" if crosswind > 0 else "left"
    return {
        "headwind_kt": headwind_kt,
        "crosswind_kt": crosswind_kt,
        "tailwind_kt": tailwind_kt,
        "crosswind_direction": crosswind_direction,
    }


def density_altitude_ft(elevation_m: float, qnh_hpa: float | None, temp_c: float | None) -> dict:
    if qnh_hpa is None or temp_c is None:
        return {"density_altitude_ft": None, "density_altitude_m": None}
    elevation_ft = elevation_m * 3.28084
    pressure_alt_ft = elevation_ft + (1013.25 - qnh_hpa) * 30
    isa_temp = 15.0 - 1.98 * (elevation_ft / 1000.0)
    da_ft = pressure_alt_ft + 120.0 * (temp_c - isa_temp)
    return {
        "density_altitude_ft": round(da_ft),
        "density_altitude_m": round(da_ft / 3.28084),
    }


def qnh_trend(history: list[dict]) -> str:
    if len(history) < 2:
        return "steady"
    delta = history[-1]["qnh_hpa"] - history[-2]["qnh_hpa"]
    if delta > 1:
        return "rising"
    if delta < -1:
        return "falling"
    return "steady"


def load_history(history_dir: Path, ident: str) -> list[dict]:
    path = history_dir / f"{ident}.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def save_history(history_dir: Path, ident: str, history: list[dict]) -> None:
    history_dir.mkdir(parents=True, exist_ok=True)
    path = history_dir / f"{ident}.json"
    path.write_text(json.dumps(history[-12:], indent=2), encoding="utf-8")


def compute_flags(
    *,
    wind_components_per_runway: Iterable[dict],
    density_altitude: dict,
    visibility_m: int | None,
    cloud_layers: list[dict],
    thresholds: dict,
) -> list[str]:
    flags: list[str] = []
    crosswind_high = thresholds["crosswind_high_kt"]
    tailwind_limit = thresholds["tailwind_kt"]
    high_da_ft = thresholds["high_da_ft"]
    low_vis_m = thresholds["low_vis_m"]
    low_ceiling_ft = thresholds["low_ceiling_ft"]

    max_crosswind = max(
        (component["crosswind_kt"] or 0 for component in wind_components_per_runway),
        default=0,
    )
    if max_crosswind >= crosswind_high:
        flags.append("CROSSWIND_HIGH")

    max_tailwind = max(
        (component["tailwind_kt"] or 0 for component in wind_components_per_runway),
        default=0,
    )
    if max_tailwind >= tailwind_limit:
        flags.append("TAILWIND")

    if density_altitude.get("density_altitude_ft") and density_altitude["density_altitude_ft"] >= high_da_ft:
        flags.append("HIGH_DA")

    if visibility_m is not None and visibility_m <= low_vis_m:
        flags.append("LOW_VIS")

    if cloud_layers:
        lowest = min(layer["base_ft"] for layer in cloud_layers)
        if lowest <= low_ceiling_ft:
            flags.append("LOW_CEILING")

    return flags
