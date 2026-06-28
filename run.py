"""Run a single fetch-and-send cycle (used by GitHub Actions)."""

import asyncio
import sys

from telegram import Bot

from main import (
    BOT_TOKEN,
    load_seen_keys,
    run_worker_cycle,
    save_seen_keys,
    validate_config,
)


async def run_once() -> int:
    missing = validate_config()
    if missing:
        print(f"[ERROR] Missing: {', '.join(missing)}")
        return 1

    bot = Bot(BOT_TOKEN)
    seen_keys = load_seen_keys()
    print(f"Loaded {len(seen_keys)} previously sent article keys.")

    sent = await run_worker_cycle(bot, seen_keys)
    save_seen_keys(seen_keys)
    print(f"Cycle complete. Sent {sent} message(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_once()))
