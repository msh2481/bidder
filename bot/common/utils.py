import html

from aiogram import Bot, types
from aiogram.enums import ParseMode

from .config import MAX_TELEGRAM_LEN


async def send_long_message(
    message: types.Message, text: str, parse_mode: str | None = None
):
    """Send long messages by splitting them into chunks if needed."""
    if len(text) <= 500:
        await message.answer(text, parse_mode=parse_mode)
        return

    lines = text.split("\n")
    message_block = ""
    for line in lines:
        if len(message_block) + len(line) + 1 > 500:
            if message_block:
                await message.answer(message_block, parse_mode=parse_mode)
            message_block = line
        else:
            if message_block:
                message_block += "\n"
            message_block += line

    if message_block:
        await message.answer(message_block, parse_mode=parse_mode)


async def send_chunked_html_message(
    bot: Bot, chat_id: int, text: str, header: str = ""
):
    """Send HTML-formatted messages with chunking support."""
    full_text = header + text
    if len(full_text) <= MAX_TELEGRAM_LEN:
        await bot.send_message(
            chat_id, full_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        return

    # Chunk by size
    available = MAX_TELEGRAM_LEN - len(header)
    start = 0
    idx = 1
    total = (len(text) + available - 1) // available

    while start < len(text):
        chunk = text[start : start + available]
        suffix = f"\n\n<i>Part {idx}/{total}</i>"
        out = header + chunk + (suffix if idx < total else "")
        await bot.send_message(
            chat_id, out, parse_mode=ParseMode.HTML, disable_web_page_preview=True
        )
        start += available
        idx += 1
