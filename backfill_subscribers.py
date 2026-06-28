"""Backfill subscribers.json from recent Telegram bot updates.

Run this once after deploying the subscriber tracking code.
It fetches recent messages sent to the bot and adds those chat IDs
to subscribers.json so existing users don't need to re-message.
"""

import json
import os
import urllib.request
import urllib.parse

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
SUBSCRIBERS_FILE = "subscribers.json"


def fetch_updates() -> list[dict]:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
    resp = urllib.request.urlopen(url, timeout=15)
    data = json.loads(resp.read().decode())
    return data.get("result", [])


def extract_chat_ids(updates: list[dict]) -> set[int]:
    chat_ids: set[int] = set()
    for upd in updates:
        msg = upd.get("message")
        if msg:
            cid = msg.get("chat", {}).get("id")
            if cid and isinstance(cid, int):
                chat_ids.add(cid)
    return chat_ids


def load_existing() -> list[int]:
    try:
        with open(SUBSCRIBERS_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save(subscribers: list[int]) -> None:
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(subscribers, f)


def main() -> None:
    if not BOT_TOKEN:
        print("[ERROR] BOT_TOKEN environment variable not set.")
        return

    print("Fetching recent bot updates...")
    updates = fetch_updates()
    print(f"Got {len(updates)} update(s).")

    chat_ids = extract_chat_ids(updates)
    print(f"Found {len(chat_ids)} unique chat ID(s): {chat_ids}")

    existing = load_existing()
    merged = list(set(existing) | chat_ids)
    merged.sort()

    new_ids = [cid for cid in merged if cid not in existing]
    if new_ids:
        print(f"Adding {len(new_ids)} new chat ID(s): {new_ids}")
    else:
        print("No new chat IDs to add.")

    save(merged)
    print(f"subscribers.json now has {len(merged)} subscriber(s).")


if __name__ == "__main__":
    main()
