from __future__ import annotations


def _category_vis(vis_m: int | None) -> str:
    if vis_m is None:
        return "unknown"
    if vis_m < 1000:
        return "very_low"
    if vis_m < 3000:
        return "low"
    return "normal"


def _category_ceiling(ceiling_ft: int | None) -> str:
    if ceiling_ft is None:
        return "unknown"
    if ceiling_ft < 500:
        return "ifr"
    if ceiling_ft < 1500:
        return "marginal"
    return "normal"


def detect_changes(previous: dict | None, current: dict) -> dict:
    if not previous:
        return {"summary": "No prior data", "details": {}}

    details = {
        "wind_speed_delta_kt": (current.get("wind_speed_kt") or 0)
        - (previous.get("wind_speed_kt") or 0),
        "wind_dir_shift_deg": (current.get("wind_dir_deg") or 0)
        - (previous.get("wind_dir_deg") or 0),
        "qnh_change_hpa": (current.get("qnh_hpa") or 0) - (previous.get("qnh_hpa") or 0),
        "temp_dewpoint_spread_change": (
            (current.get("temp_c") or 0) - (current.get("dewpoint_c") or 0)
        )
        - ((previous.get("temp_c") or 0) - (previous.get("dewpoint_c") or 0)),
        "ceiling_category": {
            "from": _category_ceiling(previous.get("ceiling_ft_est")),
            "to": _category_ceiling(current.get("ceiling_ft_est")),
        },
        "visibility_category": {
            "from": _category_vis(previous.get("visibility_m")),
            "to": _category_vis(current.get("visibility_m")),
        },
    }
    summary = (
        "Wind/QNH changes detected"
        if details["wind_speed_delta_kt"] or details["qnh_change_hpa"]
        else "Minimal changes"
    )
    return {"summary": summary, "details": details}
