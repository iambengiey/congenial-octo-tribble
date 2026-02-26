from __future__ import annotations

import re

VALID_RE = re.compile(r"(?P<from>\d{4})/(?P<to>\d{4})")
CHANGE_RE = re.compile(r"\b(TEMPO|BECMG|PROB\d{2}|FM\d{4})\b")


def decode_taf(raw: str) -> dict:
    valid_from = ""
    valid_to = ""
    match = VALID_RE.search(raw)
    if match:
        valid_from = match.group("from")
        valid_to = match.group("to")

    changes = CHANGE_RE.findall(raw)
    summary = {
        "valid_from": valid_from,
        "valid_to": valid_to,
        "key_changes": changes,
    }

    return {"raw": raw, "summary": summary}
