from __future__ import annotations


def decode_sigmet(lines: list[str]) -> list[dict]:
    decoded = []
    for line in lines:
        tokens = line.split()
        decoded.append(
            {
                "raw": line,
                "type": tokens[0],
                "details": " ".join(tokens[1:]) if len(tokens) > 1 else "",
            }
        )
    return decoded
