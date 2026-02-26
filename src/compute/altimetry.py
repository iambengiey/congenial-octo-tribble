from __future__ import annotations


def pressure_altitude_ft(elevation_m: float, qnh_hpa: float) -> float:
    elevation_ft = elevation_m * 3.28084
    return round(elevation_ft + (1013.25 - qnh_hpa) * 30, 1)
