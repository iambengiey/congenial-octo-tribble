from __future__ import annotations

import datetime as dt
import math


def _julian_day(date: dt.date) -> float:
    return date.toordinal() + 1721424.5


def _sun_declination(julian_day: float) -> float:
    n = julian_day - 2451545.0
    mean_long = (280.46 + 0.9856474 * n) % 360
    mean_anom = math.radians((357.528 + 0.9856003 * n) % 360)
    eclip_long = math.radians((mean_long + 1.915 * math.sin(mean_anom) + 0.02 * math.sin(2 * mean_anom)) % 360)
    return math.asin(math.sin(math.radians(23.44)) * math.sin(eclip_long))


def _equation_of_time(julian_day: float) -> float:
    n = julian_day - 2451545.0
    mean_long = math.radians((280.46 + 0.9856474 * n) % 360)
    mean_anom = math.radians((357.528 + 0.9856003 * n) % 360)
    eclip_long = mean_long + math.radians(1.915) * math.sin(mean_anom) + math.radians(0.02) * math.sin(2 * mean_anom)
    return 4 * math.degrees(mean_long - eclip_long)


def sun_times(date: dt.date, lat_deg: float, lon_deg: float, zenith_deg: float = 90.833) -> dict:
    julian = _julian_day(date)
    decl = _sun_declination(julian)
    eq_time = _equation_of_time(julian)

    lat_rad = math.radians(lat_deg)
    zenith_rad = math.radians(zenith_deg)
    cos_h = (math.cos(zenith_rad) - math.sin(lat_rad) * math.sin(decl)) / (math.cos(lat_rad) * math.cos(decl))
    if cos_h >= 1:
        return {"sunrise": None, "sunset": None}
    if cos_h <= -1:
        return {"sunrise": None, "sunset": None}

    h = math.degrees(math.acos(cos_h))
    sunrise_min = 720 - 4 * (lon_deg + h) - eq_time
    sunset_min = 720 - 4 * (lon_deg - h) - eq_time

    def _to_time(minutes: float) -> str:
        hours = int(minutes // 60) % 24
        mins = int(minutes % 60)
        return dt.time(hours, mins).strftime("%H:%M")

    return {
        "sunrise": _to_time(sunrise_min),
        "sunset": _to_time(sunset_min),
    }


def civil_twilight(date: dt.date, lat_deg: float, lon_deg: float) -> dict:
    return sun_times(date, lat_deg, lon_deg, zenith_deg=96.0)


def is_night(now: dt.datetime, sunset: str | None, sunrise: str | None) -> bool:
    if not sunset or not sunrise:
        return False
    sunset_time = dt.datetime.combine(now.date(), dt.time.fromisoformat(sunset), tzinfo=dt.timezone.utc)
    sunrise_time = dt.datetime.combine(now.date(), dt.time.fromisoformat(sunrise), tzinfo=dt.timezone.utc)
    if sunset_time < sunrise_time:
        return now >= sunset_time or now <= sunrise_time
    return now >= sunset_time and now <= sunrise_time
