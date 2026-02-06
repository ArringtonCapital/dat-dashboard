from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
import yfinance as yf


@st.cache_data(ttl=300, show_spinner="Fetching market data...")
def fetch_price_data(
    tickers: tuple[str, ...], start_date: str
) -> tuple[pd.DataFrame, datetime]:
    """Download adjusted close prices from Yahoo Finance.

    Returns (close_df, fetch_timestamp). close_df has DatetimeIndex rows and
    ticker columns. Uses auto_adjust so 'Close' is already adjusted.
    """
    raw = yf.download(
        list(tickers),
        start=start_date,
        auto_adjust=True,
        threads=True,
        progress=False,
    )

    if raw.empty:
        return pd.DataFrame(), datetime.now()

    # yfinance returns flat columns for a single ticker, MultiIndex for multiple
    if len(tickers) == 1:
        close_df = raw[["Close"]].rename(columns={"Close": tickers[0]})
    else:
        close_df = raw["Close"]

    return close_df, datetime.now()


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
