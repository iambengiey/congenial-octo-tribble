from __future__ import annotations


def cabin_profile(
    cruise_level_ft: float,
    destination_elevation_ft: float,
    cabin_rate_fpm: float,
    max_differential_psi: float,
) -> dict:
    cabin_altitude = min(
        cruise_level_ft * 0.6,
        destination_elevation_ft + max_differential_psi * 2000,
    )
    return {
        "cabin_altitude_ft": round(cabin_altitude),
        "cabin_rate_fpm": cabin_rate_fpm,
        "note": "Training-only, simplified pressurisation profile.",
    }
