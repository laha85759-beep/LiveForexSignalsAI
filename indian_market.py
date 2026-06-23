"""Indian stock market data fetcher using yfinance."""

from html import escape

import yfinance as yf

NIFTY_TICKER = "^NSEI"
SENSEX_TICKER = "^BSESN"
INDIA_VIX_TICKER = "^INDIAVIX"
BANK_NIFTY_TICKER = "^NSEBANK"

TOP_STOCKS = [
    "RELIANCE.NS",
    "TCS.NS",
    "HDFCBANK.NS",
    "INFY.NS",
    "ICICIBANK.NS",
    "HINDUNILVR.NS",
    "SBIN.NS",
    "BHARTIARTL.NS",
]


def fetch_index_data() -> dict[str, dict]:
    result: dict[str, dict] = {}
    tickers = {
        "Nifty 50": NIFTY_TICKER,
        "Sensex": SENSEX_TICKER,
        "India VIX": INDIA_VIX_TICKER,
        "Bank Nifty": BANK_NIFTY_TICKER,
    }
    for name, ticker in tickers.items():
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="2d")
            if hist.empty:
                continue
            last = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[0] if len(hist) > 1 else last
            change = last - prev_close
            pct = (change / prev_close) * 100 if prev_close else 0
            result[name] = {
                "price": round(last, 2),
                "change": round(change, 2),
                "pct": round(pct, 2),
            }
        except Exception:
            pass
    return result


def fetch_stock_data() -> list[dict]:
    results: list[dict] = []
    for ticker in TOP_STOCKS:
        try:
            tk = yf.Ticker(ticker)
            hist = tk.history(period="2d")
            if hist.empty:
                continue
            last = hist["Close"].iloc[-1]
            prev_close = hist["Close"].iloc[0] if len(hist) > 1 else last
            change = last - prev_close
            pct = (change / prev_close) * 100 if prev_close else 0
            name = ticker.replace(".NS", "")
            results.append({
                "symbol": name,
                "price": round(last, 2),
                "change": round(change, 2),
                "pct": round(pct, 2),
            })
        except Exception:
            pass
    return results


def format_market_snapshot() -> str | None:
    indices = fetch_index_data()
    if not indices:
        return None

    lines = ["<b>Indian Market Snapshot</b>"]
    for name, data in indices.items():
        arrow = "GREEN" if data["change"] >= 0 else "RED"
        lines.append(
            f"{arrow} <b>{name}:</b> {data['price']} "
            f"({'+' if data['change'] >= 0 else ''}{data['change']} | "
            f"{'+' if data['pct'] >= 0 else ''}{data['pct']}%)"
        )

    stocks = fetch_stock_data()
    if stocks:
        sorted_stocks = sorted(stocks, key=lambda s: abs(s["pct"]), reverse=True)
        gainers = [s for s in sorted_stocks if s["pct"] > 0][:3]
        losers = [s for s in sorted_stocks if s["pct"] < 0][:3]
        if gainers:
            lines.append(f"\n<b>Top Gainers:</b>")
            for s in gainers:
                lines.append(f"  + {s['symbol']}: {s['price']} (+{s['pct']}%)")
        if losers:
            lines.append(f"\n<b>Top Losers:</b>")
            for s in losers:
                lines.append(f"  - {s['symbol']}: {s['price']} ({s['pct']}%)")

    return "\n".join(lines)


US_INDICES = {
    "Dow Jones": "^DJI",
    "Nasdaq": "^IXIC",
    "S&P 500": "^GSPC",
}

COMMODITIES = {
    "Crude Oil": "CL=F",
    "Brent Oil": "BZ=F",
    "Gold": "GC=F",
    "Silver": "SI=F",
}

CRYPTO = {
    "Bitcoin": "BTC-USD",
    "Ethereum": "ETH-USD",
    "Solana": "SOL-USD",
    "XRP": "XRP-USD",
    "Cardano": "ADA-USD",
    "Dogecoin": "DOGE-USD",
    "Polkadot": "DOT-USD",
    "Avalanche": "AVAX-USD",
    "Chainlink": "LINK-USD",
    "Litecoin": "LTC-USD",
}

US_STOCKS = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "JPM"]


def fetch_ticker_price(ticker: str) -> dict | None:
    try:
        tk = yf.Ticker(ticker)
        hist = tk.history(period="2d")
        if hist.empty:
            return None
        last = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[0] if len(hist) > 1 else last
        change = last - prev_close
        pct = (change / prev_close) * 100 if prev_close else 0
        return {"price": round(last, 2), "change": round(change, 2), "pct": round(pct, 2)}
    except Exception:
        return None


def fetch_group_data(group: dict[str, str]) -> list[tuple[str, dict]]:
    results: list[tuple[str, dict]] = []
    for name, ticker in group.items():
        data = fetch_ticker_price(ticker)
        if data:
            results.append((name, data))
    return results


def format_group_snapshot(name: str, items: list[tuple[str, dict]]) -> str:
    lines = [f"<b>{name}</b>"]
    for label, data in items:
        arrow = "+" if data["change"] >= 0 else "-"
        sign = "+" if data["change"] >= 0 else ""
        lines.append(f"  {arrow} {label}: {data['price']} ({sign}{data['change']} | {sign}{data['pct']}%)")
    return "\n".join(lines)


def format_global_snapshot() -> str | None:
    parts: list[str] = []

    us = fetch_group_data(US_INDICES)
    if us:
        parts.append(format_group_snapshot("US Indices", us))

    commodities = fetch_group_data(COMMODITIES)
    if commodities:
        parts.append(format_group_snapshot("Commodities", commodities))

    crypto = fetch_group_data(CRYPTO)
    if crypto:
        parts.append(format_group_snapshot("Crypto", crypto))

    us_stocks_list = []
    for t in US_STOCKS:
        d = fetch_ticker_price(t)
        if d:
            us_stocks_list.append((t, d))
    if us_stocks_list:
        sorted_us = sorted(us_stocks_list, key=lambda x: abs(x[1]["pct"]), reverse=True)
        gainers = [s for s in sorted_us if s[1]["pct"] > 0][:3]
        losers = [s for s in sorted_us if s[1]["pct"] < 0][:3]
        lines = ["<b>US Stocks Movers</b>"]
        if gainers:
            for s, d in gainers:
                lines.append(f"  + {s}: {d['price']} (+{d['pct']}%)")
        if losers:
            for s, d in losers:
                lines.append(f"  - {s}: {d['price']} ({d['pct']}%)")
        if len(lines) > 1:
            parts.append("\n".join(lines))

    return "\n\n".join(parts) if parts else None


def format_nifty_options() -> str | None:
    try:
        tk = yf.Ticker(NIFTY_TICKER)
        hist = tk.history(period="1d")
        if hist.empty:
            return None
        spot = hist["Close"].iloc[-1]
        exps = tk.options
        if not exps:
            return None
        chain = tk.option_chain(exps[0])
        calls = chain.calls
        puts = chain.puts
        atm_strike = round(spot / 50) * 50
        near_calls = calls[calls["strike"].between(atm_strike - 150, atm_strike + 150)].head(3)
        near_puts = puts[puts["strike"].between(atm_strike - 150, atm_strike + 150)].head(3)

        lines = [f"<b>Nifty Options ({exps[0][:10]}):</b> Spot: {spot:.2f}"]
        lines.append(f"\n<b>Calls:</b>")
        for _, row in near_calls.iterrows():
            lines.append(f"  {int(row['strike'])} CE: {row['lastPrice']:.2f} | OI: {int(row['openInterest'])}")
        lines.append(f"\n<b>Puts:</b>")
        for _, row in near_puts.iterrows():
            lines.append(f"  {int(row['strike'])} PE: {row['lastPrice']:.2f} | OI: {int(row['openInterest'])}")
        return "\n".join(lines)
    except Exception:
        return None
