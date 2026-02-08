from __future__ import annotations

from dataclasses import dataclass
from urllib.request import Request, urlopen


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
        request = Request(url, headers={"User-Agent": "METAR.oncloud.africa (training)"})
        with urlopen(request, timeout=10) as resp:
            return resp.read().decode("utf-8").strip()

    def fetch_metar(self, ident: str) -> RawObservation:
        raw = self._fetch(self.metar_url.format(ident=ident)).splitlines()[0].strip()
        if not raw:
            raw = self._fetch(
                f"https://tgftp.nws.noaa.gov/data/observations/metar/stations/{ident}.TXT"
            ).splitlines()[-1].strip()
        return RawObservation(ident=ident, raw=raw, source="LIVE_BETA", observed_time_utc="")

    def fetch_taf(self, ident: str) -> RawObservation:
        raw = self._fetch(self.taf_url.format(ident=ident)).splitlines()[0].strip()
        if not raw:
            raw = self._fetch(
                f"https://tgftp.nws.noaa.gov/data/forecasts/taf/stations/{ident}.TXT"
            ).splitlines()[-1].strip()
        return RawObservation(ident=ident, raw=raw, source="LIVE_BETA", observed_time_utc="")
