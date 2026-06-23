"""Run a single fetch-and-send cycle (used by GitHub Actions)."""

import asyncio
import os
import sys

from telegram import Bot

from main import (
    BOT_TOKEN,
    TELEGRAM_CHAT_ID,
    fetch_latest_articles,
    MAX_ARTICLES_PER_CYCLE,
    send_articles,
    validate_config,
)


async def run_once() -> int:
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing: {', '.join(missing)}")
        return 1

    bot = Bot(BOT_TOKEN)
    seen: set[str] = set()
    articles = fetch_latest_articles()
    sent = await send_articles(bot, TELEGRAM_CHAT_ID, articles, seen)
    print(f"Cycle complete. Sent {sent} article(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
