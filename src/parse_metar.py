from __future__ import annotations

import datetime as dt
import re

WIND_RE = re.compile(r"(?P<dir>\d{3}|VRB)(?P<speed>\d{2})(G(?P<gust>\d{2}))?KT")
VIS_RE = re.compile(r"(?P<vis>\d{4})")
TEMP_RE = re.compile(r"(?P<temp>M?\d{2})/(?P<dew>M?\d{2})")
QNH_RE = re.compile(r"Q(?P<qnh>\d{4})")
TIME_RE = re.compile(r"(?P<day>\d{2})(?P<hour>\d{2})(?P<min>\d{2})Z")
CLOUD_RE = re.compile(r"(?P<cover>FEW|SCT|BKN|OVC)(?P<base>\d{3})")


def _parse_temp(value: str) -> int:
    if value.startswith("M"):
        return -int(value[1:])
    return int(value)


def _parse_time(raw: str) -> str:
    match = TIME_RE.search(raw)
    if not match:
        return ""
    now = dt.datetime.utcnow()
    obs = dt.datetime(
        year=now.year,
        month=now.month,
        day=int(match.group("day")),
        hour=int(match.group("hour")),
        minute=int(match.group("min")),
        tzinfo=dt.timezone.utc,
    )
    return obs.isoformat().replace("+00:00", "Z")


def decode_metar(raw: str) -> dict:
    wind_dir = None
    wind_speed = None
    gust = None
    wind_match = WIND_RE.search(raw)
    if wind_match:
        if wind_match.group("dir") != "VRB":
            wind_dir = int(wind_match.group("dir"))
        wind_speed = int(wind_match.group("speed"))
        if wind_match.group("gust"):
            gust = int(wind_match.group("gust"))

    vis_match = VIS_RE.search(raw)
    visibility_m = int(vis_match.group("vis")) if vis_match else None

    cloud_layers = []
    for cover, base in CLOUD_RE.findall(raw):
        cloud_layers.append({"cover": cover, "base_ft": int(base) * 100})

    temp_match = TEMP_RE.search(raw)
    temp_c = dew_c = None
    if temp_match:
        temp_c = _parse_temp(temp_match.group("temp"))
        dew_c = _parse_temp(temp_match.group("dew"))

    qnh_match = QNH_RE.search(raw)
    qnh_hpa = int(qnh_match.group("qnh")) if qnh_match else None

    observed_time = _parse_time(raw)

    remarks = ""
    if "RMK" in raw:
        remarks = raw.split("RMK", 1)[1].strip()

    return {
        "raw": raw,
        "wind_dir": wind_dir,
        "wind_speed_kt": wind_speed,
        "gust_kt": gust,
        "vis_m": visibility_m,
        "cloud_layers": cloud_layers,
        "temp_c": temp_c,
        "dewpoint_c": dew_c,
        "qnh_hpa": qnh_hpa,
        "remarks": remarks,
        "observed_time_utc": observed_time,
    }
