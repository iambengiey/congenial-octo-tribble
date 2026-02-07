from __future__ import annotations

from pathlib import Path

from src.adapters.base import TextProduct


class SampleNotamAdapter:
    def __init__(self, notam_dir: Path) -> None:
        self.notam_dir = notam_dir

    def fetch(self, ident: str) -> TextProduct:
        path = self.notam_dir / f"{ident}.txt"
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return TextProduct(ident=ident, lines=lines, source="SAMPLE")
