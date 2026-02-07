from src.routes import bearing_deg, headwind_component


def test_bearing_east():
    assert round(bearing_deg(0, 0, 0, 1)) == 90


def test_headwind_component():
    headwind = headwind_component(90, 20, 90)
    assert headwind == 20.0
