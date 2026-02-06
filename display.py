from __future__ import annotations

import pandas as pd
import streamlit as st


def _fmt_price(v: float) -> str:
    if pd.isna(v):
        return "N/A"
    return f"${v:.2f}"


def _fmt_pct(v: float) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{v:+.2%}"


def _color_return(v: str) -> str:
    """Light green/red background for return cells."""
    if v == "N/A":
        return ""
    try:
        num = float(v.replace("%", "").replace("+", "")) / 100
    except (ValueError, AttributeError):
        return ""
    if num > 0:
        return "background-color: #d4edda"
    elif num < 0:
        return "background-color: #f8d7da"
    return ""


def _color_relative(v: str) -> str:
    """Bold green/red background for relative return cells."""
    if v == "N/A":
        return ""
    try:
        num = float(v.replace("%", "").replace("+", "")) / 100
    except (ValueError, AttributeError):
        return ""
    if num > 0:
        return "background-color: #28a745; color: white; font-weight: bold"
    elif num < 0:
        return "background-color: #dc3545; color: white; font-weight: bold"
    return ""


def render_benchmark_header(
    benchmark: str,
    base_prices: pd.Series,
    current_prices: pd.Series,
    ytd_returns: pd.Series,
) -> None:
    st.subheader(f"Benchmark: {benchmark}")
    col1, col2, col3 = st.columns(3)
    base = base_prices.get(benchmark)
    current = current_prices.get(benchmark)
    ret = ytd_returns.get(benchmark)

    with col1:
        st.metric("Base Price (YTD Start)", _fmt_price(base))
    with col2:
        st.metric("Current Price", _fmt_price(current))
    with col3:
        delta_str = _fmt_pct(ret) if not pd.isna(ret) else None
        st.metric("YTD Return", _fmt_pct(ret), delta=delta_str)


def render_dat_table(
    tickers: list[str],
    base_prices: pd.Series,
    current_prices: pd.Series,
    ytd_returns: pd.Series,
    relative_returns: pd.Series,
) -> None:
    st.subheader("DAT Company Performance")

    rows = []
    for t in tickers:
        rows.append({
            "Ticker": t,
            "Base Price": _fmt_price(base_prices.get(t)),
            "Current Price": _fmt_price(current_prices.get(t)),
            "YTD Return": _fmt_pct(ytd_returns.get(t)),
            "Relative Return": _fmt_pct(relative_returns.get(t)),
        })

    df = pd.DataFrame(rows)

    # Sort by relative return (best to worst), handling N/A
    def _sort_key(val: str) -> float:
        if val == "N/A":
            return float("-inf")
        try:
            return float(val.replace("%", "").replace("+", ""))
        except (ValueError, AttributeError):
            return float("-inf")

    df["_sort"] = df["Relative Return"].map(_sort_key)
    df = df.sort_values("_sort", ascending=False).drop(columns="_sort").reset_index(drop=True)

    styled = (
        df.style
        .map(_color_return, subset=["YTD Return"])
        .map(_color_relative, subset=["Relative Return"])
        .hide(axis="index")
    )

    st.dataframe(styled, use_container_width=True, hide_index=True)


def render_correlation_table(corr_df: pd.DataFrame) -> None:
    st.subheader("Rolling Correlations with Benchmark")

    if corr_df.empty:
        st.info("Insufficient data for correlation calculations.")
        return

    display_df = corr_df.set_index("Ticker")

    styled = (
        display_df.style
        .format("{:.3f}", na_rep="N/A")
        .background_gradient(cmap="RdYlGn", vmin=-1, vmax=1, subset=pd.IndexSlice[:, :])
    )

    st.dataframe(styled, use_container_width=True)
