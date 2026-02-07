from __future__ import annotations

from dataclasses import dataclass
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


@dataclass
class TextProduct:
    ident: str
    lines: list[str]
    source: str


class TextAdapter(Protocol):
    def fetch(self, ident: str) -> TextProduct: ...


class SigmetAdapter(Protocol):
    def fetch(self) -> list[str]: ...


class UpperWindsAdapter(Protocol):
    def fetch(self) -> dict: ...


class SigwxAdapter(Protocol):
    def fetch(self) -> dict: ...
