from __future__ import annotations

from pathlib import Path

from src.yaml_loader import load_yaml

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
PACKS_DIR = DATA_DIR / "packs"


def _require_keys(item: dict, keys: list[str], label: str) -> None:
    for key in keys:
        if key not in item:
            raise ValueError(f"Missing {key} in {label}")


def validate_aerodromes(path: Path) -> None:
    data = load_yaml(path.read_text(encoding="utf-8"))
    for item in data.get("aerodromes", []):
        _require_keys(item, ["ident", "elevation_m", "latitude_deg", "longitude_deg", "runways"], "aerodrome")
        _require_keys(item, ["night_ops_allowed", "lighting", "ppr_required", "ops_hours", "notes"], "night ops")
        _require_keys(item, ["airspace_context", "circuit"], "airspace/circuit")
        for runway in item["runways"]:
            _require_keys(runway, ["designator", "magnetic_heading_deg", "length_m", "surface"], "runway")


def validate_routes(path: Path) -> None:
    data = load_yaml(path.read_text(encoding="utf-8"))
    for route in data.get("routes", []):
        _require_keys(route, ["route_id", "dep", "dest", "alternates", "corridor_nm", "cruise_levels_ft"], "route")


def validate_profiles(path: Path) -> None:
    data = load_yaml(path.read_text(encoding="utf-8"))
    for profile in data.get("profiles", []):
        _require_keys(profile, ["name", "licence_tier", "ratings", "operation_context", "thresholds"], "profile")
        _require_keys(
            profile["thresholds"],
            [
                "max_crosswind_kt",
                "max_tailwind_kt",
                "max_gust_spread_kt",
                "short_runway_m",
                "max_da_ft",
                "min_vis_m",
                "min_ceiling_ft",
            ],
            "thresholds",
        )


def validate_aircraft(path: Path) -> None:
    data = load_yaml(path.read_text(encoding="utf-8"))
    for item in data.get("aircraft", []):
        _require_keys(item, ["type", "demonstrated_crosswind_kt", "notes"], "aircraft")


def validate_all() -> None:
    validate_aerodromes(DATA_DIR / "aerodromes.yaml")
    validate_routes(DATA_DIR / "routes.yaml")
    validate_profiles(DATA_DIR / "profiles.yaml")
    validate_aircraft(DATA_DIR / "aircraft.yaml")

    for pack in PACKS_DIR.glob("*/aerodromes.yaml"):
        validate_aerodromes(pack)
    for pack_routes in PACKS_DIR.glob("*/routes.yaml"):
        validate_routes(pack_routes)


if __name__ == "__main__":
    validate_all()
