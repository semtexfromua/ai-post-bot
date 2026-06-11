"""Mint a Telethon StringSession via QR login (no login code needed).

Telegram often never delivers login codes for freshly registered api_ids:
the API answers SentCodeTypeApp, but no message arrives in the app, and
force_sms has been ignored server-side for years (Telethon issue #4730).
QR login sidesteps codes entirely — scan the QR with the Telegram app the
same way you link a desktop client.

Usage:
    uv run --env-file .env --with qrcode python -m scripts.login_qr

Reads TELEGRAM_API_ID / TELEGRAM_API_HASH from the environment, renders a QR
in the terminal (Telegram -> Settings -> Devices -> Link Desktop Device),
asks for the 2FA password if enabled, then prints the StringSession to
stdout. Copy it into your .env as TELETHON_STRING_SESSION. The session is
never written to disk.
"""

from __future__ import annotations

import asyncio
import getpass
import os

import qrcode
from telethon import TelegramClient, errors
from telethon.sessions import StringSession


def _show_qr(url: str) -> None:
    qr = qrcode.QRCode()
    qr.add_data(url)
    qr.make()
    qr.print_ascii(invert=True)
    print("Telegram -> Settings -> Devices -> Link Desktop Device -> scan")


async def main() -> None:
    api_id = int(os.environ.get("TELEGRAM_API_ID") or input("api_id: ").strip())
    api_hash = os.environ.get("TELEGRAM_API_HASH") or input("api_hash: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.connect()

    qr_login = await client.qr_login()
    while True:
        _show_qr(qr_login.url)
        try:
            await qr_login.wait()
            break
        except TimeoutError:
            # QR tokens expire after ~30s; mint a fresh one and re-render.
            await qr_login.recreate()
        except errors.SessionPasswordNeededError:
            await client.sign_in(password=getpass.getpass("2FA password: "))
            break

    print("\n=== TELETHON_STRING_SESSION (paste into .env, keep secret) ===")
    print(client.session.save())
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
