from __future__ import annotations

import datetime as dt
import re

WIND_RE = re.compile(r"(?P<dir>\d{3}|VRB)(?P<speed>\d{2})(G(?P<gust>\d{2}))?KT")
VAR_WIND_RE = re.compile(r"(?P<from>\d{3})V(?P<to>\d{3})")
VIS_RE = re.compile(r"\b(?P<vis>\d{4})\b")
TEMP_RE = re.compile(r"(?P<temp>M?\d{2})/(?P<dew>M?\d{2})")
QNH_RE = re.compile(r"Q(?P<qnh>\d{4})")
TIME_RE = re.compile(r"(?P<day>\d{2})(?P<hour>\d{2})(?P<min>\d{2})Z")
CLOUD_RE = re.compile(r"(?P<cover>FEW|SCT|BKN|OVC)(?P<base>\d{3})")
WEATHER_CODES = {
    "TS",
    "RA",
    "SH",
    "DZ",
    "SN",
    "BR",
    "FG",
    "HZ",
    "GR",
    "GS",
    "SQ",
    "VA",
}


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

    var_wind = None
    var_match = VAR_WIND_RE.search(raw)
    if var_match:
        var_wind = {"from": int(var_match.group("from")), "to": int(var_match.group("to"))}

    vis_match = VIS_RE.search(raw)
    visibility_m = int(vis_match.group("vis")) if vis_match else None

    cloud_layers = []
    for cover, base in CLOUD_RE.findall(raw):
        cloud_layers.append({"cover": cover, "base_ft": int(base) * 100})

    ceiling = None
    for layer in cloud_layers:
        if layer["cover"] in {"BKN", "OVC"}:
            ceiling = layer["base_ft"]
            break

    temp_match = TEMP_RE.search(raw)
    temp_c = dew_c = None
    if temp_match:
        temp_c = _parse_temp(temp_match.group("temp"))
        dew_c = _parse_temp(temp_match.group("dew"))

    qnh_match = QNH_RE.search(raw)
    qnh_hpa = int(qnh_match.group("qnh")) if qnh_match else None

    observed_time = _parse_time(raw)

    weather = [token for token in raw.split() if any(code in token for code in WEATHER_CODES)]

    remarks = ""
    if "RMK" in raw:
        remarks = raw.split("RMK", 1)[1].strip()

    return {
        "raw": raw,
        "observed_time_utc": observed_time,
        "wind_dir_deg": wind_dir,
        "wind_speed_kt": wind_speed,
        "gust_kt": gust,
        "variable_wind": var_wind,
        "visibility_m": visibility_m,
        "weather_codes": weather,
        "cloud_layers": cloud_layers,
        "ceiling_ft": ceiling,
        "temp_c": temp_c,
        "dewpoint_c": dew_c,
        "qnh_hpa": qnh_hpa,
        "remarks": remarks,
    }
