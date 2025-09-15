import asyncio
import json
import logging
import random
import re
from pathlib import Path

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from ..common.config import DATA_DIR, SERVER_TZINFO
from ..common.utils import send_chunked_html_message
from .parser import PrincipleItem, parse_principles
from .storage import load_raw_principles

logger = logging.getLogger(__name__)

scheduler = AsyncIOScheduler(timezone=SERVER_TZINFO)


def job_id_for(user_id: int) -> str:
    return f"daily_{user_id}"


async def send_daily_principle_job(bot: Bot, user_id: int) -> None:
    """Cron-fired once per day per user at their HH:MM with random delay."""
    # Random delay 0..3600 seconds
    delay = random.randint(0, 3600)
    await asyncio.sleep(delay)

    raw = load_raw_principles(user_id)
    if not raw:
        try:
            await bot.send_message(
                user_id,
                "You haven't provided any principles yet. Use /update_principles to add them.",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify user %s about missing principles: %s", user_id, e
            )
        return

    items = parse_principles(raw)
    if not items:
        try:
            await bot.send_message(
                user_id,
                "I couldn't parse any leaf principles from your text. "
                "Please check your headings (#, ##, ###) and try /update_principles again.",
            )
        except Exception as e:
            logger.warning(
                "Failed to notify user %s about parsing issue: %s", user_id, e
            )
        return

    item = random.choice(items)
    try:
        await send_principle_message(bot, user_id, item)
    except Exception as e:
        logger.error("Failed sending principle to %s: %s", user_id, e)


async def send_principle_message(bot: Bot, chat_id: int, item: PrincipleItem) -> None:
    """Send a principle message with chunking support."""
    import html

    path_str = " -> ".join(item.path)
    header = f"<b>{html.escape(path_str)}</b>\n"
    body = html.escape(item.text)

    await send_chunked_html_message(bot, chat_id, body, header)


def schedule_daily_job_for_user(bot: Bot, user_id: int, hhmm: str) -> None:
    """(Re)schedule the user's daily job at HH:MM local server time."""
    # Validate HH:MM
    if not re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", hhmm):
        raise ValueError("Time must be HH:MM in 24h format")

    # Remove previous job if any
    jid = job_id_for(user_id)
    old = scheduler.get_job(jid)
    if old:
        old.remove()

    hour, minute = map(int, hhmm.split(":"))

    # Add cron job
    scheduler.add_job(
        send_daily_principle_job,
        trigger="cron",
        id=jid,
        args=[bot, user_id],
        hour=hour,
        minute=minute,
        misfire_grace_time=12 * 3600,  # if missed (downtime), allow 12h grace
        coalesce=True,  # collapse multiple missed runs into one
        max_instances=1,
        replace_existing=True,
    )
    logger.info("Scheduled daily job for user %s at %02d:%02d", user_id, hour, minute)


def load_existing_schedules(bot: Bot) -> int:
    """On startup, reload any existing time configs and schedule them."""
    count = 0
    for tf in DATA_DIR.glob("*_time.json"):
        try:
            data = json.loads(tf.read_text(encoding="utf-8"))
            hhmm = data.get("time")
            if hhmm:
                # derive user_id from filename
                uid_str = tf.name.split("_time.json")[0]
                user_id = int(uid_str)
                schedule_daily_job_for_user(bot, user_id, hhmm)
                count += 1
        except Exception as e:
            logger.warning("Skipping schedule file %s: %s", tf.name, e)
    return count


def start_scheduler():
    """Start the scheduler."""
    scheduler.start()


def shutdown_scheduler():
    """Shutdown the scheduler."""
    scheduler.shutdown(wait=False)
