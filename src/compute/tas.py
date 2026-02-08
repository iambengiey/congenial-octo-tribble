from __future__ import annotations


def tas_estimate(ias_kt: float, altitude_ft: float, isa_dev_c: float | None = None) -> float:
    temp_factor = 1.0
    if isa_dev_c is not None:
        temp_factor += isa_dev_c / 100.0
    return round(ias_kt * (1 + altitude_ft / 1000.0 * 0.02) * temp_factor, 1)
