from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path

CONFIGS_DIR = Path(__file__).parent / "configs"


@dataclass(frozen=True)
class DashboardConfig:
    name: str
    benchmark: str
    tickers: tuple[str, ...]
    ytd_base_date: date
    correlation_window: int

    @property
    def all_tickers(self) -> tuple[str, ...]:
        """Benchmark + DAT tickers, deduplicated, for a single yfinance call."""
        seen: set[str] = set()
        result: list[str] = []
        for t in [self.benchmark] + list(self.tickers):
            if t not in seen:
                seen.add(t)
                result.append(t)
        return tuple(result)


def load_config(path: str | Path) -> DashboardConfig:
    with open(path) as f:
        raw = json.load(f)
    return DashboardConfig(
        name=raw["name"],
        benchmark=raw["benchmark"],
        tickers=tuple(raw["tickers"]),
        ytd_base_date=date.fromisoformat(raw["ytd_base_date"]),
        correlation_window=raw["correlation_window"],
    )


def list_configs() -> list[tuple[str, Path]]:
    """Return (display_name, path) for each JSON config in configs/ dir."""
    configs = []
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        with open(p) as f:
            raw = json.load(f)
        configs.append((raw["name"], p))
    return configs
