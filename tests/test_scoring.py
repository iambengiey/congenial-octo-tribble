import datetime as dt

from src.compute.change_detection import detect_changes
from src.compute.compound_flags import compound_flags
from src.compute.stability import stability_score
from src.compute.sun import sun_times
from src.compute.workload import workload_score


def test_change_detection_deltas():
    prev = {
        "wind_speed_kt": 10,
        "wind_dir_deg": 180,
        "qnh_hpa": 1010,
        "temp_c": 20,
        "dewpoint_c": 10,
        "visibility_m": 8000,
        "ceiling_ft_est": 1500,
    }
    curr = {
        "wind_speed_kt": 15,
        "wind_dir_deg": 200,
        "qnh_hpa": 1008,
        "temp_c": 18,
        "dewpoint_c": 12,
        "visibility_m": 4000,
        "ceiling_ft_est": 800,
    }
    changes = detect_changes(prev, curr)
    assert changes["details"]["wind_speed_delta_kt"] == 5
    assert changes["details"]["qnh_change_hpa"] == -2


def test_workload_score_category():
    result = workload_score(
        {
            "crosswind_ratio": 1.0,
            "gust_ratio": 1.0,
            "da_ratio": 1.0,
            "convective": 1.0,
            "night": 1.0,
            "rapid_change": 1.0,
        }
    )
    assert result["category"] == "High"


def test_stability_score_category():
    result = stability_score(
        {
            "wind_shift": 1.0,
            "gust_spread": 1.0,
            "metar_taf_mismatch": 1.0,
            "qnh_fall": 1.0,
            "speci": 1.0,
        }
    )
    assert result["category"] == "Unstable"


def test_compound_flags():
    flags = compound_flags(
        ["HIGH_DA", "CROSSWIND_HIGH", "GUSTY", "LOW_CEILING"],
        True,
        True,
        True,
        True,
    )
    assert "HIGH_DA_SHORT_RWY" in flags
    assert "CROSSWIND_HIGH_GUSTY" in flags
    assert "LOW_CEILING_NIGHT" in flags


def test_sun_times():
    date = dt.date(2024, 6, 1)
    times = sun_times(date, -26.0, 28.0)
    assert times["sunrise"] is not None
    assert times["sunset"] is not None
