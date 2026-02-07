from pathlib import Path

from src.yaml_loader import load_yaml


ROOT = Path(__file__).resolve().parents[1]


def test_aerodromes_schema():
    data = load_yaml((ROOT / "data" / "aerodromes.yaml").read_text(encoding="utf-8"))
    assert "aerodromes" in data
    for item in data["aerodromes"]:
        for key in ["ident", "elevation_m", "runways", "latitude_deg", "longitude_deg"]:
            assert key in item
        for runway in item["runways"]:
            for key in ["designator", "magnetic_heading_deg", "length_m", "surface"]:
                assert key in runway


def test_routes_schema():
    data = load_yaml((ROOT / "data" / "routes.yaml").read_text(encoding="utf-8"))
    assert "routes" in data
    for route in data["routes"]:
        for key in ["route_id", "dep", "dest", "alternates", "corridor_nm", "cruise_levels_ft"]:
            assert key in route
