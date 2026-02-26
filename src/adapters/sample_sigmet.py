from __future__ import annotations

from pathlib import Path


class SampleSigmetAdapter:
    def __init__(self, sigmet_path: Path) -> None:
        self.sigmet_path = sigmet_path

    def fetch(self) -> list[str]:
        return [
            line.strip()
            for line in self.sigmet_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
