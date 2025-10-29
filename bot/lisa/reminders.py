import asyncio
import json
import random
from datetime import datetime, time
from pathlib import Path

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from loguru import logger

from ..common.config import DATA_DIR, SERVER_TZINFO

# Lisa reminder categories with samples
LISA_CATEGORIES = {
    "поддержка": [
        "помочь с текущими задачами",
        "поддержать морально (\"всё будет хорошо\", \"я в тебя верю\", \"не расстраивайся\")",
    ],
    "изучение": [
        "\"что бы ты хотела поделать со мной?\"",
        "\"что бы ты хотела попробовать, или какой подарок получить?\"",
        "понять, чем она живёт и как мыслит (например, \"какие ценности и убеждения для тебя самые важные?\")",
    ],
    "подарки": [
        "цветы без повода",
        "заказать доставку с чем-нибудь вкусным (например, суши)",
        "подарить одежду или аксессуар, или подарочную карту в магазин одежды",
    ],
    "внимание": [
        "посмотреть вместе фильм",
        "почитать с ней книжку",
        "сыграть ей на скрипке",
        "запланировать какую-нибудь необычную активность (вечер оригами / стихов)",
    ],
    "слова": [
        "\"я рад, что ты со мной\"",
        "\"я скучаю по тебе\"",
        "\"ты мне нравишься\"",
    ],
}


def lisa_config_file(user_id: int) -> Path:
    return DATA_DIR / f"{user_id}_lisa.json"


def load_lisa_config(user_id: int) -> dict | None:
    """Load Lisa reminder configuration."""
    config_file = lisa_config_file(user_id)
    if not config_file.exists():
        return None
    
    try:
        return json.loads(config_file.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_lisa_config(user_id: int, enabled: bool) -> None:
    """Save Lisa reminder configuration."""
    config_file = lisa_config_file(user_id)
    config = {
        "enabled": enabled,
        "tzname": str(SERVER_TZINFO),
        "created_at": datetime.now().isoformat()
    }
    config_file.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8")


def generate_lisa_message() -> str:
    """Generate a Lisa reminder message with one sample from each category."""
    message_parts = ["Подумай о Лизе!"]
    
    for category, samples in LISA_CATEGORIES.items():
        sample = random.choice(samples)
        message_parts.append(f"- {sample}")
    
    return "\n".join(message_parts)


async def send_lisa_reminder_job(bot: Bot, user_id: int) -> None:
    """Send Lisa reminder at random time between 4-8pm."""
    # Random time between 16:00 and 20:00 (4pm-8pm)
    random_hour = random.randint(16, 19)  # 16, 17, 18, or 19
    random_minute = random.randint(0, 59)
    
    # Calculate delay until that time today
    now = datetime.now(SERVER_TZINFO)
    target_time = now.replace(hour=random_hour, minute=random_minute, second=0, microsecond=0)
    
    # If target time has passed today, schedule for tomorrow
    if target_time <= now:
        target_time = target_time.replace(day=target_time.day + 1)
    
    delay_seconds = (target_time - now).total_seconds()
    
    logger.info("Lisa reminder for user {} scheduled at {} (delay: {} seconds)", 
               user_id, target_time.strftime("%H:%M"), int(delay_seconds))
    
    await asyncio.sleep(delay_seconds)
    
    # Check if still enabled
    config = load_lisa_config(user_id)
    if not config or not config.get("enabled", False):
        logger.info("Lisa reminders disabled for user {}, skipping", user_id)
        return
    
    message = generate_lisa_message()
    
    try:
        await bot.send_message(user_id, message)
        logger.info("Successfully sent Lisa reminder to user {}", user_id)
    except Exception as e:
        logger.error("Failed to send Lisa reminder to user {}: {}", user_id, e)


def lisa_job_id(user_id: int) -> str:
    return f"lisa_reminder_{user_id}"


def schedule_lisa_reminder(scheduler: AsyncIOScheduler, bot: Bot, user_id: int) -> None:
    """Schedule daily Lisa reminder for a user."""
    job_id = lisa_job_id(user_id)
    
    # Remove existing job if any
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        existing_job.remove()
    
    # Schedule daily job at midnight (job will then wait for random 4-8pm time)
    scheduler.add_job(
        send_lisa_reminder_job,
        trigger="cron",
        id=job_id,
        args=[bot, user_id],
        hour=0,
        minute=0,
        misfire_grace_time=12 * 3600,
        coalesce=True,
        max_instances=1,
        replace_existing=True,
    )
    
    logger.info("Scheduled daily Lisa reminder for user {}", user_id)


def unschedule_lisa_reminder(scheduler: AsyncIOScheduler, user_id: int) -> None:
    """Remove Lisa reminder schedule for a user."""
    job_id = lisa_job_id(user_id)
    existing_job = scheduler.get_job(job_id)
    if existing_job:
        existing_job.remove()
        logger.info("Removed Lisa reminder schedule for user {}", user_id)


def load_existing_lisa_schedules(scheduler: AsyncIOScheduler, bot: Bot) -> int:
    """Load existing Lisa reminder schedules on startup."""
    count = 0
    for config_file in DATA_DIR.glob("*_lisa.json"):
        try:
            config = json.loads(config_file.read_text(encoding="utf-8"))
            if config.get("enabled", False):
                # Extract user_id from filename
                user_id_str = config_file.name.split("_lisa.json")[0]
                user_id = int(user_id_str)
                schedule_lisa_reminder(scheduler, bot, user_id)
                count += 1
        except Exception as e:
            logger.warning("Skipping Lisa config file {}: {}", config_file.name, e)
    
    return count
