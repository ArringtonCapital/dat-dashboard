"""Holdings data: load cached holdings.json and compute mNAV."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

HOLDINGS_PATH = Path(__file__).parent / "data" / "holdings.json"


def load_holdings(coin_type: str) -> dict:
    """Load holdings cache for a given coin type (bitcoin/ethereum/solana).

    Returns dict with keys: tickers (dict of per-ticker data), coin_price_usd, last_updated.
    Returns empty dict if file missing or coin_type not found.
    """
    if not HOLDINGS_PATH.exists():
        return {}
    with open(HOLDINGS_PATH) as f:
        data = json.load(f)
    return data.get(coin_type, {})


def compute_mnav(
    holdings_data: dict,
    tickers: list[str],
    current_prices: pd.Series,
    holdings_config: dict | None = None,
    coin_price_override: float | None = None,
) -> pd.DataFrame:
    """Compute debt-adjusted mNAV for each ticker.

    mNAV = Market Cap / (Coin Value + Cash - Non-Convertible Debt)

    When convertible_debt is specified in config, only the non-convertible
    portion of debt is subtracted (since diluted shares already account for
    conversion). When not specified, all debt is assumed convertible (safe
    default = no debt subtraction, avoids double-counting).

    Returns DataFrame with columns:
        Ticker, mNAV, Coin Held, Coin Source, Shares, Shares Type,
        Stock Price, Cash, Conv Debt, Non-Conv Debt, Coin Price,
        Holdings Updated
    """
    if holdings_config is None:
        holdings_config = {}

    ticker_data = holdings_data.get("tickers", {})
    coin_price = coin_price_override or holdings_data.get("coin_price_usd")

    if not ticker_data or not coin_price:
        return pd.DataFrame()

    rows = []
    for t in tickers:
        info = ticker_data.get(t)
        if not info:
            continue

        coin_held = info.get("coin_held")
        shares = info.get("shares_outstanding")
        if not coin_held or not shares:
            continue

        stock_price = current_prices.get(t)
        if pd.isna(stock_price) or stock_price is None:
            continue

        market_cap = shares * stock_price
        coin_value = coin_held * coin_price
        total_debt = info.get("total_debt") or 0
        total_cash = info.get("total_cash") or 0
        convertible_debt = holdings_config.get(t, {}).get("convertible_debt")

        if convertible_debt is not None:
            non_conv = max(0, total_debt - convertible_debt)
            adjusted_nav = coin_value + total_cash - non_conv
        else:
            non_conv = 0
            adjusted_nav = coin_value + total_cash

        mnav = market_cap / adjusted_nav if adjusted_nav > 0 else None

        rows.append({
            "Ticker": t,
            "mNAV": mnav,
            "Coin Held": coin_held,
            "Coin Source": info.get("coin_held_source", ""),
            "Shares": shares,
            "Shares Type": info.get("shares_type", "basic"),
            "Stock Price": stock_price,
            "Cash": total_cash,
            "Conv Debt": convertible_debt,
            "Non-Conv Debt": non_conv,
            "Coin Price": coin_price,
            "Holdings Updated": info.get("coin_held_updated", ""),
        })

    return pd.DataFrame(rows)
