from __future__ import annotations


def cloud_base_ft(temp_c: float | None, dewpoint_c: float | None) -> int | None:
    if temp_c is None or dewpoint_c is None:
        return None
    spread = temp_c - dewpoint_c
    return int(round(spread * 400))
