from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass
class RawObservation:
    ident: str
    raw: str
    source: str
    observed_time_utc: str


class MetarTafAdapter(Protocol):
    def fetch_metar(self, ident: str) -> RawObservation: ...

    def fetch_taf(self, ident: str) -> RawObservation: ...


class SampleMetarTafAdapter:
    def __init__(self, samples_dir: Path) -> None:
        self.samples_dir = samples_dir

    def _read(self, prefix: str, ident: str) -> str:
        path = self.samples_dir / f"{prefix}_{ident}.txt"
        return path.read_text(encoding="utf-8").strip()

    def fetch_metar(self, ident: str) -> RawObservation:
        raw = self._read("metar", ident)
        return RawObservation(ident=ident, raw=raw, source="SAMPLE", observed_time_utc="")

    def fetch_taf(self, ident: str) -> RawObservation:
        raw = self._read("taf", ident)
        return RawObservation(ident=ident, raw=raw, source="SAMPLE", observed_time_utc="")


class HttpMetarTafAdapter:
    def __init__(self, metar_url_template: str, taf_url_template: str) -> None:
        self.metar_url_template = metar_url_template
        self.taf_url_template = taf_url_template

    def _fetch(self, url: str) -> str:
        import requests

        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.text.strip()

    def fetch_metar(self, ident: str) -> RawObservation:
        raw = self._fetch(self.metar_url_template.format(ident=ident))
        return RawObservation(ident=ident, raw=raw, source="LIVE", observed_time_utc="")

    def fetch_taf(self, ident: str) -> RawObservation:
        raw = self._fetch(self.taf_url_template.format(ident=ident))
        return RawObservation(ident=ident, raw=raw, source="LIVE", observed_time_utc="")


@dataclass
class TextProduct:
    ident: str
    lines: list[str]
    source: str


class TextAdapter(Protocol):
    def fetch(self, ident: str) -> TextProduct: ...


class SampleTextAdapter:
    def __init__(self, samples_dir: Path, prefix: str) -> None:
        self.samples_dir = samples_dir
        self.prefix = prefix

    def fetch(self, ident: str) -> TextProduct:
        path = self.samples_dir / f"{self.prefix}_{ident}.txt"
        lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return TextProduct(ident=ident, lines=lines, source="SAMPLE")


class SigmetAdapter(Protocol):
    def fetch(self) -> list[dict]: ...


class SampleJsonAdapter:
    def __init__(self, json_path: Path, source_label: str = "SAMPLE") -> None:
        self.json_path = json_path
        self.source_label = source_label

    def fetch(self) -> list[dict]:
        import json

        data = json.loads(self.json_path.read_text(encoding="utf-8"))
        for item in data:
            item["source"] = self.source_label
        return data


class UpperWindsAdapter(Protocol):
    def fetch(self) -> dict: ...


class SampleUpperWindsAdapter:
    def __init__(self, json_path: Path) -> None:
        self.json_path = json_path

    def fetch(self) -> dict:
        import json

        data = json.loads(self.json_path.read_text(encoding="utf-8"))
        data["source"] = "SAMPLE"
        return data
