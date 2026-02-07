from __future__ import annotations

import math


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    lat1_r = math.radians(lat1)
    lat2_r = math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(lat2_r)
    y = math.cos(lat1_r) * math.sin(lat2_r) - math.sin(lat1_r) * math.cos(lat2_r) * math.cos(dlon)
    bearing = math.degrees(math.atan2(x, y))
    return (bearing + 360) % 360


def headwind_component(wind_dir_deg: float, wind_speed_kt: float, track_deg: float) -> float:
    diff = math.radians((wind_dir_deg - track_deg + 360) % 360)
    return round(wind_speed_kt * math.cos(diff), 1)


def ground_speed_estimate(true_airspeed_kt: float, wind_dir_deg: float, wind_speed_kt: float, track_deg: float) -> float:
    headwind = headwind_component(wind_dir_deg, wind_speed_kt, track_deg)
    return round(true_airspeed_kt - headwind, 1)
