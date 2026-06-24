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


def _build_options_suggestion(
    ticker: str,
    index_name: str,
    strike_round: int = 50,
    range_width: int = 200,
) -> str | None:
    """Build an options trade suggestion for a given index ticker."""
    try:
        tk = yf.Ticker(ticker)
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

        atm_strike = round(spot / strike_round) * strike_round

        atm_calls = calls[calls["strike"].between(atm_strike - range_width, atm_strike + range_width)]
        atm_puts = puts[puts["strike"].between(atm_strike - range_width, atm_strike + range_width)]

        if atm_calls.empty and atm_puts.empty:
            return None

        call_oi = atm_calls["openInterest"].sum() if not atm_calls.empty else 0
        put_oi = atm_puts["openInterest"].sum() if not atm_puts.empty else 0
        pcr = put_oi / call_oi if call_oi > 0 else 0

        if pcr > 1.3:
            suggestion = "Bearish sentiment (high PCR). Consider buying PUTS for hedging or downside protection."
            direction = "BEARISH"
        elif pcr < 0.7:
            suggestion = "Bullish sentiment (low PCR). Consider buying CALLS for upside potential."
            direction = "BULLISH"
        else:
            max_oi_strike = None
            max_oi = 0
            for df in [atm_calls, atm_puts]:
                if not df.empty:
                    idx = df["openInterest"].idxmax()
                    row = df.loc[idx]
                    if row["openInterest"] > max_oi:
                        max_oi = row["openInterest"]
                        max_oi_strike = int(row["strike"])
            direction = "NEUTRAL"
            if max_oi_strike:
                suggestion = (
                    f"Market range-bound. Max OI at {max_oi_strike}. "
                    "Consider Iron Condor or wait for breakout above/below this level."
                )
            else:
                suggestion = "Market range-bound. Wait for clear breakout direction."

        expiry_label = exps[0][:10]

        lines = [
            f"<b>{index_name} OPTIONS SUGGESTION</b>",
            "----------------------------------------",
            f"<b>Spot:</b> {spot:.2f}",
            f"<b>ATM Strike:</b> {atm_strike}",
            f"<b>Expiry:</b> {expiry_label}",
            f"<b>PCR (Put-Call Ratio):</b> {pcr:.2f}",
            f"<b>Outlook:</b> {direction}",
            "",
        ]

        if not atm_calls.empty:
            lines.append("<b>Top Call OI:</b>")
            top_calls = atm_calls.nlargest(3, "openInterest")
            for _, row in top_calls.iterrows():
                lines.append(
                    f"  {int(row['strike'])} CE: {row['lastPrice']:.2f} | "
                    f"OI: {int(row['openInterest'])}"
                )

        if not atm_puts.empty:
            lines.append(f"\n<b>Top Put OI:</b>")
            top_puts = atm_puts.nlargest(3, "openInterest")
            for _, row in top_puts.iterrows():
                lines.append(
                    f"  {int(row['strike'])} PE: {row['lastPrice']:.2f} | "
                    f"OI: {int(row['openInterest'])}"
                )

        lines.append(f"\n<b>Trade Suggestion:</b> {suggestion}")

        return "\n".join(lines)
    except Exception:
        return None


def format_nifty_options_suggestion() -> str | None:
    return _build_options_suggestion(NIFTY_TICKER, "Nifty", strike_round=50, range_width=200)


def format_sensex_options_suggestion() -> str | None:
    return _build_options_suggestion(SENSEX_TICKER, "Sensex", strike_round=100, range_width=500)
