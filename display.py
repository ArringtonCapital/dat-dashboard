from __future__ import annotations

import altair as alt
import pandas as pd
import streamlit as st

CHART_COLORS = ["#5B9BD5", "#E06C75", "#98C379", "#D19A66", "#C678DD", "#56B6C2", "#ABB2BF"]


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


def _section_header(title: str) -> None:
    st.markdown(
        f'<p style="color: #656D76; font-size: 0.85rem; text-transform: uppercase; '
        f'letter-spacing: 0.08em; margin-bottom: 0.5rem; border-bottom: 1px solid #D0D7DE; '
        f'padding-bottom: 0.5rem;">{title}</p>',
        unsafe_allow_html=True,
    )


def render_benchmark_header(
    benchmark: str,
    base_prices: pd.Series,
    current_prices: pd.Series,
    ytd_returns: pd.Series,
) -> None:
    st.markdown(
        f'<p style="color: #656D76; font-size: 0.9rem; margin-bottom: 0.25rem; '
        f'text-transform: uppercase; letter-spacing: 0.05em;">Benchmark</p>'
        f'<p style="font-size: 1.4rem; font-weight: 600; margin-top: 0;">{benchmark}</p>',
        unsafe_allow_html=True,
    )
    col1, col2, col3 = st.columns(3)
    base = base_prices.get(benchmark)
    current = current_prices.get(benchmark)
    ret = ytd_returns.get(benchmark)

    with col1:
        st.metric("YTD Start Price", _fmt_price(base))
    with col2:
        st.metric("Current Price", _fmt_price(current))
    with col3:
        st.metric("YTD Return", _fmt_pct(ret))


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
    _section_header("DAT Company Performance")

    # Index correlation data by ticker for easy lookup
    corr_lookup = {}
    if not corr_df.empty:
        corr_lookup = corr_df.set_index("Ticker").to_dict("index")

    pearson_col = f"{correlation_window}d Corr w/ {benchmark}"

    rows = []
    for t in tickers:
        corr_row = corr_lookup.get(t, {})
        rows.append({
            "Ticker": t,
            "YTD Start Price": _fmt_price(base_prices.get(t)),
            "Current Price": _fmt_price(current_prices.get(t)),
            "YTD Return": _fmt_pct(ytd_returns.get(t)),
            "Relative Return": _fmt_pct(relative_returns.get(t)),
            pearson_col: _fmt_corr(corr_row.get("Pearson Correlation")),
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
        .map(_color_corr, subset=[pearson_col])
        .hide(axis="index")
    )

    st.dataframe(styled, width="stretch", hide_index=True, height=450)


def render_price_chart(
    close_df: pd.DataFrame,
    benchmark: str,
    tickers: list[str],
    base_date: pd.Timestamp,
    key: str = "",
) -> None:
    _section_header("YTD Price")

    # Filter to YTD only
    ytd_df = close_df[close_df.index >= base_date].copy()
    if ytd_df.empty:
        st.info("No YTD data available for charting.")
        return

    # Clean index for Vega-Lite compatibility
    ytd_df.index = pd.to_datetime(ytd_df.index)
    ytd_df.index.name = "Date"

    # Reserve space for the chart, render controls below it
    chart_slot = st.container()

    all_options = [benchmark] + tickers
    selected = st.pills(
        "Tickers",
        options=all_options,
        default=[benchmark],
        selection_mode="multi",
        key=f"pills_{key}",
    )

    if not selected:
        st.info("Select at least one ticker to display.")
        return

    mode = st.radio(
        "Display", ["YTD Return (%)", "Price ($)"], horizontal=True, label_visibility="collapsed",
        key=f"radio_{key}",
    )

    plot_df = ytd_df[list(selected)].ffill()
    if mode == "YTD Return (%)":
        first_valid = plot_df.bfill().iloc[0]
        plot_df = (plot_df / first_valid - 1) * 100
        value_name = "Return (%)"
    else:
        value_name = "Price ($)"

    chart_data = plot_df.reset_index().melt(
        id_vars="Date", var_name="Ticker", value_name=value_name
    )

    chart = (
        alt.Chart(chart_data)
        .mark_line(strokeWidth=2)
        .encode(
            x=alt.X("Date:T", axis=alt.Axis(
                format="%b %d",
                labelColor="#656D76",
                titleColor="#656D76",
                gridColor="#E8E8E8",
            )),
            y=alt.Y(f"{value_name}:Q", axis=alt.Axis(
                labelColor="#656D76",
                titleColor="#656D76",
                gridColor="#E8E8E8",
            )),
            color=alt.Color("Ticker:N", scale=alt.Scale(range=CHART_COLORS)),
            tooltip=["Date:T", "Ticker:N", alt.Tooltip(f"{value_name}:Q", format=".2f")],
        )
        .properties(height=340)
        .configure_view(strokeWidth=0)
        .configure_legend(
            labelColor="#656D76",
            titleColor="#656D76",
        )
    )

    with chart_slot:
        st.altair_chart(chart, width="stretch", theme=None)
