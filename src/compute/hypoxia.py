from __future__ import annotations


def oxygen_index(altitude_ft: float) -> float:
    if altitude_ft <= 0:
        return 100.0
    return round(max(10.0, 100.0 - altitude_ft / 300.0), 1)
