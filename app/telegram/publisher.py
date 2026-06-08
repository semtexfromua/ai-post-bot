import asyncio
import html

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings


async def _publish(channel_id: int, text: str) -> int:
    bot = Bot(
        settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            link_preview_is_disabled=True,
        ),
    )
    async with bot:
        message = await bot.send_message(chat_id=channel_id, text=html.escape(text))
    return message.message_id


def publish(channel_id: int, text: str) -> int:
    return asyncio.run(_publish(channel_id, text))
