from __future__ import annotations

import math


def wind_components(wind_dir: int | None, wind_speed: int | None, runway_heading: int) -> dict:
    if wind_dir is None or wind_speed is None:
        return {
            "headwind_kt": None,
            "crosswind_kt": None,
            "tailwind_kt": None,
            "crosswind_side": None,
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
    crosswind_side = "R" if crosswind > 0 else "L"
    return {
        "headwind_kt": headwind_kt,
        "crosswind_kt": crosswind_kt,
        "tailwind_kt": tailwind_kt,
        "crosswind_side": crosswind_side,
    }
