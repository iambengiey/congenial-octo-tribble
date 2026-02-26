from __future__ import annotations

from pathlib import Path

from src.adapters.base import RawObservation


class SampleMetarTafAdapter:
    def __init__(self, metar_dir: Path, taf_dir: Path) -> None:
        self.metar_dir = metar_dir
        self.taf_dir = taf_dir

    def _read(self, directory: Path, ident: str) -> str:
        path = directory / f"{ident}.txt"
        if not path.exists():
            return f"{ident} 010000Z 00000KT CAVOK 20/10 Q1013 NOSIG"
        return path.read_text(encoding="utf-8").strip()

    def fetch_metar(self, ident: str) -> RawObservation:
        raw = self._read(self.metar_dir, ident)
        return RawObservation(ident=ident, raw=raw, source="SAMPLE", observed_time_utc="")

    def fetch_taf(self, ident: str) -> RawObservation:
        raw = self._read(self.taf_dir, ident)
        return RawObservation(ident=ident, raw=raw, source="SAMPLE", observed_time_utc="")
