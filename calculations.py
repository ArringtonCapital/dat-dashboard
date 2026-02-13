from __future__ import annotations

import pandas as pd


def compute_ytd_returns(
    current_prices: pd.Series, base_prices: pd.Series
) -> pd.Series:
    """(current / base) - 1 for each ticker."""
    return (current_prices / base_prices) - 1


def compute_relative_returns(
    ytd_returns: pd.Series, benchmark_ticker: str
) -> pd.Series:
    """Arithmetic difference: ticker_return - benchmark_return."""
    benchmark_return = ytd_returns.get(benchmark_ticker)
    if pd.isna(benchmark_return):
        return pd.Series(dtype=float)
    return ytd_returns - benchmark_return


def compute_rolling_correlations(
    close_df: pd.DataFrame,
    benchmark_ticker: str,
    dat_tickers: list[str],
    window: int = 60,
) -> pd.DataFrame:
    """Compute Pearson (rolling) correlation of daily returns.

    Returns DataFrame with columns: Ticker, Pearson Correlation.
    """
    daily_returns = close_df.pct_change(fill_method=None).iloc[1:]

    if benchmark_ticker not in daily_returns.columns:
        return pd.DataFrame(columns=["Ticker", "Pearson Correlation"])

    bench_returns = daily_returns[benchmark_ticker]
    rows = []

    for ticker in dat_tickers:
        if ticker not in daily_returns.columns:
            rows.append({"Ticker": ticker, "Pearson Correlation": None})
            continue

        ticker_returns = daily_returns[ticker]
        # Align and drop NaNs
        aligned = pd.concat([bench_returns, ticker_returns], axis=1).dropna()

        if len(aligned) < window:
            rows.append({"Ticker": ticker, "Pearson Correlation": None})
            continue

        recent = aligned.iloc[-window:]
        pearson = recent.iloc[:, 0].corr(recent.iloc[:, 1], method="pearson")

        rows.append({
            "Ticker": ticker,
            "Pearson Correlation": pearson,
        })

    return pd.DataFrame(rows)
