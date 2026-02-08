from __future__ import annotations

import json
from pathlib import Path


class SampleWindsTempsAdapter:
    def __init__(self, winds_path: Path) -> None:
        self.winds_path = winds_path

    def fetch(self) -> dict:
        return json.loads(self.winds_path.read_text(encoding="utf-8"))
