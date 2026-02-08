from __future__ import annotations

from dataclasses import dataclass
from urllib.request import urlopen


@dataclass
class RawObservation:
    ident: str
    raw: str
    source: str
    observed_time_utc: str


class LiveMetarTafAdapter:
    metar_url = "https://aviationweather.gov/api/data/metar?ids={ident}&format=raw"
    taf_url = "https://aviationweather.gov/api/data/taf?ids={ident}&format=raw"

    def _fetch(self, url: str) -> str:
        with urlopen(url, timeout=10) as resp:
            return resp.read().decode("utf-8").strip()

    def fetch_metar(self, ident: str) -> RawObservation:
        raw = self._fetch(self.metar_url.format(ident=ident)).splitlines()[0].strip()
        return RawObservation(ident=ident, raw=raw, source="LIVE_BETA", observed_time_utc="")

    def fetch_taf(self, ident: str) -> RawObservation:
        raw = self._fetch(self.taf_url.format(ident=ident)).splitlines()[0].strip()
        return RawObservation(ident=ident, raw=raw, source="LIVE_BETA", observed_time_utc="")
