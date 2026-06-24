import asyncio
import json
import os
from datetime import datetime, timezone
from html import escape
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

from telegram import Bot

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

BOT_TOKEN = "8710452375:AAG-pqR8amkjx772hAYiLC_0WymUcoruVqE"
TELEGRAM_CHAT_ID = "6207722743"
NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "").strip()
NEWS_API_KEY = "f1f7db9dc3354374a5f03aa7652fd49b"
NEWSDATA_API_URL = "https://newsdata.io/api/1/latest"
NEWSAPI_URL = "https://newsapi.org/v2/everything"
NEWS_PROVIDER = os.getenv("NEWS_PROVIDER", "auto").strip().lower()
FETCH_INTERVAL_SECONDS = int(os.getenv("FETCH_INTERVAL_SECONDS", "900"))

SENT_KEYS_FILE = "sent_articles.json"

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


def load_seen_keys() -> set[str]:
    try:
        with open(SENT_KEYS_FILE) as f:
            return set(json.load(f))
    except (FileNotFoundError, json.JSONDecodeError):
        return set()


def save_seen_keys(keys: set[str]) -> None:
    with open(SENT_KEYS_FILE, "w") as f:
        json.dump(sorted(keys), f)


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
        for pair, _, pip in TRADE_PAIRS.get("USD", []):
            base, quote = pair.split("/")
            b_rate = usd_base.get(base)
            q_rate = usd_base.get(quote)
            if b_rate and q_rate:
                rates[pair] = q_rate / b_rate
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


def format_trade_lines(bias: str) -> str | None:
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
        tp = round(price + (50 * pip_size) if is_buy else price - (50 * pip_size), 4)
        sl = round(price - (20 * pip_size) if is_buy else price + (20 * pip_size), 4)
        lines.append(f"{i}. {'BUY' if is_buy else 'SELL'} {pair} @ {entry} | TP: {tp} | SL: {sl}")
    return "\n".join(lines) if lines else None


def ai_analyze_news(article: dict[str, Any]) -> str | None:
    try:
        title = article.get("title", "")
        desc = (article.get("description") or "")[:200]
        prompt = (
            f"News: {title}\n{desc}\n\n"
            "Give a 1-line trading insight for this forex news. "
            "Mention direction (bullish/bearish) and which asset. Max 15 words."
        )
        headers = {
            "Authorization": f"Bearer {GROQ_API_KEY}",
            "Content-Type": "application/json",
        }
        import urllib.request as ureq
        payload = json.dumps({
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": prompt}],
        }).encode()
        req = ureq.Request(
            "https://api.groq.com/openai/v1/chat/completions",
            data=payload,
            headers=headers,
        )
        with urlopen(req, timeout=15) as r:
            data = json.load(r)
        text = data["choices"][0]["message"]["content"].strip()
        return escape(text)
    except Exception:
        return None


def ensure_summary(article: dict[str, Any]) -> str:
    summary = article.get("description") or article.get("content") or ""
    summary = summary.strip()
    if summary:
        return escape(summary[:400])
    title = article.get("title") or ""
    if title:
        return escape(title[:400])
    return "No summary available."


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


def format_forex_message(article: dict[str, Any]) -> str:
    title = escape(article.get("title") or "Untitled update")
    source = escape(article.get("source_name") or "Unknown source")
    published = escape(article.get("pubDate") or "Unknown time")
    link = article.get("link") or ""

    asset = identify_asset(article)
    summary = ensure_summary(article)
    trade = generate_trade_suggestion(article, asset)

    bias = infer_bias_signal(article)
    text = normalize_text(article)
    direction, confidence = "Neutral", "Low"
    if bias:
        direction, confidence = compute_confidence(text)
    trend_icon = "BULLISH" if direction == "Bullish" else "BEARISH" if direction == "Bearish" else "NEUTRAL"

    lines = [
        "<b>FOREX SIGNAL</b>",
        "----------------------------------------",
        f"<b>Headline:</b> {title}",
        f"<b>Asset:</b> {asset}",
        f"<b>Summary:</b> {summary}",
        "",
        f"<b>Trade Suggestion:</b>",
        trade,
        "",
        f"<b>Market Trend:</b> {trend_icon} ({confidence} confidence)",
        f"<b>Source:</b> {source} | {published}",
    ]

    if bias:
        asset_name = escape(bias.split()[1])
        lines[-2] = f"<b>Market Trend:</b> {trend_icon} on {asset_name} ({confidence} confidence)"

    ai_insight = ai_analyze_news(article)
    if ai_insight:
        lines.append(f"\n<b>AI Insight:</b> {ai_insight}")

    if link:
        lines.append(f"\n<a href='{escape(link)}'>Read More</a>")

    return "\n".join(lines)


def format_india_message(article: dict[str, Any]) -> str:
    title = escape(article.get("title") or "Untitled update")
    source = escape(article.get("source_name") or "Unknown source")
    published = escape(article.get("pubDate") or "Unknown time")
    link = article.get("link") or ""

    asset = identify_asset(article)
    summary = ensure_summary(article)
    trade = generate_trade_suggestion(article, asset)

    lines = [
        "<b>INDIA MARKET NEWS</b>",
        "----------------------------------------",
        f"<b>Headline:</b> {title}",
        f"<b>Asset:</b> {asset}",
        f"<b>Summary:</b> {summary}",
        "",
        f"<b>Trade Suggestion:</b>",
        trade,
        "",
        f"<b>Source:</b> {source} | {published}",
    ]

    if link:
        lines.append(f"\n<a href='{escape(link)}'>Read More</a>")

    return "\n".join(lines)


def format_intraday_message(article: dict[str, Any]) -> str:
    title = escape(article.get("title") or "Untitled update")
    source = escape(article.get("source_name") or "Unknown source")
    published = escape(article.get("pubDate") or "Unknown time")
    link = article.get("link") or ""

    asset = identify_asset(article)
    summary = ensure_summary(article)
    trade = generate_trade_suggestion(article, asset)

    lines = [
        "<b>INTRADAY STOCK ALERT</b>",
        "----------------------------------------",
        f"<b>Headline:</b> {title}",
        f"<b>Stock:</b> {asset}",
        f"<b>Summary:</b> {summary}",
        "",
        f"<b>Trade Suggestion:</b>",
        trade,
        "",
        f"<b>Source:</b> {source} | {published}",
    ]

    if link:
        lines.append(f"\n<a href='{escape(link)}'>Read More</a>")

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
            parse_mode="HTML",
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

    if total_sent:
        market_block = format_market_snapshot_block()
        if market_block:
            hour_key = f"market_summary:{datetime.now(timezone.utc).strftime('%Y%m%d_%H')}"
            if hour_key not in seen_keys:
                try:
                    await bot.send_message(
                        chat_id=chat_id,
                        text=f"<b>MARKET SUMMARY</b>\n----------------------------------------\n{market_block}",
                        parse_mode="HTML",
                        disable_web_page_preview=True,
                    )
                    seen_keys.add(hour_key)
                    save_seen_keys(seen_keys)
                except Exception:
                    pass

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


async def worker_loop() -> None:
    bot = Bot(BOT_TOKEN)
    seen_keys = load_seen_keys()
    provider = get_active_provider()

    print("ForexSignalAI worker started.")
    print(f"Polling {provider} every {FETCH_INTERVAL_SECONDS} seconds.")
    print(f"Loaded {len(seen_keys)} previously sent article keys.")

    while True:
        try:
            sent_count = await run_worker_cycle(bot, TELEGRAM_CHAT_ID, seen_keys)
            print(f"Worker cycle complete. Sent {sent_count} message(s).")
        except Exception as exc:
            print(f"[ERROR] Worker cycle failed: {exc}")

        await asyncio.sleep(FETCH_INTERVAL_SECONDS)


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
