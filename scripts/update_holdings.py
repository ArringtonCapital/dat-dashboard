"""Fetch coin holdings from CoinGecko + share data from yfinance.

Writes results to data/holdings.json. Run daily via GitHub Action or manually.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import yfinance as yf

CONFIGS_DIR = Path(__file__).parent.parent / "configs"
DATA_DIR = Path(__file__).parent.parent / "data"
HOLDINGS_PATH = DATA_DIR / "holdings.json"

COINGECKO_BASE = "https://api.coingecko.com/api/v3"


def fetch_coingecko_treasury(coin_type: str) -> list[dict]:
    """Fetch public treasury data from CoinGecko free API."""
    url = f"{COINGECKO_BASE}/companies/public_treasury/{coin_type}"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = json.loads(resp.read().decode())
    return data.get("companies", [])


def fetch_coin_price(coin_type: str) -> float | None:
    """Fetch current coin price from CoinGecko."""
    coin_id = {"bitcoin": "bitcoin", "ethereum": "ethereum", "solana": "solana"}[coin_type]
    url = f"{COINGECKO_BASE}/simple/price?ids={coin_id}&vs_currencies=usd"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode())
    return data.get(coin_id, {}).get("usd")


def get_ticker_data(ticker: str, ticker_config: dict | None = None) -> dict:
    """Get shares, debt, and cash from a single yfinance Ticker lookup.

    Share count priority:
    1. Config shares_override (manual correction when yfinance is wrong)
    2. quarterly_financials Diluted Average Shares (automated diluted)
    3. info sharesOutstanding (fallback basic)

    Returns dict with keys: shares, shares_type, total_debt, total_cash.
    """
    t = yf.Ticker(ticker)
    shares = None
    shares_type = "unknown"

    # 1. Config override takes precedence
    if ticker_config and ticker_config.get("shares_override"):
        shares = ticker_config["shares_override"]
        shares_type = ticker_config.get("shares_type_override", "manual")
    else:
        # 2. Try diluted shares from quarterly financials
        try:
            fins = t.quarterly_financials
            if fins is not None and not fins.empty and "Diluted Average Shares" in fins.index:
                row = fins.loc["Diluted Average Shares"]
                val = row.dropna().iloc[0] if not row.dropna().empty else None
                if val is not None and val > 0:
                    shares = int(val)
                    shares_type = "diluted"
        except Exception:
            pass

        # 3. Fallback to basic from info
        if shares is None:
            try:
                info_basic = t.info.get("sharesOutstanding")
                if info_basic and info_basic > 0:
                    shares = int(info_basic)
                    shares_type = "basic"
            except Exception:
                pass

    # Always fetch debt/cash from info (even if shares were overridden)
    total_debt = None
    total_cash = None
    try:
        info = t.info
        total_debt = info.get("totalDebt")
        total_cash = info.get("totalCash")
    except Exception:
        pass

    return {
        "shares": shares,
        "shares_type": shares_type,
        "total_debt": total_debt,
        "total_cash": total_cash,
    }


def load_configs() -> list[dict]:
    """Load all config files."""
    configs = []
    for p in sorted(CONFIGS_DIR.glob("*.json")):
        with open(p) as f:
            configs.append(json.load(f))
    return configs


def main() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    configs = load_configs()
    result = {"last_updated": now}

    for config in configs:
        coin_type = config.get("coin_type")
        if not coin_type:
            continue

        holdings_map = config.get("holdings", {})
        if not holdings_map:
            continue

        print(f"\n--- {coin_type.upper()} ---")

        # Fetch coin price
        coin_price = fetch_coin_price(coin_type)
        if not coin_price:
            print(f"  Failed to fetch {coin_type} price")
            continue
        print(f"  {coin_type} price: ${coin_price:,.2f}")

        # Fetch treasury data from CoinGecko
        companies = fetch_coingecko_treasury(coin_type)
        cg_by_symbol = {c["symbol"]: c for c in companies}

        tickers_data = {}

        for ticker, meta in holdings_map.items():
            cg_sym = meta.get("coingecko_symbol", "")
            company = cg_by_symbol.get(cg_sym)

            if company:
                coin_held = company.get("total_holdings", 0)
                source = "coingecko"
                # CoinGecko doesn't provide a per-company update date,
                # so we use today as the fetch date
                coin_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                print(f"  {ticker}: {coin_held:,.2f} {coin_type} (CoinGecko)")
            else:
                print(f"  {ticker}: NOT FOUND in CoinGecko ({cg_sym})")
                coin_held = None
                source = "missing"
                coin_updated = None

            # Get shares + debt/cash from yfinance
            yf_data = get_ticker_data(ticker, meta)
            shares = yf_data["shares"]
            shares_type = yf_data["shares_type"]
            shares_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if shares:
                print(f"    Shares: {shares:,} ({shares_type})")
            else:
                print(f"    Shares: NOT AVAILABLE")
            if yf_data["total_debt"] is not None:
                print(f"    Debt: ${yf_data['total_debt']:,.0f}  Cash: ${yf_data['total_cash'] or 0:,.0f}")

            entry = {
                "coin_held": coin_held,
                "coin_held_updated": coin_updated,
                "coin_held_source": source,
                "shares_outstanding": shares,
                "shares_type": shares_type,
                "shares_updated": shares_updated,
                "total_debt": yf_data["total_debt"],
                "total_cash": yf_data["total_cash"],
            }
            tickers_data[ticker] = entry

        result[coin_type] = {
            "coin_price_usd": coin_price,
            "last_updated": now,
            "tickers": tickers_data,
        }

    with open(HOLDINGS_PATH, "w") as f:
        json.dump(result, f, indent=2)
    print(f"\nSaved to {HOLDINGS_PATH}")


if __name__ == "__main__":
    main()
