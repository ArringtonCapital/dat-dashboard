import pandas as pd
import streamlit as st

from calculations import (
    compute_relative_returns,
    compute_rolling_correlations,
    compute_ytd_returns,
)
from config import list_configs, load_config
from data import fetch_hourly_data, fetch_price_data, get_base_prices, get_data_start_date
from display import render_benchmark_header, render_dat_table, render_price_chart

# --- Page config ---
st.set_page_config(page_title="DAT Dashboard", layout="wide")

CUSTOM_CSS = """
<style>
    /* Reclaim wasted top padding + cap width */
    .stMainBlockContainer {
        padding-top: 1.5rem;
        max-width: 1400px;
        margin-left: auto;
        margin-right: auto;
    }

    /* Metric cards */
    [data-testid="stMetric"] {
        background-color: #F6F8FA;
        border: 1px solid #D0D7DE;
        border-radius: 8px;
        padding: 16px 20px;
    }
    [data-testid="stMetricValue"] {
        font-size: 1.8rem;
        font-weight: 600;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.85rem;
        color: #656D76;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }

    /* Title */
    h1 { font-weight: 600; letter-spacing: -0.02em; }

    /* Hide default chrome */
    #MainMenu { visibility: hidden; }
    footer { visibility: hidden; }
</style>
"""
st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# --- Config selection ---
configs = list_configs()
if len(configs) == 0:
    st.error("No config files found in configs/ directory.")
    st.stop()
elif len(configs) == 1:
    config = load_config(configs[0][1])
else:
    selected = st.sidebar.selectbox(
        "Select Dashboard",
        options=range(len(configs)),
        format_func=lambda i: configs[i][0],
    )
    config = load_config(configs[selected][1])

st.title(config.name)

# --- Fetch data ---
# Daily data: used for correlations (needs 60+ trading days)
daily_start = get_data_start_date(config.ytd_base_date, config.correlation_window)
close_df, _ = fetch_price_data(config.all_tickers, daily_start)

# Hourly data: used for YTD chart and fresher current prices
hourly_start = config.ytd_base_date.isoformat()
hourly_df, hourly_ts = fetch_hourly_data(config.all_tickers, hourly_start)

if close_df.empty:
    st.error("Failed to fetch market data from Yahoo Finance. Please try again later.")
    st.stop()

st.caption(f"Last updated: {hourly_ts:%Y-%m-%d %H:%M:%S}")

# --- Compute ---
base_prices = get_base_prices(close_df, config.ytd_base_date)

# Use hourly last row for fresher current prices, fall back to daily
if not hourly_df.empty:
    current_prices = hourly_df.iloc[-1]
else:
    current_prices = close_df.iloc[-1]

ytd_returns = compute_ytd_returns(current_prices, base_prices)
relative_returns = compute_relative_returns(ytd_returns, config.benchmark)
corr_df = compute_rolling_correlations(
    close_df, config.benchmark, list(config.tickers), config.correlation_window
)

# --- Render ---
render_benchmark_header(config.benchmark, base_prices, current_prices, ytd_returns)
st.divider()

col_left, col_right = st.columns([5, 6])

with col_left:
    render_dat_table(
        list(config.tickers),
        config.benchmark,
        base_prices,
        current_prices,
        ytd_returns,
        relative_returns,
        corr_df,
        config.correlation_window,
    )

with col_right:
    # Use hourly data for the chart if available, otherwise fall back to daily
    chart_df = hourly_df if not hourly_df.empty else close_df
    render_price_chart(
        chart_df,
        config.benchmark,
        list(config.tickers),
        pd.Timestamp(config.ytd_base_date),
    )
