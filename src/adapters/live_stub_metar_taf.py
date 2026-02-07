from __future__ import annotations

<<<<<<< HEAD
from src.adapters.base import RawObservation


class LiveMetarTafStub:
    def fetch_metar(self, ident: str) -> RawObservation:
        raise NotImplementedError("Live METAR adapter not configured. Use SAMPLE mode.")

    def fetch_taf(self, ident: str) -> RawObservation:
        raise NotImplementedError("Live TAF adapter not configured. Use SAMPLE mode.")
=======
import json
import time
from pathlib import Path
from urllib.request import Request, urlopen

from src.adapters.base import RawObservation
from src.adapters.sample_metar_taf import SampleMetarTafAdapter

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "data" / "live_cache"


class LiveMetarTafStub:
    def __init__(self, metar_dir: Path, taf_dir: Path, cache_ttl_s: int = 300) -> None:
        self.sample = SampleMetarTafAdapter(metar_dir, taf_dir)
        self.cache_ttl_s = cache_ttl_s

    def _cache_path(self, kind: str, ident: str) -> Path:
        return CACHE_DIR / kind / f"{ident}.json"

    def _load_cache(self, kind: str, ident: str) -> str | None:
        path = self._cache_path(kind, ident)
        if not path.exists():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if time.time() - payload.get("fetched_at", 0) > self.cache_ttl_s:
            return None
        return payload.get("raw")

    def _save_cache(self, kind: str, ident: str, raw: str) -> None:
        path = self._cache_path(kind, ident)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"raw": raw, "fetched_at": time.time()}
        path.write_text(json.dumps(payload), encoding="utf-8")

    def _fetch_live(self, kind: str, ident: str) -> str:
        url = f"https://aviationweather.gov/api/data/{kind}?ids={ident}&format=raw"
        req = Request(url, headers={"User-Agent": "metar.oncloud.africa training fetch"})
        with urlopen(req, timeout=10) as resp:
            data = resp.read().decode("utf-8").strip()
        return data.splitlines()[0] if data else ""

    def _fetch(self, kind: str, ident: str) -> RawObservation:
        cached = self._load_cache(kind, ident)
        if cached:
            return RawObservation(ident=ident, raw=cached, source="LIVE_CACHE", observed_time_utc="")
        try:
            raw = self._fetch_live(kind, ident)
            if raw:
                self._save_cache(kind, ident, raw)
                return RawObservation(ident=ident, raw=raw, source="LIVE", observed_time_utc="")
        except Exception:
            pass
        sample = self.sample.fetch_metar(ident) if kind == "metar" else self.sample.fetch_taf(ident)
        return RawObservation(ident=ident, raw=sample.raw, source="SAMPLE_FALLBACK", observed_time_utc="")

    def fetch_metar(self, ident: str) -> RawObservation:
        return self._fetch("metar", ident)

    def fetch_taf(self, ident: str) -> RawObservation:
        return self._fetch("taf", ident)
>>>>>>> main
