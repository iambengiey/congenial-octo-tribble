from __future__ import annotations


def decode_notam(lines: list[str]) -> list[dict]:
    decoded = []
    for line in lines:
        parts = line.split(" ", 1)
        decoded.append({"id": parts[0], "text": parts[1] if len(parts) > 1 else ""})
    return decoded
