"""Fetch hourly close prices and merge into persistent parquet file.

Run daily via GitHub Action or manually to build up YTD hourly history.
Yahoo Finance only serves ~60 days of hourly data, so we accumulate over time.
"""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import yfinance as yf

CONFIGS_DIR = Path(__file__).parent.parent / "configs"
DATA_DIR = Path(__file__).parent.parent / "data"
PARQUET_PATH = DATA_DIR / "hourly_prices.parquet"


def load_tickers() -> list[str]:
    """Load all unique tickers from every config file."""
    tickers: list[str] = []
    seen: set[str] = set()
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        with open(p) as f:
            raw = json.load(f)
        for t in [raw["benchmark"]] + raw["tickers"]:
            if t not in seen:
                seen.add(t)
                tickers.append(t)
    return tickers


def fetch_hourly(tickers: list[str], days: int = 59) -> pd.DataFrame:
    """Fetch hourly close data for the last `days` days."""
    raw = yf.download(
        tickers,
        period=f"{days}d",
        interval="1h",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    if raw.empty:
        return pd.DataFrame()

    if len(tickers) == 1:
        close_df = raw[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        close_df = raw["Close"]

    close_df.index = pd.to_datetime(close_df.index)
    return close_df


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)

    tickers = load_tickers()
    print(f"Fetching hourly data for: {tickers}")

    fresh = fetch_hourly(tickers)
    if fresh.empty:
        print("No data fetched from Yahoo Finance.")
        return

    if PARQUET_PATH.exists():
        existing = pd.read_parquet(PARQUET_PATH)
        # Ensure both have timezone-naive index for clean merge
        if existing.index.tz is not None:
            existing.index = existing.index.tz_localize(None)
        if fresh.index.tz is not None:
            fresh.index = fresh.index.tz_localize(None)
        combined = pd.concat([existing, fresh])
        combined = combined[~combined.index.duplicated(keep="last")]
        combined = combined.sort_index()
    else:
        if fresh.index.tz is not None:
            fresh.index = fresh.index.tz_localize(None)
        combined = fresh

    combined.to_parquet(PARQUET_PATH)
    print(f"Saved {len(combined)} rows to {PARQUET_PATH}")


if __name__ == "__main__":
    main()
