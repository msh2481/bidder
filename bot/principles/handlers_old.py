import html
import random
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message
from loguru import logger

from ..common.config import SERVER_TZINFO
from .scheduler import schedule_daily_job_for_user, send_principle_message
from .storage import (
    add_principle,
    get_principle,
    load_principles,
    load_time_config,
    remove_principle,
    save_time_config,
)

router = Router()


class AddStates(StatesGroup):
    waiting_for_category = State()
    waiting_for_title = State()
    waiting_for_text = State()


class UpdateStates(StatesGroup):
    waiting_for_principles = State()


class TimeStates(StatesGroup):
    waiting_for_time = State()


@router.message(Command("principles"))
async def cmd_principles(message: Message):
    """Show current principles list."""
    user_id = message.from_user.id
    logger.info("Principles list command received from user {}", user_id)
    principles = load_principles(user_id)
    time_config = load_time_config(user_id)

    if not principles:
        await message.answer(
            "📚 You haven't added any principles yet.\n\n"
            "Use /add_principle to add your first principle!"
        )
        return

    # Group by category for display
    categories = {}
    for principle in principles:
        if principle.category not in categories:
            categories[principle.category] = []
        categories[principle.category].append(principle)

    response_parts = [f"📚 **Your Principles** ({len(principles)} total)\n"]

    for category, category_principles in categories.items():
        response_parts.append(f"**{category}:**")
        for principle in category_principles:
            # Truncate long text for list view
            text_preview = (
                principle.text[:100] + "..."
                if len(principle.text) > 100
                else principle.text
            )
            response_parts.append(f"  `{principle.id}`. **{principle.title}**")
            response_parts.append(f"     {text_preview}")
        response_parts.append("")

    # Add reminder status
    if time_config and "time" in time_config:
        reminder_time = time_config["time"]
        response_parts.append(
            f"⏰ Daily reminder set for {reminder_time} (server time)"
        )
    else:
        response_parts.append("⏰ No daily reminder set. Use /reminder to set one.")

    response_parts.append(
        "\n💡 Use /add_principle to add more or /remove_principle <id> to remove."
    )

    response_text = "\n".join(response_parts)

    # Send in chunks if too long
    from ..common.utils import send_long_message

    await send_long_message(message, response_text, parse_mode="Markdown")


@router.message(Command("update_principles"))
async def cmd_update_principles(message: Message, state: FSMContext):
    """Start the process of updating principles."""
    user_id = message.from_user.id
    logger.info("Update principles command received from user {}", user_id)
    await state.set_state(UpdateStates.waiting_for_principles)
    await message.answer(
        "Please send your principles in a Markdown-like outline, for example:\n\n"
        "# General principles\n\n"
        "## Self-improvement\n"
        "### 5-step process\n"
        "On every iteration:\n"
        "1. Have clear goals\n"
        "2. Encounter problems and don't tolerate them\n"
        "3. Diagnose the problem's root cause\n"
        "4. Design a way to get around the problem\n"
        "5. Execute the designs to push through to results\n\n"
        "### Another principle\n"
        "Text of that principle...\n\n"
        "I'll split it into leaf items using your headings (#, ##, ###, ...)."
    )


@router.message(UpdateStates.waiting_for_principles, F.text.len() > 0)
async def receive_principles(message: Message, state: FSMContext):
    """Receive and save principles text."""
    user_id = message.from_user.id
    raw = message.text.strip()
    logger.info(
        "Received principles text from user {} (length: {} chars)", user_id, len(raw)
    )
    save_raw_principles(user_id, raw)
    items = parse_principles(raw)
    logger.info("Parsed {} principle items for user {}", len(items), user_id)
    await state.clear()

    if not items:
        await message.answer(
            "Saved your text, but I couldn't find any leaf items.\n"
            "Make sure each principle has a heading line (like `### Principle name`) "
            "and text below it. You can /update_principles again anytime."
        )
        return

    # A short confirmation preview
    preview = "\n\n".join(
        f"<b>{html.escape(' -> '.join(it.path))}</b>\n{html.escape((it.text.strip().splitlines() or [''])[0])[:120]}"
        for it in items[:3]
    )
    more = "" if len(items) <= 3 else f"\n\n…and {len(items) - 3} more."
    await message.answer(
        f"✅ Saved {len(items)} principle{'s' if len(items)!=1 else ''} for you. "
        f"You can set the daily reminder time with /reminder.\n\n"
        f"Preview of the first item{'s' if len(items)!=1 else ''}:\n\n{preview}{more}",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


@router.message(Command("reminder"))
async def cmd_reminder(message: Message, state: FSMContext):
    """Set or view daily reminder time."""
    user_id = message.from_user.id
    logger.info("Reminder command received from user {}", user_id)
    now = datetime.now(SERVER_TZINFO)
    tzname = now.tzname() or "local time"
    existing = load_time_config(user_id)
    current = existing["time"] if existing and "time" in existing else "not set"
    await state.set_state(TimeStates.waiting_for_time)
    await message.answer(
        f"Server time now: <b>{now.strftime('%Y-%m-%d %H:%M')}</b> ({html.escape(tzname)}).\n"
        f"Your current reminder time: <b>{html.escape(str(current))}</b>.\n\n"
        "Please send a time in 24h <b>HH:MM</b> (server timezone).",
        parse_mode=ParseMode.HTML,
    )


@router.message(TimeStates.waiting_for_time)
async def receive_time(message: Message, state: FSMContext, bot: Bot):
    """Receive and set reminder time."""
    user_id = message.from_user.id
    text = (message.text or "").strip()
    logger.info("Received time '{}' from user {}", text, user_id)
    if not re.fullmatch(r"([01]?\d|2[0-3]):([0-5]\d)", text):
        logger.warning("Invalid time format '{}' from user {}", text, user_id)
        await message.answer(
            "❗️Please send time as HH:MM in 24h format (e.g., 07:30 or 19:05)."
        )
        return

    save_time_config(user_id, text)
    try:
        schedule_daily_job_for_user(bot, user_id, text)
        logger.info(
            "Successfully scheduled daily reminder for user {} at {}", user_id, text
        )
    except Exception as e:
        logger.error(
            "Failed to schedule reminder for user {} at {}: {}", user_id, text, e
        )
        await message.answer(
            "I couldn't schedule that time due to an internal error. Please try again."
        )
        await state.clear()
        return

    await state.clear()
    await message.answer(
        f"⏰ Daily reminder time set to <b>{html.escape(text)}</b> (server timezone). "
        "Each day I'll add a random delay up to 60 minutes.",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("test_principle"))
async def cmd_test_principle(message: Message, bot: Bot):
    """Send a random principle immediately."""
    user_id = message.from_user.id
    logger.info("Test principle command received from user {}", user_id)
    raw = load_raw_principles(user_id)

    if not raw:
        await message.answer(
            "You haven't provided any principles yet. Use /update_principles to add them."
        )
        return

    items = parse_principles(raw)
    if not items:
        await message.answer(
            "I couldn't parse any principles from your text. "
            "Please check your headings (#, ##, ###) and try /update_principles again."
        )
        return

    item = random.choice(items)
    logger.info(
        "Sending test principle '{}' to user {}", " -> ".join(item.path), user_id
    )
    await send_principle_message(bot, user_id, item)
