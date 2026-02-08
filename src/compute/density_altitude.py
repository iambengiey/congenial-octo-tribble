from __future__ import annotations

from src.compute.altimetry import pressure_altitude_ft
from src.compute.isa import isa_temp_c


def density_altitude(elevation_m: float, qnh_hpa: float | None, temp_c: float | None) -> dict:
    if qnh_hpa is None or temp_c is None:
        return {"da_ft": None, "da_m": None}
    pressure_alt = pressure_altitude_ft(elevation_m, qnh_hpa)
    isa_temp = isa_temp_c(pressure_alt)
    da_ft = pressure_alt + 120.0 * (temp_c - isa_temp)
    return {"da_ft": round(da_ft), "da_m": round(da_ft / 3.28084)}
