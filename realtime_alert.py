"""
realtime_alert.py — Real-time market monitoring via Finnhub WebSocket.
Runs as a standalone background process alongside the Telegram bot.
Sends instant alerts to Telegram when crash/market-moving events detected.
"""

import json
import os
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import requests
import yfinance as yf

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY", "").strip()
TELEGRAM_BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
TELEGRAM_BOT_TOKEN3 = os.getenv("BOT_TOKEN3", "").strip()
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")
TELEGRAM_CHAT_ID3 = os.getenv("TELEGRAM_CHAT_ID3", "").strip()

CRASH_KEYWORDS = [
    "crash", "plunge", "emergency", "recession", "bankrupt", "bankruptcy",
    "sanctions", "war", "invasion", "rate hike", "Hindenburg", "collapse",
    "selloff", "rout", "liquidation", "margin call", "flash crash",
    "default", "bailout", "downgrade", "fraud", "investigation",
    "freeze", "withdrawal halt", "crisis",
]

_monitored_prices: dict[str, float] = {}
_vix_baseline: float | None = None
_india_vix_baseline: float | None = None
_last_alert_time: dict[str, float] = {}


def _send_to_token(token: str, message: str, parse_mode: str = "Markdown", chat_id: str | None = None) -> bool:
    cid = chat_id or TELEGRAM_CHAT_ID
    if not cid:
        return False
    try:
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": cid, "text": message, "parse_mode": parse_mode}
        resp = requests.post(url, data=payload, timeout=10)
        return resp.ok
    except Exception:
        return False

def send_telegram_alert(message: str, parse_mode: str = "Markdown") -> bool:
    ok = _send_to_token(TELEGRAM_BOT_TOKEN, message, parse_mode)
    if TELEGRAM_BOT_TOKEN3:
        _send_to_token(TELEGRAM_BOT_TOKEN3, message, parse_mode, chat_id=TELEGRAM_CHAT_ID3 or TELEGRAM_CHAT_ID)
    return ok


def check_crash_news(article: dict[str, Any]) -> str | None:
    text = f"{article.get('headline', '')} {article.get('summary', '')}".lower()
    matched = [kw for kw in CRASH_KEYWORDS if kw.lower() in text]
    if not matched:
        return None

    headline = article.get("headline", "")
    source = article.get("source", "Finnhub")
    related = article.get("related", "")
    keywords_str = ", ".join(matched[:3])
    alert = (
        f"🚨 *CRASH ALERT* 🚨\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*{headline[:120]}*\n"
        f"📰 _{source}_\n"
        f"⚠️ Keywords: {keywords_str}\n"
    )
    if related:
        tickers = related.split(",")
        alert += f"📊 Related: {', '.join(tickers[:5])}\n"
    alert += (
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⏰ {datetime.now(timezone.utc).strftime('%H:%M UTC')}\n"
        f"🔖 #crashalert #urgent"
    )
    return alert


def check_vix_spike() -> str | None:
    global _vix_baseline, _india_vix_baseline
    now = time.time()
    alerts: list[str] = []

    # US VIX
    try:
        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if not hist.empty:
            current_vix = float(hist["Close"].iloc[-1])
            if _vix_baseline is None:
                _vix_baseline = current_vix
            spike_pct = ((current_vix - _vix_baseline) / _vix_baseline) * 100
            if spike_pct > 15 and "vix" not in _last_alert_time or (now - _last_alert_time.get("vix", 0)) > 3600:
                alerts.append(
                    f"⚠️ *VIX Spike Detected* ⚠️\n"
                    f"Current: {current_vix:.2f} (↑{spike_pct:.1f}%)\n"
                    f"Baseline: {_vix_baseline:.2f}\n"
                    f"High probability of sharp market movement.\n"
                    f"🔖 #vix #volatility #alert"
                )
                _last_alert_time["vix"] = now
    except Exception:
        pass

    # India VIX
    try:
        indiavix = yf.Ticker("^INDIAVIX")
        hist = indiavix.history(period="5d")
        if not hist.empty:
            current_india_vix = float(hist["Close"].iloc[-1])
            if _india_vix_baseline is None:
                _india_vix_baseline = current_india_vix
            spike_pct = ((current_india_vix - _india_vix_baseline) / _india_vix_baseline) * 100
            if spike_pct > 15 and "india_vix" not in _last_alert_time or (now - _last_alert_time.get("india_vix", 0)) > 3600:
                alerts.append(
                    f"⚠️ *India VIX Spike Detected* ⚠️\n"
                    f"Current: {current_india_vix:.2f} (↑{spike_pct:.1f}%)\n"
                    f"Baseline: {_india_vix_baseline:.2f}\n"
                    f"Potential sharp NSE/BSE movement ahead.\n"
                    f"🔖 #indiaVIX #volatility #alert"
                )
                _last_alert_time["india_vix"] = now
    except Exception:
        pass

    return "\n\n".join(alerts) if alerts else None


def check_premarket_gap() -> str | None:
    try:
        now_ist = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        # Check GIFT Nifty before market open (before 9:15 AM IST)
        if not (6 <= now_ist.hour < 9) or (now_ist.hour == 9 and now_ist.minute >= 15):
            return None

        prev_close = None
        current_price = None

        # Get Nifty futures from GIFT Nifty symbol
        gift_nifty = yf.Ticker("NIFTY_50_FUTURE")
        hist = gift_nifty.history(period="2d")
        if len(hist) >= 2:
            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(hist["Close"].iloc[0])

        if current_price and prev_close:
            gap_pct = ((current_price - prev_close) / prev_close) * 100
            gap_pts = current_price - prev_close
            direction = "🔴 Gap-Down" if gap_pts < 0 else "🟢 Gap-Up"
            key = f"premarket_{now_ist.strftime('%Y%m%d')}"
            if abs(gap_pct) > 0.3 and (key not in _last_alert_time or (time.time() - _last_alert_time.get(key, 0)) > 7200):
                _last_alert_time[key] = time.time()
                return (
                    f"📊 *PRE-MARKET ALERT* — {now_ist.strftime('%d %b %Y')}\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"{direction} on GIFT Nifty\n"
                    f"Points: {gap_pts:+.0f} ({gap_pct:+.2f}%)\n"
                    f"⏰ NSE/BSE opens in ~{60 - now_ist.hour * 60 - now_ist.minute}m\n\n"
                    f"⚠️ Prepare for {'bearish' if gap_pts < 0 else 'bullish'} open.\n"
                    f"🔖 #premarket #NSE #BSE #GIFTNifty"
                )
    except Exception:
        pass
    return None


def check_price_drop(symbol: str, current_price: float, threshold_pct: float = -1.0) -> str | None:
    global _monitored_prices
    prev = _monitored_prices.get(symbol)
    if prev is None:
        _monitored_prices[symbol] = current_price
        return None

    change_pct = ((current_price - prev) / prev) * 100
    if change_pct <= threshold_pct:
        key = f"drop_{symbol}"
        now = time.time()
        if key not in _last_alert_time or (now - _last_alert_time.get(key, 0)) > 1800:
            _last_alert_time[key] = now
            direction = "🔴 SHARP DROP" if change_pct < 0 else "🟢 SHARP RISE"
            return (
                f"{direction} DETECTED\n"
                f"━━━━━━━━━━━━━━━\n"
                f"*{symbol}*: {prev:.4f} → {current_price:.4f}\n"
                f"Change: {change_pct:+.2f}%\n"
                f"⏰ {datetime.now(timezone.utc).strftime('%H:%M:%S UTC')}\n"
                f"🔖 #alert #{symbol}"
            )

    _monitored_prices[symbol] = current_price
    return None


def check_economic_calendar_alert() -> str | None:
    try:
        # Use the existing forexfactory_calendar module
        import importlib
        try:
            ffcal = importlib.import_module("forexfactory_calendar")
        except Exception:
            return None

        events = ffcal.get_upcoming_high_impact(hours_ahead=1, target_currencies={"USD", "INR", "EUR", "GBP", "JPY"})
        now = datetime.now(timezone.utc)

        for ev in events:
            dt = ev.get("datetime")
            if not dt:
                continue
            mins_until = int((dt - now).total_seconds() / 60)
            if 3 <= mins_until <= 7:  # Alert 3-7 minutes before
                key = f"cal_alert:{ev['country']}:{ev['title']}:{dt.strftime('%Y%m%d_%H%M')}"
                if key not in _last_alert_time or (time.time() - _last_alert_time.get(key, 0)) > 86400:
                    _last_alert_time[key] = time.time()
                    impact_icon = "🔴 HIGH" if ev["impact"] == "high" else "🟡 MED"
                    return (
                        f"📅 *ECONOMIC EVENT INCOMING* — {mins_until} min\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"*{ev['title']}*\n"
                        f"🌍 {ev['country']}  ·  {impact_icon}\n"
                        f"📈 Forecast: {ev.get('forecast', 'N/A')}\n"
                        f"📉 Previous: {ev.get('previous', 'N/A')}\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"⚡ Prepare for volatility.\n"
                        f"🔖 #economiccalendar #{ev['country']} #forex"
                    )
    except Exception:
        pass
    return None


# ── WebSocket Listener ──────────────────────────────────────────────────────


def _on_message(ws, message: str) -> None:
    try:
        data = json.loads(message)

        # Type 1: Breaking News
        if data.get("type") == "news":
            for article in data.get("data", []):
                alert = check_crash_news(article)
                if alert:
                    send_telegram_alert(alert)

        # Type 2: Trade data (price updates)
        elif data.get("type") == "trade":
            for trade in data.get("data", []):
                symbol = trade.get("s", "")
                price = trade.get("p")
                if symbol and price:
                    alert = check_price_drop(symbol, float(price))
                    if alert:
                        send_telegram_alert(alert)

    except Exception as e:
        print(f"[WS ERROR] {e}")


def _on_error(ws, error) -> None:
    print(f"[WS] Error: {error}")


def _on_close(ws, close_status_code, close_msg) -> None:
    print(f"[WS] Connection closed. Reconnecting in 10s...")


def _on_open(ws) -> None:
    print("[WS] Connected to Finnhub WebSocket")
    ws.send(json.dumps({"type": "subscribe", "symbol": "news"}))
    ws.send(json.dumps({"type": "subscribe", "symbol": "OANDA:USD_INR"}))
    ws.send(json.dumps({"type": "subscribe", "symbol": "OANDA:EUR_USD"}))
    ws.send(json.dumps({"type": "subscribe", "symbol": "OANDA:XAU_USD"}))
    ws.send(json.dumps({"type": "subscribe", "symbol": "OANDA:BTC_USD"}))
    for sym in ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "TSLA", "RELIANCE.NS", "TCS.NS"]:
        ws.send(json.dumps({"type": "subscribe", "symbol": sym}))


def run_websocket() -> None:
    import websocket as ws_lib
    socket_url = f"wss://ws.finnhub.io?token={FINNHUB_API_KEY}"
    ws = ws_lib.WebSocketApp(
        socket_url,
        on_message=_on_message,
        on_error=_on_error,
        on_close=_on_close,
        on_open=_on_open,
    )
    ws.run_forever(reconnect=10)


def start_websocket_thread() -> threading.Thread:
    t = threading.Thread(target=run_websocket, daemon=True)
    t.start()
    return t


# ── Polling-based checks (for job queue integration) ──────────────────────

polling_checks = [
    ("vix_monitor", check_vix_spike, 300),
    ("premarket", check_premarket_gap, 120),
    ("calendar", check_economic_calendar_alert, 60),
]


def run_polling_cycle() -> int:
    """Run all polling checks. Returns count of alerts sent."""
    sent = 0
    for name, check_fn, _ in polling_checks:
        try:
            alert = check_fn()
            if alert:
                if send_telegram_alert(alert):
                    sent += 1
                    print(f"[ALERT] {name}: alert sent")
        except Exception as e:
            print(f"[ALERT] {name} error: {e}")
    return sent
