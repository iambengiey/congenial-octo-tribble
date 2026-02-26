import datetime as dt
import math

from src.build.build_site import parse_taf_valid_to
from src.compute.density_altitude import density_altitude
from src.compute.route import bearing_deg, headwind_component
from src.compute.wind_components import wind_components


def test_wind_components_headwind():
    comp = wind_components(90, 10, 90)
    assert math.isclose(comp["headwind_kt"], 10.0, abs_tol=0.1)
    assert math.isclose(comp["crosswind_kt"], 0.0, abs_tol=0.1)


def test_density_altitude_standard():
    result = density_altitude(0, 1013.25, 15)
    assert abs(result["da_ft"]) < 100


def test_bearing_east():
    assert round(bearing_deg(0, 0, 0, 1)) == 90


def test_headwind_component():
    assert headwind_component(90, 20, 90) == 20.0


def test_parse_taf_valid_to_supports_24z_rollover():
    reference = dt.datetime(2026, 2, 12, 10, 0, tzinfo=dt.timezone.utc)
    result = parse_taf_valid_to("1224", reference)
    assert result == dt.datetime(2026, 2, 13, 0, 0, tzinfo=dt.timezone.utc)


def test_parse_taf_valid_to_rejects_invalid_hour():
    reference = dt.datetime(2026, 2, 12, 10, 0, tzinfo=dt.timezone.utc)
    assert parse_taf_valid_to("1260", reference) is None
