from __future__ import annotations

from collections import defaultdict


def flag_severity(flags: list[str], severity_map: dict) -> dict:
    level = "OK"
    if any(flag in severity_map.get("warning", []) for flag in flags):
        level = "WARNING"
    elif any(flag in severity_map.get("caution", []) for flag in flags):
        level = "CAUTION"
    return {"level": level, "flags": flags}


def summarize_flags(flags: list[str]) -> str:
    if not flags:
        return "LOW_RISK"
    return flags[0]


def flag_counts(flags: list[str]) -> dict:
    counts = defaultdict(int)
    for flag in flags:
        counts[flag] += 1
    return dict(counts)
