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


def _fmt_corr(v: float) -> str:
    if pd.isna(v):
        return "N/A"
    return f"{v:.3f}"


def _color_return(v: str) -> str:
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


def _color_corr(v: str) -> str:
    if v == "N/A":
        return ""
    try:
        num = float(v)
    except (ValueError, AttributeError):
        return ""
    if num >= 0.7:
        return "background-color: #28a745; color: white"
    elif num >= 0.3:
        return "background-color: #d4edda"
    elif num >= -0.3:
        return ""
    elif num >= -0.7:
        return "background-color: #f8d7da"
    else:
        return "background-color: #dc3545; color: white"


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
    benchmark: str,
    base_prices: pd.Series,
    current_prices: pd.Series,
    ytd_returns: pd.Series,
    relative_returns: pd.Series,
    corr_df: pd.DataFrame,
    correlation_window: int,
) -> None:
    st.subheader("DAT Company Performance")

    # Index correlation data by ticker for easy lookup
    corr_lookup = {}
    if not corr_df.empty:
        corr_lookup = corr_df.set_index("Ticker").to_dict("index")

    pearson_col = f"{correlation_window}d Pearson w/ {benchmark}"
    spearman_col = f"{correlation_window}d Spearman w/ {benchmark}"

    rows = []
    for t in tickers:
        corr_row = corr_lookup.get(t, {})
        rows.append({
            "Ticker": t,
            "Base Price": _fmt_price(base_prices.get(t)),
            "Current Price": _fmt_price(current_prices.get(t)),
            "YTD Return": _fmt_pct(ytd_returns.get(t)),
            "Relative Return": _fmt_pct(relative_returns.get(t)),
            pearson_col: _fmt_corr(corr_row.get("Pearson Correlation")),
            spearman_col: _fmt_corr(corr_row.get("Spearman Correlation")),
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
        .map(_color_corr, subset=[pearson_col, spearman_col])
        .hide(axis="index")
    )

    st.dataframe(styled, width="stretch", hide_index=True)


def render_price_chart(
    close_df: pd.DataFrame,
    benchmark: str,
    tickers: list[str],
    base_date: pd.Timestamp,
) -> None:
    st.subheader("YTD Price")

    # Filter to YTD only
    ytd_df = close_df[close_df.index >= base_date].copy()
    if ytd_df.empty:
        st.info("No YTD data available for charting.")
        return

    # Clean index for Vega-Lite compatibility
    ytd_df.index = pd.to_datetime(ytd_df.index)
    ytd_df.index.name = None

    all_options = [benchmark] + tickers
    selected = st.pills(
        "Tickers",
        options=all_options,
        default=[benchmark],
        selection_mode="multi",
    )

    if not selected:
        st.info("Select at least one ticker to display.")
        return

    st.line_chart(ytd_df[list(selected)])
