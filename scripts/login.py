"""Mint a Telethon StringSession interactively.

Usage:
    uv run python -m scripts.login

Reads TELEGRAM_API_ID / TELEGRAM_API_HASH from the environment (or .env via
the running shell); prompts for the phone number + login code (and 2FA
password if enabled), then prints the StringSession to stdout. Copy it into
your .env as TELETHON_STRING_SESSION. The session is never written to disk.
"""

from __future__ import annotations

import os

from telethon.sessions import StringSession
from telethon.sync import TelegramClient


def main() -> None:
    api_id_raw = os.environ.get("TELEGRAM_API_ID") or input("api_id: ").strip()
    api_hash = os.environ.get("TELEGRAM_API_HASH") or input("api_hash: ").strip()
    api_id = int(api_id_raw)

    with TelegramClient(StringSession(), api_id, api_hash) as client:
        session_string = client.session.save()

    print("\n=== TELETHON_STRING_SESSION (paste into .env, keep secret) ===")
    print(session_string)


if __name__ == "__main__":
    main()
