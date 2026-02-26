from __future__ import annotations


def isa_temp_c(altitude_ft: float) -> float:
    return round(15.0 - 2.0 * (altitude_ft / 1000.0), 1)


def isa_deviation(oat_c: float, altitude_ft: float) -> float:
    return round(oat_c - isa_temp_c(altitude_ft), 1)
