from __future__ import annotations


def workload_score(inputs: dict) -> dict:
    weights = {
        "crosswind_ratio": 25,
        "gust_ratio": 15,
        "da_ratio": 20,
        "convective": 20,
        "night": 10,
        "rapid_change": 10,
    }
    score = 0
    contributors = []
    for key, weight in weights.items():
        value = max(0.0, min(1.0, inputs.get(key, 0.0)))
        contribution = value * weight
        score += contribution
        if contribution > 0:
            contributors.append((key, round(contribution, 1)))

    score = round(min(100.0, score), 1)
    contributors.sort(key=lambda x: x[1], reverse=True)
    top = [item[0] for item in contributors[:3]]
    category = "Low"
    if score >= 66:
        category = "High"
    elif score >= 33:
        category = "Medium"
    return {"score": score, "category": category, "top_contributors": top}
