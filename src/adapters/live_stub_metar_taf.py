from __future__ import annotations

from src.adapters.base import RawObservation


class LiveMetarTafStub:
    def fetch_metar(self, ident: str) -> RawObservation:
        raise NotImplementedError("Live METAR adapter not configured. Use SAMPLE mode.")

    def fetch_taf(self, ident: str) -> RawObservation:
        raise NotImplementedError("Live TAF adapter not configured. Use SAMPLE mode.")
