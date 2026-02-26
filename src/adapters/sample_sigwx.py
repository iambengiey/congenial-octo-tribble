from __future__ import annotations

from pathlib import Path


class SampleSigwxAdapter:
    def __init__(self, sigwx_dir: Path) -> None:
        self.sigwx_dir = sigwx_dir

    def fetch(self) -> dict:
        low = self.sigwx_dir / "low_sigwx.svg"
        high = self.sigwx_dir / "high_sigwx.svg"
        return {
            "low": low,
            "high": high,
            "source": "SAMPLE",
        }
