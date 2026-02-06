import streamlit as st

from calculations import (
    compute_relative_returns,
    compute_rolling_correlations,
    compute_ytd_returns,
)
from config import list_configs, load_config
from data import fetch_price_data, get_base_prices, get_data_start_date
from display import render_benchmark_header, render_correlation_table, render_dat_table

# --- Page config ---
st.set_page_config(page_title="DAT Dashboard", layout="wide")

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
start_date = get_data_start_date(config.ytd_base_date, config.correlation_window)
close_df, fetch_ts = fetch_price_data(config.all_tickers, start_date)

if close_df.empty:
    st.error("Failed to fetch market data from Yahoo Finance. Please try again later.")
    st.stop()

st.caption(f"Last updated: {fetch_ts:%Y-%m-%d %H:%M:%S}")

# --- Compute ---
base_prices = get_base_prices(close_df, config.ytd_base_date)
current_prices = close_df.iloc[-1]
ytd_returns = compute_ytd_returns(current_prices, base_prices)
relative_returns = compute_relative_returns(ytd_returns, config.benchmark)
corr_df = compute_rolling_correlations(
    close_df, config.benchmark, list(config.tickers), config.correlation_window
)

# --- Render ---
render_benchmark_header(config.benchmark, base_prices, current_prices, ytd_returns)
st.divider()
render_dat_table(list(config.tickers), base_prices, current_prices, ytd_returns, relative_returns)
st.divider()
render_correlation_table(corr_df)
