import asyncio
import json
import os
from datetime import datetime, time, timedelta, timezone
from html import escape
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

import yfinance as yf

from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

import massive_data

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

BOT_TOKEN = os.getenv("BOT_TOKEN", "PLACEHOLDER_TOKEN_REVOKED").strip()
TELEGRAM_CHAT_ID = "6207722743"
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "").strip()
MASSIVE_API_KEY = os.getenv("MASSIVE_API_KEY", "").strip()
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "auto").strip().lower()
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "900"))
HIGH_IMPACT_CHECK_INTERVAL = int(os.getenv("HIGH_IMPACT_CHECK_INTERVAL", "60"))

SENT_KEYS_FILE = "sent_articles.json"
SIGNAL_LOG_FILE = "signal_log.json"
_seen_keys: set[str] = set()
_signal_log: list[dict] = []

FOREX_QUERY = os.getenv(
    "FOREX_QUERY",
    'forex OR "foreign exchange" OR (dollar AND fed) OR (euro AND ecb) OR '
    '(pound AND boe) OR (yen AND boj) OR (gold AND fed) OR (rupee AND rbi) OR '
    '(bitcoin OR btc OR ethereum OR eth OR crypto OR solana OR ripple OR cardano OR dogecoin) OR '
    '(crude oil OR brent OR wti) OR (silver) OR (nasdaq OR "dow jones" OR "s&p 500")',
)

INDIA_MARKET_QUERY = os.getenv(
    "INDIA_MARKET_QUERY",
    '(sensex OR nifty OR "indian market" OR "india stock" OR "bse" OR "nse" OR '
    '"rbi" OR "rupee" OR "sebi" OR "indian economy") AND (india OR mumbai)',
)

INTRADAY_STOCK_QUERY = os.getenv(
    "INTRADAY_STOCK_QUERY",
    '(reliance OR tcs OR hdfc OR infosys OR icici OR "hindustan unilever" OR sbi OR '
    'bharti OR "intraday" OR "stock market today" OR "opening bell" OR "closing bell") '
    'AND (india OR "bse" OR "nse" OR "bombay stock exchange")',
)

FOREX_TERMS = {
    "forex",
    "currency",
    "currencies",
    "fx",
    "usd",
    "dollar",
    "eur",
    "euro",
    "gbp",
    "pound",
    "jpy",
    "yen",
    "xau",
    "gold",
    "silver",
    "xag",
    "crude",
    "oil",
    "brent",
    "wti",
    "fed",
    "ecb",
    "boe",
    "boj",
    "rate hike",
    "rate cut",
    "inflation",
    "cpi",
    "nonfarm payrolls",
    "inr",
    "rupee",
    "rbi",
    "sensex",
    "nifty",
    "india market",
    "bse",
    "nse",
    "bitcoin",
    "btc",
    "ethereum",
    "eth",
    "solana",
    "sol",
    "ripple",
    "xrp",
    "cardano",
    "ada",
    "dogecoin",
    "doge",
    "polkadot",
    "dot",
    "avalanche",
    "avax",
    "chainlink",
    "link",
    "polygon",
    "matic",
    "crypto",
    "cryptocurrency",
    "nasdaq",
    "dow jones",
    "s&p",
    "sp500",
    "wall street",
    "us30",
    "us100",
    "reliance",
    "tcs",
    "hdfc",
    "infosys",
    "icici",
    "sbi",
    "bharti",
    "nifty 50",
    "sensex",
    "bank nifty",
}

CURRENCY_HINTS = {
    "USD": ("usd", "dollar", "fed", "treasury"),
    "EUR": ("eur", "euro", "ecb"),
    "GBP": ("gbp", "pound", "boe", "bank of england"),
    "JPY": ("jpy", "yen", "boj", "bank of japan"),
    "XAU": ("xau", "gold", "bullion"),
    "XAG": ("xag", "silver"),
    "OIL": ("crude", "oil", "brent", "wti"),
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth"),
    "SOL": ("solana", "sol"),
    "XRP": ("ripple", "xrp"),
    "ADA": ("cardano", "ada"),
    "DOGE": ("dogecoin", "doge"),
    "DOT": ("polkadot", "dot"),
    "AVAX": ("avalanche", "avax"),
    "LINK": ("chainlink", "link"),
    "LTC": ("litecoin", "ltc"),
    "INR": ("inr", "rupee", "rbi", "india", "sensex", "nifty"),
    "US30": ("dow jones", "us30", "djia"),
    "US100": ("nasdaq", "us100", "ixic"),
    "NIFTY": ("nifty", "nifty 50", "nse"),
    "SENSEX": ("sensex", "bse", "bombay stock exchange"),
    "RELIANCE": ("reliance", "ril"),
    "TCS": ("tcs", "tata consultancy"),
    "HDFCBANK": ("hdfc bank", "hdfcbank"),
    "INFY": ("infosys", "infy"),
    "ICICIBANK": ("icici bank", "icicibank"),
    "SBIN": ("sbi", "state bank"),
    "BHARTI": ("bharti", "airtel"),
    "WIPRO": ("wipro",),
    "ITC": ("itc",),
    "LT": ("larsen", "l&t", "larsen & toubro"),
    "AXISBANK": ("axis bank", "axis"),
    "KOTAKBANK": ("kotak", "kotak mahindra", "kotak bank"),
    "MARUTI": ("maruti", "maruti suzuki"),
    "TATAMOTORS": ("tata motors", "tata motor"),
    "ASIANPAINT": ("asian paints", "asian paint"),
    "HCLTECH": ("hcl", "hcl technologies", "hcl tech"),
    "SUNPHARMA": ("sun pharma", "sun pharmaceutical"),
    "BAJFINANCE": ("bajaj finance",),
    "TITAN": ("titan",),
    "NTPC": ("ntpc",),
    "ONGC": ("ongc",),
    "POWERGRID": ("power grid", "powergrid"),
    "ULTRACEMCO": ("ultratech", "ultratech cement", "ultracemco"),
}

TRADE_PAIRS = {
    "USD": [("EUR/USD", -1, 0.0001), ("USD/JPY", 1, 0.01), ("GBP/USD", -1, 0.0001), ("USD/CAD", 1, 0.0001)],
    "EUR": [("EUR/USD", 1, 0.0001), ("EUR/GBP", 1, 0.0001)],
    "GBP": [("GBP/USD", 1, 0.0001), ("EUR/GBP", -1, 0.0001)],
    "JPY": [("USD/JPY", -1, 0.01)],
    "XAU": [("XAU/USD", 1, 0.1)],
    "XAG": [("XAG/USD", 1, 0.01)],
    "OIL": [("WTI", 1, 0.01), ("BRENT", 1, 0.01)],
    "BTC": [("BTC/USD", 1, 1.0)],
    "ETH": [("ETH/USD", 1, 1.0)],
    "SOL": [("SOL/USD", 1, 0.01)],
    "XRP": [("XRP/USD", 1, 0.0001)],
    "ADA": [("ADA/USD", 1, 0.0001)],
    "DOGE": [("DOGE/USD", 1, 0.0001)],
    "DOT": [("DOT/USD", 1, 0.001)],
    "AVAX": [("AVAX/USD", 1, 0.01)],
    "LINK": [("LINK/USD", 1, 0.01)],
    "LTC": [("LTC/USD", 1, 0.01)],
    "INR": [("USD/INR", 1, 0.01)],
    "US30": [("US30", 1, 1.0)],
    "US100": [("US100", 1, 1.0)],
    "NIFTY": [("NIFTY", 1, 1.0)],
    "SENSEX": [("SENSEX", 1, 1.0)],
}

INSTRUMENT_NAMES: dict[str, str] = {
    "XAU/USD": "Gold vs US Dollar",
    "XAG/USD": "Silver vs US Dollar",
    "EUR/USD": "Euro vs US Dollar",
    "GBP/USD": "British Pound vs US Dollar",
    "USD/JPY": "US Dollar vs Japanese Yen",
    "USD/CAD": "US Dollar vs Canadian Dollar",
    "EUR/GBP": "Euro vs British Pound",
    "WTI": "Crude Oil WTI",
    "BRENT": "Brent Crude Oil",
    "BTC/USD": "Bitcoin vs US Dollar",
    "ETH/USD": "Ethereum vs US Dollar",
    "SOL/USD": "Solana vs US Dollar",
    "XRP/USD": "Ripple vs US Dollar",
    "ADA/USD": "Cardano vs US Dollar",
    "DOGE/USD": "Dogecoin vs US Dollar",
    "DOT/USD": "Polkadot vs US Dollar",
    "AVAX/USD": "Avalanche vs US Dollar",
    "LINK/USD": "Chainlink vs US Dollar",
    "LTC/USD": "Litecoin vs US Dollar",
    "USD/INR": "US Dollar vs Indian Rupee",
    "US30": "Dow Jones Industrial Average",
    "US100": "NASDAQ 100",
    "NIFTY": "Nifty 50",
    "SENSEX": "BSE Sensex",
}

FOREX_PRICE_API = "https://api.exchangerate-api.com/v4/latest/USD"

POSITIVE_KEYWORDS = {
    "rises",
    "rise",
    "gains",
    "gain",
    "surges",
    "surge",
    "strengthens",
    "strong",
    "hawkish",
    "beats",
    "beat",
    "higher",
    "upside",
    "rally",
    "rallies",
    "breakout",
    "bullish",
    "recovery",
    "rebound",
    "upgrade",
}

NEGATIVE_KEYWORDS = {
    "falls",
    "fall",
    "drops",
    "drop",
    "slides",
    "slide",
    "weakens",
    "weak",
    "dovish",
    "misses",
    "miss",
    "lower",
    "downside",
    "cut",
    "crash",
    "plunge",
    "decline",
    "bearish",
    "selloff",
    "downgrade",
    "slump",
}

HIGH_IMPACT_KEYWORDS = {
    "breaking", "just in", "urgent", "emergency",
    "fed rate decision", "fomc", "interest rate decision",
    "nonfarm payrolls", "nfp", "jobs report",
    "cpi", "consumer price index", "inflation data",
    "gdp", "economic growth",
    "crash", "plunge", "selloff", "rout",
    "war", "invasion", "sanctions",
    "central bank", "rate hike", "rate cut",
    "recession", "depression",
    "bankruptcy", "bailout",
    "black swan", "flash crash",
    "market crash", "stock crash",
    "fed emergency", "emergency meeting",
}

TRADING_SYSTEM_PROMPT = (
    "You are a professional Telegram trading signal bot. "
    "You generate clear, actionable trade setups with entry, targets, and stop-loss levels. "
    "You are concise, factual, and never give financial advice — only data-driven setups. "
    "Always state the direction, pair, entry price, TP1, TP2, and SL. "
    "Keep financial terms in English. "
    "Use bullet points or numbered lists for readability."
)


def load_seen_keys() -> set[str]:
    try:
        with open(SENT_KEYS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_keys(keys: set[str]) -> None:
    with open(SENT_KEYS_FILE, "w") as f:
        json.dump(sorted(keys), f)


def load_signal_log() -> list[dict]:
    try:
        with open(SIGNAL_LOG_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_signal_log(log: list[dict]) -> None:
    with open(SIGNAL_LOG_FILE, "w") as f:
        json.dump(log, f, indent=2)


def log_signal(pair: str, direction: str, entry: float, tp1: float, tp2: float, sl: float, source: str) -> None:
    global _signal_log
    record = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "time": datetime.now(timezone.utc).strftime("%H:%M UTC"),
        "pair": pair,
        "direction": direction,
        "entry": entry,
        "tp1": tp1,
        "tp2": tp2,
        "sl": sl,
        "source": source,
    }
    _signal_log.append(record)
    save_signal_log(_signal_log)


def get_active_provider() -> str:
    if NEWS_PROVIDER in {"newsdata", "newsapi"}:
        return NEWS_PROVIDER
    if NEWS_API_KEY:
        return "newsapi"
    return "newsdata"


def build_newsdata_url(query: str) -> str:
    params = {
        "apikey": NEWSDATA_API_KEY,
        "q": query,
        "language": "en",
        "category": "business",
    }
    return f"{NEWSDATA_API_URL}?{urlencode(params)}"


def build_newsapi_url(query: str) -> str:
    params = {
        "apiKey": NEWS_API_KEY,
        "q": query,
        "language": "en",
        "sortBy": "publishedAt",
        "pageSize": "25",
    }
    return f"{NEWSAPI_URL}?{urlencode(params)}"


def normalize_newsdata_article(article: dict[str, Any]) -> dict[str, Any]:
    return {
        "article_id": article.get("article_id") or article.get("link") or article.get("title"),
        "title": article.get("title"),
        "description": article.get("description"),
        "link": article.get("link"),
        "pubDate": article.get("pubDate"),
        "source_name": article.get("source_name"),
        "keywords": article.get("keywords") or [],
    }


def normalize_newsapi_article(article: dict[str, Any]) -> dict[str, Any]:
    source = article.get("source") or {}
    return {
        "article_id": article.get("url") or article.get("title") or article.get("publishedAt"),
        "title": article.get("title"),
        "description": article.get("description") or article.get("content"),
        "link": article.get("url"),
        "pubDate": article.get("publishedAt"),
        "source_name": source.get("name") or "Unknown source",
        "keywords": [],
    }


def article_key(article: dict[str, Any]) -> str:
    return str(
        article.get("article_id")
        or article.get("link")
        or article.get("title")
        or article.get("pubDate")
        or ""
    )


def normalize_text(article: dict[str, Any]) -> str:
    parts = [
        article.get("title") or "",
        article.get("description") or "",
        " ".join(article.get("keywords") or []),
        article.get("source_name") or "",
    ]
    return " ".join(parts).lower()


def is_forex_relevant(article: dict[str, Any]) -> bool:
    text = normalize_text(article)
    return any(term in text for term in FOREX_TERMS)


def identify_asset(article: dict[str, Any]) -> str:
    text = normalize_text(article)
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text for hint in hints):
            return symbol
    return "MARKET"


def infer_bias_signal(article: dict[str, Any]) -> str | None:
    text = normalize_text(article)

    subject = None
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text for hint in hints):
            subject = symbol
            break

    if not subject:
        return None

    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)

    if score == 0:
        return None

    direction = "Bullish" if score > 0 else "Bearish"
    return f"{direction} {subject}"


def fetch_current_prices() -> dict[str, float]:
    rates: dict[str, float] = {}
    try:
        with urlopen(FOREX_PRICE_API, timeout=10) as r:
            data = json.load(r)
        base_rates = data.get("rates", {})
        usd_base = {"USD": 1.0} | base_rates
        for asset, pairs in TRADE_PAIRS.items():
            for pair, _, _ in pairs:
                if pair in rates:
                    continue
                if "/" not in pair:
                    continue
                base, quote = pair.split("/")
                b_rate = usd_base.get(base)
                q_rate = usd_base.get(quote)
                if b_rate and q_rate:
                    rates[pair] = q_rate / b_rate
    except Exception:
        pass

    yf_map = {
        "XAU/USD": "GC=F",
        "XAG/USD": "SI=F",
        "WTI": "CL=F",
        "BRENT": "BZ=F",
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "SOL/USD": "SOL-USD",
        "XRP/USD": "XRP-USD",
        "ADA/USD": "ADA-USD",
        "DOGE/USD": "DOGE-USD",
        "DOT/USD": "DOT-USD",
        "AVAX/USD": "AVAX-USD",
        "LINK/USD": "LINK-USD",
        "LTC/USD": "LTC-USD",
        "US30": "^DJI",
        "US100": "^IXIC",
        "DXY": "DX-Y.NYB",
        "NIFTY": "^NSEI",
        "SENSEX": "^BSESN",
    }
    try:
        for pair, ticker in yf_map.items():
            if pair not in rates:
                tk = yf.Ticker(ticker)
                hist = tk.history(period="1d")
                if not hist.empty:
                    rates[pair] = round(float(hist["Close"].iloc[-1]), 2)
    except Exception:
        pass

    return rates


def compute_confidence(text: str) -> tuple[str, str]:
    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)
    abs_score = abs(score)
    if abs_score >= 4:
        level = "High"
    elif abs_score >= 2:
        level = "Medium"
    else:
        level = "Low"
    direction = "Bullish" if score > 0 else "Bearish"
    return direction, level


def is_high_impact(article: dict[str, Any]) -> bool:
    text = normalize_text(article)
    return any(kw in text for kw in HIGH_IMPACT_KEYWORDS)


def format_trade_lines(bias: str, source: str = "news") -> str | None:
    parts = bias.split()
    if len(parts) != 2:
        return None
    direction_str, asset = parts[0], parts[1]
    pairs = TRADE_PAIRS.get(asset)
    if not pairs:
        return None
    is_bullish = direction_str == "Bullish"
    prices = fetch_current_prices()
    lines: list[str] = []
    for i, (pair, multiplier, pip_size) in enumerate(pairs, 1):
        price = prices.get(pair)
        if not price:
            lines.append(f"{i}. {pair}")
            continue
        is_buy = (is_bullish == (multiplier > 0))
        entry = round(price, 4)
        tp1 = round(price + (30 * pip_size) if is_buy else price - (30 * pip_size), 4)
        tp2 = round(price + (50 * pip_size) if is_buy else price - (50 * pip_size), 4)
        sl = round(price - (20 * pip_size) if is_buy else price + (20 * pip_size), 4)
        dir_label = "BUY" if is_buy else "SELL"
        icon = " 🟢" if is_buy else " 🔴"
        lines.append(f"{i}.{icon} {dir_label} {pair} @ {_price_str(entry, pair)}")
        lines.append(f"   Targets: {_price_str(tp1, pair)} / {_price_str(tp2, pair)} | SL: {_price_str(sl, pair)}")
        log_signal(pair, dir_label, entry, tp1, tp2, sl, source)
    return "\n".join(lines) if lines else None


def detect_asset_in_text(text: str) -> str | None:
    text_lower = text.lower()
    for symbol, hints in CURRENCY_HINTS.items():
        if any(hint in text_lower for hint in hints):
            return symbol
    return None


def ai_verify_trade_suggestion(trade_text: str, asset: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    prompt = (
        "You are an expert trading analyst. Verify this trade suggestion:\n"
        f"{trade_text}\n\n"
        f"Is this a reasonable trade setup for {asset}? "
        "Consider current market conditions. "
        "Reply: 'APPROVED - [reason]' or 'REJECTED - [reason]'. "
        "Be concise - max 2 sentences."
    )
    return _groq_chat(prompt)


def ai_enhance_trade_suggestion(trade_text: str, context_title: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    prompt = (
        "You are an expert trading analyst improving a trade suggestion.\n"
        f"Current suggestion:\n{trade_text}\n\n"
        f"News context: {context_title}\n\n"
        "Review this suggestion for:\n"
        "1. Direction correctness based on the news\n"
        "2. Sensible entry/TP/SL levels\n"
        "3. Risk management quality\n\n"
        "If it is already good, reply 'OK'.\n"
        "If it needs improvement, provide the improved version. "
        "Keep the same format (BUY/SELL, @, Targets:, SL). "
        "Max 2 sentences of explanation."
    )
    result = _groq_chat(prompt)
    if result and result.strip().upper() == "OK":
        return None
    return result


def generate_asset_trade_setup(asset: str, question: str) -> str | None:
    pairs = TRADE_PAIRS.get(asset)
    if not pairs:
        return None

    prices = fetch_current_prices()

    dir_prompt = (
        f"Based on this question: '{question}'\n"
        f"Should we go LONG (buy) or SHORT (sell) {asset}? "
        "Reply with only one word: LONG or SHORT."
    )
    direction = _groq_chat(dir_prompt, system_prompt=TRADING_SYSTEM_PROMPT)
    if not direction:
        return None
    is_bullish = "LONG" in direction.strip().upper()

    lines: list[str] = []
    for i, (pair, multiplier, pip_size) in enumerate(pairs, 1):
        price = prices.get(pair)
        if not price:
            lines.append(f"{i}. {pair} - price unavailable")
            continue
        is_buy = (is_bullish == (multiplier > 0))
        entry = round(price, 4)
        tp1 = round(price + (30 * pip_size) if is_buy else price - (30 * pip_size), 4)
        tp2 = round(price + (50 * pip_size) if is_buy else price - (50 * pip_size), 4)
        sl = round(price - (20 * pip_size) if is_buy else price + (20 * pip_size), 4)
        dir_label = "BUY" if is_buy else "SELL"
        icon = " 🟢" if is_buy else " 🔴"
        lines.append(f"{i}.{icon} {dir_label} {pair} @ {_price_str(entry, pair)}")
        lines.append(f"   Targets: {_price_str(tp1, pair)} / {_price_str(tp2, pair)} | SL: {_price_str(sl, pair)}")
        log_signal(pair, dir_label, entry, tp1, tp2, sl, "question")

    if not lines:
        return None

    trade_text = "\n".join(lines)
    verification = ai_verify_trade_suggestion(trade_text, asset)

    result = [f"<b>Real-Time Setup ({asset}):</b>", trade_text]
    if verification:
        result.append(f"\n<b>AI Verification:</b> {verification}")

    return "\n".join(result)


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
        text = resp.json()["choices"][0]["message"]["content"].strip()
        return escape(text)
    except Exception:
        return None


def build_market_context() -> str:
    ctx_parts: list[str] = []
    try:
        prices = fetch_current_prices()
        key_prices = {
            "XAU/USD": prices.get("XAU/USD"),
            "US100": prices.get("US100"),
            "EUR/USD": prices.get("EUR/USD"),
            "BTC/USD": prices.get("BTC/USD"),
        }
        for name, price in key_prices.items():
            if price:
                ctx_parts.append(f"{name}: {price}")
    except Exception:
        pass
    if not ctx_parts:
        return ""
    return "Current prices: " + ", ".join(ctx_parts) + "."


def ai_analyze_news(article: dict[str, Any]) -> str | None:
    title = article.get("title", "")
    desc = (article.get("description") or "")[:200]
    market_ctx = build_market_context()
    prompt = (
        f"News: {title}\n{desc}\n\n"
        f"{market_ctx}\n\n"
        "Give a 1-line trading insight for this financial news. "
        "Mention direction (bullish/bearish) and which asset. "
        "Be specific (entry bias, key level). Max 20 words."
    )
    return _groq_chat(prompt, system_prompt=TRADING_SYSTEM_PROMPT)


def ai_answer_question(question: str) -> str | None:
    if not GROQ_API_KEY:
        return None
    market_ctx = build_market_context()
    prompt = (
        "You are an expert forex and stock market trading analyst. "
        "Answer the user's trading question concisely and accurately. "
        "Provide analysis, direction (bullish/bearish), key price levels if applicable, "
        "and risk management advice.\n\n"
        f"{market_ctx}\n\n"
        f"Question: {question}\n\n"
        "Keep it under 150 words. Be specific about entry zones, not just direction."
    )
    return _groq_chat(prompt, system_prompt=TRADING_SYSTEM_PROMPT)


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "<b>ForexSignalAI Trade Analyzer</b>\n\n"
        "Send me any trading or market question and I'll analyze it with AI.\n\n"
        "Examples:\n"
        "- Is EUR/USD bullish today?\n"
        "- Should I buy gold now?\n"
        "- Technical analysis of Nifty\n"
        "- What is the market outlook for this week?",
        parse_mode="HTML",
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Send any trading or market question. "
        "I will analyze it using AI and provide trading insights."
    )


async def handle_user_question(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        question = update.message.text.strip()
        if not question:
            return

        await update.message.chat.send_action(action="typing")

        answer = ai_answer_question(question)

        msg_parts: list[str] = []
        if answer:
            msg_parts.append(
                f"<b>Question:</b> {escape(question)}\n\n"
                f"<b>AI Analysis:</b>\n{answer}"
            )
        else:
            msg_parts.append(
                "<b>AI analysis unavailable.</b>\n\n"
                "GROQ_API_KEY may not be configured. Please check server settings."
            )
            await update.message.reply_text("\n".join(msg_parts), parse_mode="HTML")
            return

        asset = detect_asset_in_text(question)
        if asset and asset in TRADE_PAIRS:
            trade_setup = generate_asset_trade_setup(asset, question)
            if trade_setup:
                enhancement = ai_enhance_trade_suggestion(trade_setup, question)
                if enhancement:
                    trade_setup += f"\n\n<b>AI Improvement:</b> {enhancement}"
                msg_parts.append(f"\n\n{trade_setup}")

        await update.message.reply_text("\n".join(msg_parts), parse_mode="HTML")
    except Exception as e:
        print(f"[ERROR] handle_user_question: {e}")
        try:
            await update.message.reply_text(
                "Sorry, an error occurred while processing your question. Please check the bot logs."
            )
        except Exception:
            pass


def ensure_summary(article: dict[str, Any]) -> str:
    summary = article.get("description") or article.get("content") or ""
    summary = summary.strip()
    if summary:
        return escape(summary[:400])
    title = article.get("title") or ""
    if title:
        return escape(title[:400])
    return "No summary available."


def ai_translate(text: str, target_lang: str = "Bengali") -> str | None:
    if not GROQ_API_KEY or not text or not text.strip():
        return None
    prompt = (
        f"Translate this English text to {target_lang}. "
        "Keep ALL financial terms, numbers, percentages, currency codes (USD, EUR, XAU, etc.), "
        "and trading jargon (BUY, SELL, TP, SL, bullish, bearish, resistance, support, breakout, "
        "rally, decline) in English. Only translate surrounding explanatory words.\n\n"
        f"{text[:400]}"
    )
    return _groq_chat(prompt)


def translate_to_bengali(text: str) -> str | None:
    if not text or not text.strip():
        return None
    text = text[:500]

    ai_result = ai_translate(text)
    if ai_result:
        return ai_result

    try:
        from urllib.parse import quote
        url = f"https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=bn&dt=t&q={quote(text)}"
        with urlopen(url, timeout=10) as r:
            data = json.load(r)
        translated = data[0][0][0] if data and data[0] and data[0][0] else None
        if translated and translated.strip():
            return escape(translated)
    except Exception:
        pass

    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source="en", target="bn")
        translated = translator.translate(text)
        if translated and translated.strip():
            return escape(translated)
    except Exception:
        pass

    return None


def format_stock_price_info(asset: str) -> str | None:
    try:
        import indian_market as im
        yf_map = {
            "RELIANCE": "RELIANCE.NS", "TCS": "TCS.NS", "HDFCBANK": "HDFCBANK.NS",
            "INFY": "INFY.NS", "ICICIBANK": "ICICIBANK.NS", "SBIN": "SBIN.NS",
            "BHARTI": "BHARTIARTL.NS", "WIPRO": "WIPRO.NS", "ITC": "ITC.NS",
            "LT": "LT.NS", "AXISBANK": "AXISBANK.NS", "KOTAKBANK": "KOTAKBANK.NS",
            "MARUTI": "MARUTI.NS", "TATAMOTORS": "TATAMOTORS.NS",
            "ASIANPAINT": "ASIANPAINT.NS", "HCLTECH": "HCLTECH.NS",
            "SUNPHARMA": "SUNPHARMA.NS", "BAJFINANCE": "BAJFINANCE.NS",
            "TITAN": "TITAN.NS", "NTPC": "NTPC.NS", "ONGC": "ONGC.NS",
            "POWERGRID": "POWERGRID.NS", "ULTRACEMCO": "ULTRACEMCO.NS",
            "NIFTY": "^NSEI", "SENSEX": "^BSESN",
        }
        yf_symbol = yf_map.get(asset)
        if not yf_symbol:
            return None
        data = im.fetch_ticker_price(yf_symbol)
        if not data:
            return None
        sign = "+" if data["change"] >= 0 else ""
        return (f"<b>Live Price:</b> {data['price']} ({sign}{data['change']} | "
                f"{sign}{data['pct']}%)")
    except Exception:
        return None


def generate_trade_suggestion(article: dict[str, Any], asset: str) -> str:
    bias = infer_bias_signal(article)
    if bias:
        trade = format_trade_lines(bias)
        if trade:
            return trade

    text = normalize_text(article)
    score = sum(1 for word in POSITIVE_KEYWORDS if word in text)
    score -= sum(1 for word in NEGATIVE_KEYWORDS if word in text)

    if score > 0:
        direction = "BUY"
    elif score < 0:
        direction = "SELL"
    else:
        direction = "WATCH"

    return f"{direction} {asset} - Monitor for confirmation with proper risk management"


def load_newsdata_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") not in {None, "success"}:
        raise RuntimeError(f"Newsdata API returned status {payload.get('status')!r}")
    results = payload.get("results") or []
    if not isinstance(results, list):
        raise RuntimeError("Newsdata API payload did not contain a list of results")
    return [normalize_newsdata_article(item) for item in results if isinstance(item, dict)]


def load_newsapi_articles(payload: dict[str, Any]) -> list[dict[str, Any]]:
    if payload.get("status") != "ok":
        raise RuntimeError(
            f"News API returned status {payload.get('status')!r}: {payload.get('message', 'unknown error')}"
        )
    articles = payload.get("articles") or []
    if not isinstance(articles, list):
        raise RuntimeError("News API payload did not contain a list of articles")
    return [normalize_newsapi_article(item) for item in articles if isinstance(item, dict)]


def fetch_latest_articles(query: str = FOREX_QUERY) -> list[dict[str, Any]]:
    provider = get_active_provider()
    url = build_newsapi_url(query) if provider == "newsapi" else build_newsdata_url(query)
    with urlopen(url, timeout=30) as response:
        payload = json.load(response)

    if provider == "newsapi":
        return load_newsapi_articles(payload)
    return load_newsdata_articles(payload)


def is_recent(article: dict[str, Any], max_age_hours: int = 48) -> bool:
    pub_date = article.get("pubDate") or ""
    if not pub_date:
        return False
    try:
        dt_str = pub_date.replace("Z", "+00:00")
        if "+" not in dt_str and dt_str.count("-") == 2:
            dt_str += "+00:00"
        pub = datetime.fromisoformat(dt_str)
        delta = datetime.now(timezone.utc) - pub
        return delta.total_seconds() < max_age_hours * 3600
    except Exception:
        return True


def format_market_snapshot_block() -> str | None:
    try:
        import indian_market as im
        indian = im.format_market_snapshot()
        global_data = im.format_global_snapshot()
        parts = []
        if global_data:
            parts.append(global_data)
        if indian:
            parts.append(indian)
        return "\n\n".join(parts) if parts else None
    except Exception:
        return None


def _calc_rr(trade_text: str) -> str | None:
    for line in trade_text.split("\n"):
        if "Targets:" not in line:
            continue
        try:
            entry_line = ""
            lines = trade_text.split("\n")
            idx = lines.index(line)
            if idx > 0:
                entry_line = lines[idx - 1]
            entry_str = entry_line.split("@")[-1].strip() if "@" in entry_line else ""
            entry_str = _re.sub(r'[$₹,€£¥]', '', entry_str)
            if not entry_str:
                continue
            entry = float(entry_str)
            targets_str = line.split("Targets:")[1].split("|")[0].strip()
            sl_str = line.split("SL:")[1].strip() if "SL:" in line else ""
            targets_str = _re.sub(r'[$₹,€£¥]', '', targets_str)
            sl_str = _re.sub(r'[$₹,€£¥]', '', sl_str)
            tp_parts = targets_str.split("/")
            tp_reward = max(float(tp_parts[0].strip()), float(tp_parts[1].strip()))
            sl = float(sl_str) if sl_str else 0
            reward = abs(tp_reward - entry)
            risk = abs(sl - entry)
            if risk > 0:
                return f"R:R 1:{reward / risk:.1f}"
        except (ValueError, IndexError, AttributeError):
            pass
    return None


import re as _re


def _strip_md(text: str) -> str:
    return _re.sub(r'[*_`>#()\[\]\\<>]', '', text)


def _confidence_pct(level: str) -> int:
    return {"High": 78, "Medium": 62, "Low": 45}.get(level, 50)


_USD_QUOTE_PAIRS = frozenset({
    "EUR/USD", "GBP/USD", "AUD/USD", "NZD/USD",
    "XAU/USD", "XAG/USD",
    "BTC/USD", "ETH/USD", "SOL/USD", "XRP/USD", "ADA/USD",
    "DOGE/USD", "DOT/USD", "AVAX/USD", "LINK/USD", "LTC/USD",
    "WTI", "BRENT", "US30", "US100",
})


def _price_str(val: float, pair: str) -> str:
    if pair in _USD_QUOTE_PAIRS:
        if abs(val) >= 1000:
            return f"${val:,.2f}"
        elif abs(val) >= 1:
            return f"${val:.2f}"
        return f"${val:.4f}"
    if abs(val) >= 1000:
        return f"{val:,.2f}"
    elif abs(val) >= 1:
        return f"{val:.2f}"
    return f"{val:.4f}"


def format_professional_signal(
    pair: str, direction: str, entry: float, tp1: float, tp2: float, sl: float,
    confidence_pct: int, reason: str, timeframe: str = "H1",
) -> str:
    dir_icon = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    pips_sl = _price_str(abs(round(sl - entry, 4)), pair)
    pips_tp1 = _price_str(abs(round(tp1 - entry, 4)), pair)
    pips_tp2 = _price_str(abs(round(tp2 - entry, 4)), pair)
    risk = abs(sl - entry)
    reward = abs(tp2 - entry)
    rr = f"{reward / risk:.1f}" if risk > 0 else "?"
    name = INSTRUMENT_NAMES.get(pair, pair)
    lines = [
        "📡 *TradeSignal Pro* | AI Signal",
        "",
        f"*{pair}* · {dir_icon} · {timeframe}",
        f"_{name}_",
        "",
        "━━━━━━━━━━━━━━",
        f"📌 Entry:      {_price_str(entry, pair)}",
        f"🛑 Stop Loss:  {_price_str(sl, pair)}  (-{pips_sl})",
        f"🎯 TP 1:       {_price_str(tp1, pair)} (+{pips_tp1})",
        f"🎯 TP 2:       {_price_str(tp2, pair)} (+{pips_tp2})",
        f"⚖️ Risk:Reward: 1 : {rr}",
        "━━━━━━━━━━━━━━",
        f"🤖 AI Confidence: {confidence_pct}%",
        "",
        f"📝 Reason: {_strip_md(reason[:300])}",
        "",
        "⚠️ Not financial advice. Trade at your own risk.",
    ]
    return "\n".join(lines)


def format_high_impact_alert(
    title: str, asset: str, direction: str, confidence_pct: int,
    analysis: str,
) -> str:
    """Template 2 — High-impact breaking news alert."""
    dir_icon = (
        "🟢 Bullish" if direction == "Bullish"
        else "🔴 Bearish" if direction == "Bearish"
        else "🟡 Neutral"
    )
    ist_now  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
    date_str = ist_now.strftime("%d %b %Y, %I:%M %p IST")
    return (
        f"📰 *BREAKING NEWS ALERT*\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"*{_strip_md(title[:80])}*\n"
        f"🌍 *Asset:* {asset}  ·  {date_str}\n\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💥 *Impact:* {dir_icon} for *{asset}*\n"
        f"🤖 *Confidence:* {confidence_pct}%\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"⚡ *Quick Analysis:*\n"
        f"{_strip_md(analysis[:350])}\n\n"
        f"🔖 #{asset}  #highimpact  #breakingnews  #news"
    )


def format_nse_signal(
    index: str, option_type: str, strike: str, direction: str,
    entry_low: float, entry_high: float, sl: float, tp1: float, tp2: float,
    spot: float, pcr: float | None, reason: str, bengali: str | None = None,
    expiry: str = "Weekly",
) -> str:
    dir_emoji = "🟢 BUY" if direction == "BUY" else "🔴 SELL"
    sl_pct = round(abs(sl - entry_low) / entry_low * 100)
    tp1_pct = round(abs(tp1 - entry_low) / entry_low * 100)
    tp2_pct = round(abs(tp2 - entry_low) / entry_low * 100)
    pcr_str = ""
    if pcr is not None:
        pcr_label = "bullish" if pcr > 1.2 else ("bearish" if pcr < 0.8 else "neutral")
        pcr_str = f"📊 PCR:             {pcr:.2f} ({pcr_label})"
    expiry_label = f"Weekly Expiry · {expiry}"
    lines = [
        f"🇮🇳 *{index}* · {option_type} {strike} | {dir_emoji}",
        f"_{expiry_label} · Options_",
        "",
        "━━━━━━━━━━━━━━",
        f"📌 Entry (premium): ₹{entry_low}–{entry_high}",
        f"🛑 Stop Loss:       ₹{sl}  (-{sl_pct}%)",
        f"🎯 Target 1:        ₹{tp1}  (+{tp1_pct}%)",
        f"🎯 Target 2:        ₹{tp2}  (+{tp2_pct}%)",
        f"📍 Spot ref:        {spot}",
    ]
    if pcr_str:
        lines.append(pcr_str)
    lines.append("━━━━━━━━━━━━━━")
    lines.append(f"📝 Reason: {_strip_md(reason[:300])}")
    if bengali:
        lines.append("")
        lines.append(f"🇧🇩 বাংলা: {bengali[:150]}")
    lines.append("")
    lines.append(f"🔖 #{index} #options #NSE #India #{expiry}")
    return "\n".join(lines)


def format_calendar_alert_md(events: list[dict]) -> str | None:
    if not events:
        return None
    lines = [
        "📰 *ECONOMIC CALENDAR*",
        "━━━━━━━━━━━━━━",
    ]
    now = datetime.now(timezone.utc)
    for ev in events:
        dt = ev.get("datetime")
        if not dt:
            continue
        mins_until = int((dt - now).total_seconds() / 60)
        if mins_until <= 0:
            time_str = "NOW"
        elif mins_until < 60:
            time_str = f"in {mins_until}m"
        else:
            hours = mins_until // 60
            mins_left = mins_until % 60
            time_str = f"in {hours}h {mins_left}m" if mins_left else f"in {hours}h"
        icon = "🔴" if ev["impact"] == "high" else "🟡"
        title = _strip_md(ev["title"])
        country = ev["country"]
        forecast = _strip_md(ev.get("forecast", "N/A"))
        previous = _strip_md(ev.get("previous", "N/A"))
        lines.append(f"{icon} *{country}* — {title}")
        lines.append(f"   ⏰ {time_str} | 📈 Fcst: {forecast} | 📉 Prev: {previous}")
    if len(lines) == 2:
        return None
    lines.append("")
    lines.append("🔖 #calendar #forex #economic")
    return "\n".join(lines)


def format_forex_message(article: dict[str, Any]) -> str:
    """Template 1 — Forex/Crypto trade signal or news alert."""
    title     = _strip_md(article.get("title") or "Market Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")
    link      = article.get("link") or ""

    asset  = identify_asset(article)
    bias   = infer_bias_signal(article)
    prices = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    pairs = TRADE_PAIRS.get(asset) if asset else None

    # ── Build trade signal card (Template 1) if we have a clear bias + pair ──
    if bias and pairs:
        parts = bias.split()
        if len(parts) == 2:
            direction_str, asset_sym = parts[0], parts[1]
            is_bullish = direction_str == "Bullish"
            pair, multiplier, pip_size = pairs[0]
            price = prices.get(pair)
            if price:
                is_buy = (is_bullish == (multiplier > 0))
                direction_label = "BUY" if is_buy else "SELL"
                dir_icon  = "🟢 BUY" if is_buy else "🔴 SELL"
                e  = round(price, 4)
                t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 4)
                t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 4)
                s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 4)
                reward = abs(t2 - e)
                risk   = abs(s - e)
                rr_str = f"{reward / risk:.1f}" if risk > 0 else "?"
                conf_pct = _confidence_pct(confidence)
                ai_reason = _strip_md(ai_analyze_news(article) or title[:200])
                inst_name = INSTRUMENT_NAMES.get(pair, pair)
                log_signal(pair, direction_label, e, t1, t2, s, "forex")
                lines = [
                    f"📡 *TradeSignal Pro*  |  AI Signal",
                    f"",
                    f"*{pair}*  ·  {dir_icon}  ·  H1",
                    f"_{inst_name}_",
                    f"",
                    f"━━━━━━━━━━━━━━━━━━",
                    f"📌 Entry:        {_price_str(e,  pair)}",
                    f"🛑 Stop Loss:    {_price_str(s,  pair)}  (-{_price_str(abs(s-e),  pair)})",
                    f"🎯 TP 1:         {_price_str(t1, pair)}  (+{_price_str(abs(t1-e), pair)})",
                    f"🎯 TP 2:         {_price_str(t2, pair)}  (+{_price_str(abs(t2-e), pair)})",
                    f"⚖️ Risk:Reward:  1 : {rr_str}",
                    f"━━━━━━━━━━━━━━━━━━",
                    f"🤖 AI Confidence: {conf_pct}%",
                    f"📝 {ai_reason[:250]}",
                    f"",
                    f"🔖 #{asset_sym}  #forex  #signal",
                    f"⚠️ _Not financial advice. Trade at your own risk._",
                ]
                if link:
                    lines.append(f"🔗 {link}")
                return "\n".join(lines)

    # ── Fallback: news alert (Template 2 style) ──────────────────────────────
    ai_analysis = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])
    dir_icon_fb = (
        "🟢 Bullish" if direction == "Bullish"
        else "🔴 Bearish" if direction == "Bearish"
        else "🟡 Neutral"
    )
    conf_pct_fb = _confidence_pct(confidence)
    ist_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
    lines = [
        f"📰 *FOREX/MARKET UPDATE*",
        f"━━━━━━━━━━━━━━━━━━",
        f"*{title[:80]}*",
        f"🌍 *Asset:* {asset}  ·  {ist_str}",
        f"",
        f"━━━━━━━━━━━━━━━━━━",
        f"💥 *Impact:* {dir_icon_fb} for *{asset}*",
        f"🤖 *Confidence:* {conf_pct_fb}%",
        f"━━━━━━━━━━━━━━━━━━",
        f"⚡ *Analysis:*",
        f"{ai_analysis[:350]}",
        f"",
        f"🔖 #{asset}  #forex  #news",
    ]
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    if link:
        lines.append(f"🔗 {link}")
    return "\n".join(lines)


def format_india_message(article: dict[str, Any]) -> str:
    """Template 3 — India/NSE market signal."""
    title     = _strip_md(article.get("title") or "India Market Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")

    asset  = identify_asset(article)
    bias   = infer_bias_signal(article)
    prices = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    dir_icon = (
        "🟢 BUY"  if direction == "Bullish"
        else "🔴 SELL" if direction == "Bearish"
        else "➖ WATCH"
    )
    conf_pct   = _confidence_pct(confidence)
    ai_insight = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])
    inst_name  = INSTRUMENT_NAMES.get(asset, asset)

    # Try to compute price levels
    pairs_list = TRADE_PAIRS.get(asset)
    entry_str = sl_str = tp1_str = tp2_str = "Monitor levels"
    sl_diff = tp1_diff = tp2_diff = ""
    if pairs_list:
        pair, multiplier, pip_size = pairs_list[0]
        price = prices.get(pair)
        if price:
            is_buy = (direction == "Bullish") == (multiplier > 0)
            e  = round(price, 2)
            t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 2)
            t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 2)
            s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 2)
            entry_str = _price_str(e, pair)
            sl_str    = _price_str(s, pair)
            tp1_str   = _price_str(t1, pair)
            tp2_str   = _price_str(t2, pair)
            sl_diff   = _price_str(abs(s - e), pair)
            tp1_diff  = _price_str(abs(t1 - e), pair)
            tp2_diff  = _price_str(abs(t2 - e), pair)
            log_signal(pair, direction, e, t1, t2, s, "india")

    live_price = format_stock_price_info(asset)
    lines = [
        f"🇮🇳 *NSE / BSE SIGNAL*",
        f"━━━━━━━━━━━━━━━━━━",
        f"*{asset}*  ·  {inst_name}  |  {dir_icon}",
        f"_{title[:80]}_",
        f"",
    ]
    if live_price:
        lines.append(live_price)
        lines.append("")
    lines.extend([
        f"━━━━━━━━━━━━━━━━━━",
        f"📌 Entry zone:   {entry_str}",
        f"🛑 Stop loss:    {sl_str}" + (f"  (-{sl_diff})" if sl_diff else ""),
        f"🎯 Target 1:     {tp1_str}" + (f"  (+{tp1_diff})" if tp1_diff else ""),
        f"🎯 Target 2:     {tp2_str}" + (f"  (+{tp2_diff})" if tp2_diff else ""),
        f"🤖 Confidence:   {conf_pct}%",
        f"━━━━━━━━━━━━━━━━━━",
        f"📊 *Analysis:* {ai_insight[:300]}",
        f"",
        f"🔖 #{asset}  #NSE  #BSE  #India  #news",
    ])
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    return "\n".join(lines)


def format_intraday_message(article: dict[str, Any]) -> str:
    """Template 3 variant — India intraday stock signal."""
    title     = _strip_md(article.get("title") or "Intraday Update")
    source    = _strip_md(article.get("source_name") or "")
    published = _strip_md(article.get("pubDate") or "")

    asset     = identify_asset(article)
    inst_name = INSTRUMENT_NAMES.get(asset, asset)
    bias      = infer_bias_signal(article)
    prices    = fetch_current_prices()
    text_body = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text_body)

    dir_icon = (
        "🟢 BUY"  if direction == "Bullish"
        else "🔴 SELL" if direction == "Bearish"
        else "➖ WATCH"
    )
    conf_pct   = _confidence_pct(confidence)
    ai_insight = _strip_md(ai_analyze_news(article) or ensure_summary(article)[:300])

    exchange_tag = "NSE" if asset in {
        "RELIANCE", "TCS", "HDFCBANK", "INFY", "ICICIBANK", "SBIN", "BHARTI",
        "WIPRO", "ITC", "LT", "AXISBANK", "KOTAKBANK", "MARUTI", "TATAMOTORS",
        "ASIANPAINT", "HCLTECH", "SUNPHARMA", "BAJFINANCE", "TITAN", "NTPC",
        "ONGC", "POWERGRID", "ULTRACEMCO", "NIFTY", "SENSEX",
    } else "BSE/NSE"

    pairs_list = TRADE_PAIRS.get(asset)
    entry_str = sl_str = tp1_str = tp2_str = "Monitor levels"
    sl_diff = tp1_diff = tp2_diff = ""
    if pairs_list:
        pair, multiplier, pip_size = pairs_list[0]
        price = prices.get(pair)
        if price:
            is_buy = (direction == "Bullish") == (multiplier > 0)
            e  = round(price, 2)
            t1 = round(price + 30 * pip_size if is_buy else price - 30 * pip_size, 2)
            t2 = round(price + 50 * pip_size if is_buy else price - 50 * pip_size, 2)
            s  = round(price - 20 * pip_size if is_buy else price + 20 * pip_size, 2)
            entry_str = _price_str(e, pair)
            sl_str    = _price_str(s, pair)
            tp1_str   = _price_str(t1, pair)
            tp2_str   = _price_str(t2, pair)
            sl_diff   = _price_str(abs(s - e), pair)
            tp1_diff  = _price_str(abs(t1 - e), pair)
            tp2_diff  = _price_str(abs(t2 - e), pair)
            log_signal(pair, direction, e, t1, t2, s, "intraday")

    live_price = format_stock_price_info(asset)
    lines = [
        f"📈 *INTRADAY SIGNAL*  ·  {exchange_tag}",
        f"━━━━━━━━━━━━━━━━━━",
        f"*{asset}*  ·  {inst_name}  |  {dir_icon}",
        f"_{title[:80]}_",
        f"",
    ]
    if live_price:
        lines.append(live_price)
        lines.append("")
    lines.extend([
        f"━━━━━━━━━━━━━━━━━━",
        f"📌 Entry zone:   {entry_str}",
        f"🛑 Stop loss:    {sl_str}" + (f"  (-{sl_diff})" if sl_diff else ""),
        f"🎯 Target 1:     {tp1_str}" + (f"  (+{tp1_diff})" if tp1_diff else ""),
        f"🎯 Target 2:     {tp2_str}" + (f"  (+{tp2_diff})" if tp2_diff else ""),
        f"🤖 Confidence:   {conf_pct}%",
        f"━━━━━━━━━━━━━━━━━━",
        f"📊 *Analysis:* {ai_insight[:300]}",
        f"",
        f"🔖 #{asset}  #intraday  #{exchange_tag}  #India",
    ])
    if source:
        lines.append(f"📰 _{source}  |  {published}_")
    return "\n".join(lines)


async def send_category_article(
    bot: Bot,
    chat_id: str,
    articles: list[dict[str, Any]],
    seen_keys: set[str],
    category_prefix: str,
    format_func: Any,
) -> int:
    for article in articles:
        key = article_key(article)
        if not key:
            continue
        full_key = f"{category_prefix}:{key}"
        if full_key in seen_keys:
            continue
        if not is_recent(article):
            continue

        text = format_func(article)
        if not text:
            continue

        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        seen_keys.add(full_key)
        save_seen_keys(seen_keys)
        return 1
    return 0


async def send_options_suggestion(bot: Bot, chat_id: str, seen_keys: set[str]) -> int:
    import indian_market as im

    nifty_suggestion = im.format_nifty_options_suggestion()
    today = datetime.now(timezone.utc).strftime("%Y%m%d")

    sent = 0

    if nifty_suggestion:
        key = f"option:nifty_{today}"
        if key not in seen_keys:
            await bot.send_message(
                chat_id=chat_id,
                text=nifty_suggestion,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1

    sensex_suggestion = im.format_sensex_options_suggestion()
    if sensex_suggestion:
        key = f"option:sensex_{today}"
        if key not in seen_keys:
            await bot.send_message(
                chat_id=chat_id,
                text=sensex_suggestion,
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1

    return sent


async def send_institutional_signals(bot: Bot, chat_id: str, seen_keys: set[str]) -> int:
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    key = f"institutional_signals:{today}"
    if key in seen_keys:
        return 0
    if not MASSIVE_API_KEY:
        return 0

    sent = 0
    try:
        block = massive_data.format_institutional_signal_block()
        if block:
            await bot.send_message(
                chat_id=chat_id, text=block,
                parse_mode="Markdown", disable_web_page_preview=True,
            )
            seen_keys.add(key)
            save_seen_keys(seen_keys)
            sent += 1
            print("[INSTITUTIONAL SIGNALS] Sent consensus ratings")

        commodity_block = massive_data.format_commodity_signal_block()
        if commodity_block:
            await bot.send_message(
                chat_id=chat_id, text=commodity_block,
                parse_mode="Markdown", disable_web_page_preview=True,
            )
            sent += 1
            print("[COMMODITY WATCH] Sent commodity prices")
    except Exception as e:
        print(f"[ERROR] Institutional signals: {e}")

    return sent


async def run_worker_cycle(bot: Bot, chat_id: str, seen_keys: set[str]) -> int:
    total_sent = 0

    forex_articles = fetch_latest_articles(FOREX_QUERY)
    total_sent += await send_category_article(
        bot, chat_id, forex_articles, seen_keys,
        "forex", format_forex_message,
    )

    india_articles = fetch_latest_articles(INDIA_MARKET_QUERY)
    total_sent += await send_category_article(
        bot, chat_id, india_articles, seen_keys,
        "india", format_india_message,
    )

    intraday_articles = fetch_latest_articles(INTRADAY_STOCK_QUERY)
    total_sent += await send_category_article(
        bot, chat_id, intraday_articles, seen_keys,
        "intraday", format_intraday_message,
    )

    total_sent += await send_options_suggestion(bot, chat_id, seen_keys)
    total_sent += await send_institutional_signals(bot, chat_id, seen_keys)

    return total_sent


def validate_config() -> list[str]:
    missing = []
    if BOT_TOKEN == "PLACEHOLDER_TOKEN_REVOKED":
        missing.append("BOT_TOKEN")
    if not TELEGRAM_CHAT_ID:
        missing.append("TELEGRAM_CHAT_ID")

    provider = get_active_provider()
    if provider == "newsapi":
        if not NEWS_API_KEY:
            missing.append("NEWS_API_KEY")
    elif not NEWSDATA_API_KEY:
        missing.append("NEWSDATA_API_KEY")

    return missing


async def news_broadcast_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _seen_keys
    try:
        sent_count = await run_worker_cycle(context.bot, TELEGRAM_CHAT_ID, _seen_keys)
        if sent_count:
            print(f"Worker cycle complete. Sent {sent_count} message(s).")
    except Exception as exc:
        print(f"[ERROR] Worker cycle failed: {exc}")


async def high_impact_check_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    global _seen_keys
    try:
        articles = fetch_latest_articles(FOREX_QUERY)
        for article in articles:
            if not is_recent(article, max_age_hours=6):
                continue
            if not is_high_impact(article):
                continue
            key = article_key(article)
            if not key:
                continue
            full_key = f"forex:{key}"
            if full_key in _seen_keys:
                continue

            asset = identify_asset(article)
            text = normalize_text(article)
            bias = infer_bias_signal(article)
            direction, confidence = "Neutral", "Low"
            if bias:
                direction, confidence = compute_confidence(text)
            ai_analysis = ai_analyze_news(article) or ""
            conf_pct = _confidence_pct(confidence)
            now_str = datetime.now(timezone(timedelta(hours=5, minutes=30))).strftime("%d %b %Y")
            text_msg = format_high_impact_alert(
                title=article.get("title", "Breaking News"),
                asset=asset,
                direction=direction,
                confidence_pct=conf_pct,
                analysis=ai_analysis or "Significant market-moving event detected.",
            )
            await context.bot.send_message(
                chat_id=TELEGRAM_CHAT_ID,
                text=text_msg,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )
            _seen_keys.add(full_key)
            save_seen_keys(_seen_keys)
            print(f"[HIGH IMPACT NEWS] Text alert sent: {(article.get('title') or '')[:80]}")
    except Exception as exc:
        print(f"[ERROR] High impact news check failed: {exc}")

    try:
        import forexfactory_calendar as ffcal
        events = ffcal.get_upcoming_high_impact(hours_ahead=2, target_currencies={"USD"})
        if events:
            now = datetime.now(timezone.utc)
            for ev in events:
                dt = ev.get("datetime")
                if not dt:
                    continue
                mins_until = int((dt - now).total_seconds() / 60)
                if mins_until > 90:
                    continue
                hour_key = dt.strftime("%Y%m%d_%H%M")
                cal_key = f"calendar:{hour_key}:{ev['country']}:{ev['title']}"
                if cal_key in _seen_keys:
                    continue
                alert_text = format_calendar_alert_md([ev])
                if not alert_text:
                    continue
                await context.bot.send_message(
                    chat_id=TELEGRAM_CHAT_ID,
                    text=alert_text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True,
                )
                _seen_keys.add(cal_key)
                save_seen_keys(_seen_keys)
                print(f"[CALENDAR] Alert: {ev['title']} ({ev['country']}) in {mins_until}m")
    except Exception as exc:
        print(f"[ERROR] Calendar check failed: {exc}")


def _signals_yesterday() -> list[dict]:
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
    return [s for s in load_signal_log() if s.get("date") == yesterday]


def _build_signal_results_block(signals: list[dict]) -> str:
    if not signals:
        return "_No signals sent yesterday._"
    lines: list[str] = []
    for s in signals:
        icon = " 🟢" if s["direction"] == "BUY" else " 🔴"
        lines.append(f"{icon} {s['pair']}: {s['direction']} @ {s['entry']} — OPEN")
        lines.append(f"   TP1: {s['tp1']} / TP2: {s['tp2']} | SL: {s['sl']}")
    return "\n".join(lines)


async def morning_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Template 4 — Morning market briefing (text, English only)."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %B %Y")

        # Yesterday's signals
        yesterday_signals = _signals_yesterday()
        sig_lines = []
        for s in yesterday_signals[:4]:
            icon = "🟢" if s["direction"] == "BUY" else "🔴"
            sig_lines.append(f"{icon} {s['pair']} {s['direction']} @ {s['entry']} — OPEN")
        sig_block = "\n".join(sig_lines) if sig_lines else "_No signals sent yesterday._"

        # Key events today
        ev_lines = []
        try:
            import forexfactory_calendar as ffcal
            all_events = ffcal.get_upcoming_high_impact(hours_ahead=24)
            for ev in all_events[:4]:
                imp     = ev.get("impact", "MED").upper()
                imp_ico = "🔴" if imp == "HIGH" else "🟡"
                ev_lines.append(f"{imp_ico} {ev.get('time','')}  —  {_strip_md(ev['title'])}  [{imp}]")
        except Exception:
            pass
        ev_block = "\n".join(ev_lines) if ev_lines else "_No major events today._"

        # Market overview (English only)
        prices      = fetch_current_prices()
        gold_price  = prices.get("XAU/USD", "N/A")
        dxy_price   = prices.get("DXY",     "N/A")
        nifty_price = prices.get("NIFTY",   "N/A")

        overview = _strip_md(
            _groq_chat(
                f"Generate a 3-4 sentence market overview for {date_str}. "
                f"DXY={dxy_price}, Gold={gold_price}, Nifty={nifty_price}. "
                "Cover DXY trend, Gold level, key overnight moves, caution zones. "
                "English only. Concise."
            ) or
            f"Gold at {gold_price}. DXY at {dxy_price}. Nifty at {nifty_price}. "
            "Trade cautiously around major economic events today."
        )

        text = (
            f"🌅 *Market Briefing — {date_str}*\n"
            f"_Forex  ·  Crypto  ·  NSE / BSE  ·  Events_\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📋 *Yesterday's Signals*\n"
            f"{sig_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📅 *Key Events Today* (IST)\n"
            f"{ev_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🔭 *Market Overview*\n"
            f"{overview}\n\n"
            f"🔖 #morning  #briefing  #forex  #NSE  #crypto"
        )
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        print(f"[MORNING BRIEFING] Sent for {date_str}")
    except Exception as exc:
        print(f"[ERROR] Morning briefing failed: {exc}")


async def premarket_india_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Template 6 — Pre-market India NSE/BSE news (30 min before 9:15 AM IST open)."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %b %Y")

        articles = fetch_latest_articles(INTRADAY_STOCK_QUERY) + \
                   fetch_latest_articles(INDIA_MARKET_QUERY)

        news_lines = []
        seen_titles: set[str] = set()
        for a in articles:
            t = _strip_md(a.get("title") or "")
            if not t or t in seen_titles:
                continue
            seen_titles.add(t)
            src = _strip_md(a.get("source_name") or "")
            news_lines.append(f"• {t[:90]}" + (f"\n  📰 _{src}_" if src else ""))
            if len(news_lines) >= 5:
                break

        news_block = "\n".join(news_lines) if news_lines else "_No pre-market news available._"

        prices      = fetch_current_prices()
        nifty_price = prices.get("NIFTY", "N/A")
        sensex_str  = "—"
        nifty_str   = f"{nifty_price}" if nifty_price != "N/A" else "N/A"

        outlook_prompt = (
            f"In 2 sentences, give a pre-market outlook for Indian NSE/BSE markets on {date_str}. "
            f"Nifty futures: {nifty_str}. English only. Concise."
        )
        outlook = _strip_md(_groq_chat(outlook_prompt) or
                            "Watch for gap-up or gap-down openings based on overnight global cues.")

        text = (
            f"🔔 *PRE-MARKET INDIA — {date_str}*\n"
            f"⏰ _NSE/BSE opens in ~30 minutes_\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📰 *Top Stories Before Open*\n"
            f"{news_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Pre-Market Levels*\n"
            f"  NIFTY futures:  {nifty_str}\n\n"
            f"💡 *Pre-Market Signal:* {outlook}\n\n"
            f"🔖 #premarket  #NSE  #BSE  #India"
        )
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        print(f"[PRE-MARKET INDIA] Sent for {date_str}")
    except Exception as exc:
        print(f"[ERROR] Pre-market India job failed: {exc}")


async def session_summary_job(
    context: ContextTypes.DEFAULT_TYPE,
    session_name: str,
    is_open: bool,
    tags: list[str],
) -> None:
    """Template 5 — Market session open / close summary."""
    try:
        now_ist  = datetime.now(timezone(timedelta(hours=5, minutes=30)))
        date_str = now_ist.strftime("%d %b %Y")
        time_str = now_ist.strftime("%I:%M %p")
        phase    = "OPENS 🟢" if is_open else "CLOSES 🔴"
        phase_icon = "🔔" if is_open else "🔕"

        prices = fetch_current_prices()
        label_map = [
            ("XAU/USD", "Gold  (XAU/USD)"),
            ("EUR/USD", "EUR/USD       "),
            ("GBP/USD", "GBP/USD       "),
            ("US100",   "NASDAQ 100    "),
            ("US30",    "Dow Jones     "),
            ("DXY",     "DXY Index     "),
            ("NIFTY",   "Nifty 50      "),
            ("WTI",     "Crude Oil WTI "),
        ]
        price_lines = []
        for key, label in label_map:
            val = prices.get(key)
            if val:
                price_lines.append(f"  {label}: {_price_str(val, key)}")
            if len(price_lines) >= 6:
                break
        prices_block = "\n".join(price_lines) if price_lines else "  _Prices unavailable_"

        outlook_prompt = (
            f"In 2-3 sentences give a trading outlook for the {session_name} "
            f"session {'opening' if is_open else 'closing'} on {date_str}. "
            "English only. Factual and concise."
        )
        outlook = _strip_md(_groq_chat(outlook_prompt) or
                            f"Monitor key levels during the {session_name} session.")

        tag_str = "  ".join(f"#{t}" for t in tags)
        text = (
            f"{phase_icon} *{session_name} — {phase}*\n"
            f"📅 {date_str}  ·  {time_str} IST\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"📊 *Market Snapshot*\n"
            f"{prices_block}\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💡 *Session Outlook:*\n"
            f"{outlook}\n\n"
            f"🔖 {tag_str}"
        )
        await context.bot.send_message(
            chat_id=TELEGRAM_CHAT_ID,
            text=text,
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
        print(f"[SESSION] {session_name} {'OPEN' if is_open else 'CLOSE'} summary sent.")
    except Exception as exc:
        print(f"[ERROR] Session summary job failed: {exc}")


# ── Session job wrappers (one per open/close event) ──────────────────────────
async def _nse_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "NSE / BSE India", True, ["NSE", "BSE", "India", "marketopen"])

async def _nse_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "NSE / BSE India", False, ["NSE", "BSE", "India", "marketclose"])

async def _london_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "London Forex", True, ["London", "forex", "GBP", "EUR", "session"])

async def _london_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "London Forex", False, ["London", "forex", "session"])

async def _ny_open_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "New York Forex", True, ["NewYork", "NYSE", "forex", "USD", "session"])

async def _ny_close_job(ctx: ContextTypes.DEFAULT_TYPE) -> None:
    await session_summary_job(ctx, "New York Forex", False, ["NewYork", "forex", "session"])


async def worker_loop() -> None:
    global _seen_keys, _signal_log
    _seen_keys  = load_seen_keys()
    _signal_log = load_signal_log()
    provider    = get_active_provider()

    print("ForexSignalAI worker started.")
    print(f"Polling {provider} every {FETCH_INTERVAL_SECONDS}s / high-impact every {HIGH_IMPACT_CHECK_INTERVAL}s")
    print(f"Loaded {len(_seen_keys)} previously sent article keys.")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  start_command))
    app.add_handler(CommandHandler("help",   help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_question))

    jq = app.job_queue

    # ── Regular news broadcast & high-impact monitoring ───────────────────────
    jq.run_repeating(news_broadcast_job,      interval=FETCH_INTERVAL_SECONDS,       first=10)
    jq.run_repeating(high_impact_check_job,   interval=HIGH_IMPACT_CHECK_INTERVAL,   first=5)

    # ── Morning briefing: 8:00 AM IST = 02:30 UTC ────────────────────────────
    jq.run_daily(morning_briefing_job,  time=time(hour=2,  minute=30), name="morning_briefing")

    # ── Pre-market India: 8:45 AM IST = 03:15 UTC ────────────────────────────
    jq.run_daily(premarket_india_job,   time=time(hour=3,  minute=15), name="premarket_india")

    # ── NSE/BSE Session: Open 9:15 AM IST (03:45 UTC), Close 3:30 PM (10:00 UTC)
    jq.run_daily(_nse_open_job,         time=time(hour=3,  minute=45), name="nse_open")
    jq.run_daily(_nse_close_job,        time=time(hour=10, minute=0),  name="nse_close")

    # ── London Forex: Open 1:30 PM IST (08:00 UTC), Close 9:30 PM (16:00 UTC)
    jq.run_daily(_london_open_job,      time=time(hour=8,  minute=0),  name="london_open")
    jq.run_daily(_london_close_job,     time=time(hour=16, minute=0),  name="london_close")

    # ── New York Forex: Open 6:30 PM IST (13:00 UTC), Close 12:30 AM (19:00 UTC)
    jq.run_daily(_ny_open_job,          time=time(hour=13, minute=0),  name="ny_open")
    jq.run_daily(_ny_close_job,         time=time(hour=19, minute=0),  name="ny_close")

    print("All jobs scheduled. Listening for user questions...")
    await app.run_polling(allowed_updates=Update.ALL_TYPES)


def main() -> int:
    print("Launching ForexSignalAI Bot Engine...")
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing required environment variables: {', '.join(missing)}")
        return 1

    asyncio.run(worker_loop())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

