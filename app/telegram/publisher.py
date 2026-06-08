import asyncio

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from app.core.config import settings


async def _publish(channel_id: int, text: str) -> int:
    # text is already safe HTML built by app.ai.formatting.format_post (body escaped,
    # source link as an <a> tag) — do NOT re-escape it. Link preview stays on so the
    # source link renders a rich card.
    bot = Bot(
        settings.TELEGRAM_BOT_TOKEN.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    async with bot:
        message = await bot.send_message(chat_id=channel_id, text=text)
    return message.message_id


def publish(channel_id: int, text: str) -> int:
    return asyncio.run(_publish(channel_id, text))
