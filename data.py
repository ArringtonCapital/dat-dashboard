from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf

PARQUET_PATH = Path(__file__).parent / "data" / "hourly_prices.parquet"


@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_price_data(
    tickers: tuple[str, ...], start_date: str
) -> tuple[pd.DataFrame, datetime]:
    """Download adjusted close prices from Yahoo Finance (daily).

    Returns (close_df, fetch_timestamp). close_df has DatetimeIndex rows and
    ticker columns. Uses auto_adjust so 'Close' is already adjusted.
    Used for correlations which need 60+ trading days of daily data.
    """
    raw = yf.download(
        list(tickers),
        start=start_date,
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    if raw.empty:
        return pd.DataFrame(), datetime.now(ZoneInfo("America/New_York"))

    # yfinance returns flat columns for a single ticker, MultiIndex for multiple
    if len(tickers) == 1:
        close_df = raw[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        close_df = raw["Close"]

    # Retry tickers that came back all-NaN (yfinance bulk download can fail silently)
    failed = [t for t in tickers if t in close_df.columns and close_df[t].isna().all()]
    for t in failed:
        single = yf.download(
            t, start=start_date, auto_adjust=True, progress=False
        )
        if not single.empty:
            close_df[t] = single["Close"]

    return close_df, datetime.now(ZoneInfo("America/New_York"))


@st.cache_data(ttl=300, show_spinner="Fetching hourly data...")
def fetch_hourly_data(
    tickers: tuple[str, ...], start_date: str
) -> tuple[pd.DataFrame, datetime]:
    """Load stored hourly parquet + fetch recent hourly data, merge both.

    The parquet file provides full YTD history (accumulated by GitHub Action).
    Fresh yfinance call provides the most recent hours. Overlap of 5 days
    ensures no gaps; duplicates are dropped keeping the freshest value.

    Returns (hourly_df, fetch_timestamp).
    """
    frames: list[pd.DataFrame] = []

    # Load stored parquet history
    if PARQUET_PATH.exists():
        stored = pd.read_parquet(PARQUET_PATH)
        if stored.index.tz is not None:
            stored.index = stored.index.tz_localize(None)
        # Filter to only requested tickers (columns that exist)
        available = [t for t in tickers if t in stored.columns]
        if available:
            frames.append(stored[available])

    # Fetch recent hourly from yfinance (last 5 days for overlap)
    raw = yf.download(
        list(tickers),
        period="5d",
        interval="1h",
        auto_adjust=True,
        threads=True,
        progress=False,
    )
    if not raw.empty:
        if len(tickers) == 1:
            fresh = raw[["Close"]].rename(columns={"Close": tickers[0]})
        else:
            fresh = raw["Close"]
        fresh.index = pd.to_datetime(fresh.index)
        if fresh.index.tz is not None:
            fresh.index = fresh.index.tz_localize(None)
        frames.append(fresh)

    if not frames:
        return pd.DataFrame(), datetime.now(ZoneInfo("America/New_York"))

    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")]
    combined = combined.sort_index()

    # Filter to start_date onward
    combined = combined[combined.index >= pd.Timestamp(start_date)]

    return combined, datetime.now(ZoneInfo("America/New_York"))


def get_base_prices(close_df: pd.DataFrame, base_date: date) -> pd.Series:
    """Get the close price on or immediately before base_date for each ticker.

    Handles weekends/holidays by looking backward up to 10 days.
    """
    target = pd.Timestamp(base_date)
    # Look backward for the most recent trading day on or before base_date
    mask = close_df.index <= target
    if not mask.any():
        return pd.Series(dtype=float)
    last_valid_date = close_df.index[mask][-1]
    return close_df.loc[last_valid_date]


def get_data_start_date(base_date: date, correlation_window: int = 60) -> str:
    """Return a start date far enough back for the correlation window.

    Need correlation_window trading days before base_date, plus buffer.
    Roughly 1.5x calendar days per trading day, plus 10-day holiday buffer.
    """
    calendar_days = int(correlation_window * 1.5) + 10
    return (base_date - timedelta(days=calendar_days)).isoformat()
