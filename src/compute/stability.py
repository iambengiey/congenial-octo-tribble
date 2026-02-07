from __future__ import annotations


def stability_score(inputs: dict) -> dict:
    penalties = {
        "wind_shift": 25,
        "gust_spread": 20,
        "metar_taf_mismatch": 20,
        "qnh_fall": 20,
        "speci": 15,
    }
    score = 100.0
    reasons = []
    for key, weight in penalties.items():
        value = max(0.0, min(1.0, inputs.get(key, 0.0)))
        deduction = value * weight
        score -= deduction
        if deduction > 0:
            reasons.append((key, round(deduction, 1)))

    score = round(max(0.0, score), 1)
    category = "Stable"
    if score < 40:
        category = "Unstable"
    elif score < 70:
        category = "Variable"
    reasons.sort(key=lambda x: x[1], reverse=True)
    return {"score": score, "category": category, "drivers": [r[0] for r in reasons[:3]]}
