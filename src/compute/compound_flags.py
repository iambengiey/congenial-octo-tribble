from __future__ import annotations


def compound_flags(
    flags: list[str],
    runway_short: bool,
    night_ops: bool,
    taf_deteriorating: bool,
    rapid_qnh_fall: bool,
) -> list[str]:
    compounds = []
    if "HIGH_DA" in flags and runway_short:
        compounds.append("HIGH_DA_SHORT_RWY")
    if "CROSSWIND_HIGH" in flags and "GUSTY" in flags:
        compounds.append("CROSSWIND_HIGH_GUSTY")
    if "LOW_CEILING" in flags and night_ops:
        compounds.append("LOW_CEILING_NIGHT")
    if rapid_qnh_fall and taf_deteriorating:
        compounds.append("RAPID_QNH_FALL_TAF_DETERIORATING")
    return compounds
