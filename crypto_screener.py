"""
crypto_screener.py — TradingView Crypto Pump/Dump Screener.
Scans crypto markets using TradingView screener filters,
generates AI trade setups, and sends early pump alerts via Telegram.
"""

import json
import os
import re
import time
from datetime import datetime, timezone, timedelta
from html import escape
from typing import Any

from tradingview_screener import crypto, col

CRYPTO_SCAN_INTERVAL = int(os.getenv("CRYPTO_SCAN_INTERVAL", "300"))
MAX_CANDIDATES = int(os.getenv("CRYPTO_MAX_CANDIDATES", "5"))

SEEN_KEYS_FILE = "crypto_screener_seen.json"

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
BOT_TOKEN2 = os.getenv("BOT_TOKEN2", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

COIN_NAME_CLEANUP = re.compile(r"[.].*$")

def load_seen_keys() -> set[str]:
    try:
        with open(SEEN_KEYS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()

def save_seen_keys(keys: set[str]) -> None:
    with open(SEEN_KEYS_FILE, "w") as f:
        json.dump(sorted(keys), f)

def _best_ai(prompt: str, system_prompt: str | None = None) -> str | None:
    result = _openai_chat(prompt, system_prompt)
    if result:
        return result
    return _groq_chat(prompt, system_prompt)

def _openai_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not OPENAI_API_KEY:
        return None
    try:
        import requests
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "gpt-4o-mini",
                "messages": messages,
                "max_tokens": 500,
            },
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def _groq_chat(prompt: str, system_prompt: str | None = None) -> str | None:
    if not GROQ_API_KEY:
        return None
    try:
        import requests
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        resp = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "llama-3.3-70b-versatile",
                "messages": messages,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        return None

def _extract_base_coin(ticker: str) -> str:
    parts = ticker.split(":")
    if len(parts) >= 2:
        pair = parts[-1]
        for suffix in ["USDT", "USD", "USDC", "EUR", "BTC", "ETH", "BUSD", "DAI"]:
            if pair.endswith(suffix):
                base = pair[: -len(suffix)]
                if base:
                    return base
        return pair
    return ticker

def scan_pump_candidates() -> list[dict[str, Any]]:
    """Query TradingView crypto screener with pump detection filters."""
    q = crypto()
    q = (q
        .select(
            'name', 'close', 'change', 'Perf.YTD',
            '24h_vol_change|5', '24h_vol|5',
            'RSI', 'Volume.1Y_Ratio',
        )
        .where(
            col('Perf.YTD') < -30,
            col('change') > 0,
            col('change') < 5,
            col('24h_vol_change|5') > 20,
        )
        .order_by('24h_vol_change|5', ascending=False)
        .limit(50))

    result = q.get_scanner_data()
    df = result[1]
    if df is None or df.empty:
        return []

    seen_coins: dict[str, dict] = {}
    for _, row in df.iterrows():
        ticker = str(row.get("ticker", ""))
        base = _extract_base_coin(ticker)
        if not base or base.upper() in {
            "USDT", "USD", "USDC", "USDD", "DAI", "BUSD", "TUSD",
            "BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE",
        }:
            continue
        name = str(row.get("name", base))
        close = row.get("close")
        if close is None or close == 0:
            continue
        if base not in seen_coins:
            seen_coins[base] = {
                "coin": base,
                "ticker": ticker,
                "name": name,
                "price": float(close),
                "change_24h": float(row.get("change", 0) or 0),
                "ytd": float(row.get("Perf.YTD", 0) or 0),
                "vol_change_24h": float(row.get("24h_vol_change|5", 0) or 0),
                "vol_24h": float(row.get("24h_vol|5", 0) or 0),
                "rsi": float(row.get("RSI", 50) or 50) if row.get("RSI") is not None else 50,
                "exchange": ticker.split(":")[0] if ":" in ticker else "CEX",
            }

    candidates = list(seen_coins.values())
    candidates.sort(key=lambda c: c["vol_change_24h"], reverse=True)
    return candidates[:MAX_CANDIDATES]

def generate_trade_setup(coin_data: dict[str, Any]) -> dict[str, Any]:
    """Generate percentage-based trade setup entry/TP/SL."""
    price = coin_data["price"]
    entry = round(price, 8)
    if price >= 1000:
        entry = round(price, 2)
    elif price >= 1:
        entry = round(price, 4)
    elif price >= 0.01:
        entry = round(price, 6)

    tp1 = round(entry * 1.05, _precision(entry))
    tp2 = round(entry * 1.10, _precision(entry))
    sl = round(entry * 0.97, _precision(entry))

    return {
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
    }

def _precision(price: float) -> int:
    if price >= 1000:
        return 2
    if price >= 1:
        return 4
    if price >= 0.01:
        return 6
    return 8

def ai_analyze_coin(coin: str, price: float, change_24h: float) -> str | None:
    """Get AI trading insight for a coin."""
    prompt = (
        f"Crypto coin: {coin}\n"
        f"Current price: ${price}\n"
        f"24h change: {change_24h:+.2f}%\n\n"
        "This coin is showing early pump signals: YTD < -30% (beaten down), "
        "24h change 0-5% (turning green), 24h volume change > 20% (volume surging).\n\n"
        "Give a 1-2 sentence trading insight:\n"
        "- Why this coin might be reversing\n"
        "- Key level to watch\n"
        "- Is this a high-risk pump or genuine reversal?\n"
        "Be concise. Max 30 words."
    )
    return _best_ai(prompt)

def format_crypto_alert(
    coin_data: dict[str, Any],
    setup: dict[str, Any],
    ai_insight: str | None,
) -> str:
    """Format a pump alert message matching the bot's template style."""
    coin = coin_data["coin"]
    price = coin_data["price"]
    change_24h = coin_data["change_24h"]
    ytd = coin_data["ytd"]
    vol_change = coin_data["vol_change_24h"]
    rsi = coin_data.get("rsi", 50)
    exchange = coin_data.get("exchange", "CEX")

    e = setup["entry"]
    t1 = setup["tp1"]
    t2 = setup["tp2"]
    s = setup["sl"]

    direction = "🟢 BUY"
    rr = round((t2 - e) / (e - s), 1) if (e - s) > 0 else 0

    signal_type = "PUMP WATCH" if vol_change > 50 else "EARLY PUMP"
    risk = "HIGH" if rsi < 30 else "MEDIUM" if rsi < 45 else "MODERATE"

    lines = [
        f"📡 *CryptoSignal Pro*  |  AI {signal_type}",
        "",
        f"*{coin}*  ·  {direction}  ·  H1",
        f"_{exchange} · Spot_",
        "",
        "━━━━━━━━━━━━━━━━━━",
        f"📌 Entry:      ${_ps(e)}",
        f"🛑 Stop Loss:  ${_ps(s)}  (-3.0%)",
        f"🎯 TP 1:       ${_ps(t1)}  (+5.0%)",
        f"🎯 TP 2:       ${_ps(t2)}  (+10.0%)",
        f"⚖️ R:R:        1 : {rr}",
        "━━━━━━━━━━━━━━━━━━",
        f"📊 *Market Data*",
        f"  24h Change:  {change_24h:+.2f}%",
        f"  YTD:         {ytd:+.2f}%",
        f"  24h Vol Δ:   +{vol_change:.0f}%",
        f"  RSI:         {rsi:.0f}  ({risk} risk)",
        "━━━━━━━━━━━━━━━━━━",
    ]

    if ai_insight:
        lines.append(f"🤖 *AI Analysis:* {_strip_md(ai_insight[:300])}")
        lines.append("")

    lines.extend([
        f"🔖 #{coin}  #crypto  #altcoin  #{'pump' if vol_change > 50 else 'earlysignal'}",
        "⚠️ _Not financial advice. Trade at your own risk._",
    ])

    return "\n".join(lines)

def _ps(val: float) -> str:
    if abs(val) >= 1000:
        return f"{val:,.2f}"
    if abs(val) >= 1:
        return f"{val:.4f}"
    if abs(val) >= 0.01:
        return f"{val:.6f}"
    return f"{val:.8f}"

def _strip_md(text: str) -> str:
    return re.sub(r'[*_`>#()\[\]\\<>]', '', text)

def send_telegram(text: str) -> bool:
    """Send message via Telegram HTTP API (fallback when bot instance not available)."""
    if not BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, data=payload, timeout=10)
        return resp.ok
    except Exception:
        return False

def send_telegram_bot2(text: str) -> bool:
    """Send via second bot token if available."""
    if not BOT_TOKEN2 or not TELEGRAM_CHAT_ID:
        return False
    try:
        import requests
        url = f"https://api.telegram.org/bot{BOT_TOKEN2}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": True,
        }
        resp = requests.post(url, data=payload, timeout=10)
        return resp.ok
    except Exception:
        return False

def run_scan_cycle() -> int:
    """Main scan cycle: scan, generate setups, send alerts."""
    seen = load_seen_keys()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    candidates = scan_pump_candidates()
    if not candidates:
        print(f"[CRYPTO SCREENER] No pump candidates found at {datetime.now(timezone.utc).strftime('%H:%M UTC')}")
        return 0

    sent = 0
    for coin_data in candidates:
        coin = coin_data["coin"]
        key = f"crypto_pump:{today}:{coin}"
        if key in seen:
            continue

        setup = generate_trade_setup(coin_data)
        ai_insight = ai_analyze_coin(coin, coin_data["price"], coin_data["change_24h"])
        message = format_crypto_alert(coin_data, setup, ai_insight)

        ok = send_telegram(message)
        if not ok:
            send_telegram_bot2(message)

        seen.add(key)
        save_seen_keys(seen)
        sent += 1
        print(f"[CRYPTO SCREENER] Alert sent for {coin} (vol Δ +{coin_data['vol_change_24h']:.0f}%)")

        if sent < len(candidates):
            time.sleep(2)

    print(f"[CRYPTO SCREENER] Sent {sent}/{len(candidates)} pump alerts")
    return sent

if __name__ == "__main__":
    run_scan_cycle()