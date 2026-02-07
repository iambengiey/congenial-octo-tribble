import math

from src.enrich import density_altitude_ft, wind_components


def test_wind_components_headwind():
    comp = wind_components(90, 10, 90)
    assert math.isclose(comp["headwind_kt"], 10.0, abs_tol=0.1)
    assert math.isclose(comp["crosswind_kt"], 0.0, abs_tol=0.1)
    assert comp["tailwind_kt"] == 0.0


def test_wind_components_crosswind():
    comp = wind_components(90, 10, 180)
    assert math.isclose(comp["crosswind_kt"], 10.0, abs_tol=0.1)
    assert comp["tailwind_kt"] == 0.0


def test_density_altitude_standard():
    result = density_altitude_ft(0, 1013.25, 15)
    assert abs(result["density_altitude_ft"]) < 100
