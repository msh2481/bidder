import html
import random
import re
from datetime import datetime

from aiogram import Bot, F, Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
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


@router.message(Command("add_principle"))
async def cmd_add_principle(message: Message, state: FSMContext):
    """Start adding a new principle."""
    user_id = message.from_user.id
    logger.info("Add principle command received from user {}", user_id)
    await state.set_state(AddStates.waiting_for_category)
    await message.answer(
        "🆕 **Adding a New Principle**\n\n"
        "Step 1/3: What **category** should this principle belong to?\n"
        "(e.g., 'Personal Growth', 'Work', 'Relationships', etc.)\n\n"
        "Type /cancel to abort."
    )


@router.message(AddStates.waiting_for_category, F.text)
async def receive_category(message: Message, state: FSMContext):
    """Receive principle category."""
    if message.text.startswith("/"):
        return  # Let command handlers take over

    user_id = message.from_user.id
    category = message.text.strip()
    logger.info("Received category '{}' from user {}", category, user_id)

    await state.update_data(category=category)
    await state.set_state(AddStates.waiting_for_title)
    await message.answer(
        f"📝 Category: **{category}**\n\n"
        "Step 2/3: What's the **title** of this principle?\n"
        "(e.g., '5-step process', 'Daily reflection', etc.)\n\n"
        "Type /cancel to abort."
    )


@router.message(AddStates.waiting_for_title, F.text)
async def receive_title(message: Message, state: FSMContext):
    """Receive principle title."""
    if message.text.startswith("/"):
        return  # Let command handlers take over

    user_id = message.from_user.id
    title = message.text.strip()
    logger.info("Received title '{}' from user {}", title, user_id)

    data = await state.get_data()
    await state.update_data(title=title)
    await state.set_state(AddStates.waiting_for_text)
    await message.answer(
        f"📝 Category: **{data['category']}**\n"
        f"📝 Title: **{title}**\n\n"
        "Step 3/3: What's the **content** of this principle?\n"
        "(This can be multiple paragraphs, bullet points, etc.)\n\n"
        "Type /cancel to abort."
    )


@router.message(AddStates.waiting_for_text, F.text)
async def receive_text(message: Message, state: FSMContext):
    """Receive principle text and save."""
    if message.text.startswith("/"):
        return  # Let command handlers take over

    user_id = message.from_user.id
    text = message.text.strip()
    logger.info(
        "Received principle text from user {} (length: {} chars)", user_id, len(text)
    )

    data = await state.get_data()
    principle_id = add_principle(user_id, data["category"], data["title"], text)
    logger.info("Added principle {} for user {}", principle_id, user_id)

    await state.clear()
    await message.answer(
        f"✅ **Principle Added!**\n\n"
        f"**ID:** {principle_id}\n"
        f"**Category:** {data['category']}\n"
        f"**Title:** {data['title']}\n\n"
        f"Use /principles to see all your principles or /add_principle to add another."
    )


@router.message(Command("remove_principle"))
async def cmd_remove_principle(message: Message, command: CommandObject):
    """Remove a principle by ID."""
    user_id = message.from_user.id
    logger.info("Remove principle command received from user {}", user_id)

    if not command.args:
        await message.answer(
            "❗️ Please specify the principle ID to remove.\n\n"
            "Usage: `/remove_principle <id>`\n"
            "Use /principles to see all IDs."
        )
        return

    try:
        principle_id = int(command.args)
    except ValueError:
        await message.answer("❗️ Principle ID must be a number.")
        return

    # Get principle details before removing
    principle = get_principle(user_id, principle_id)
    if not principle:
        await message.answer(f"❗️ No principle found with ID {principle_id}.")
        return

    # Remove the principle
    if remove_principle(user_id, principle_id):
        logger.info("Removed principle {} for user {}", principle_id, user_id)
        await message.answer(
            f"🗑️ **Principle Removed**\n\n"
            f"**ID:** {principle_id}\n"
            f"**Title:** {principle.title}\n"
            f"**Category:** {principle.category}\n\n"
            f"Use /principles to see your remaining principles."
        )
    else:
        await message.answer(f"❗️ Failed to remove principle {principle_id}.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Cancel current operation."""
    user_id = message.from_user.id
    current_state = await state.get_state()

    if current_state in [
        AddStates.waiting_for_category,
        AddStates.waiting_for_title,
        AddStates.waiting_for_text,
    ]:
        await state.clear()
        logger.info("User {} cancelled add principle operation", user_id)
        await message.answer("❌ Cancelled adding principle.")
    elif current_state == TimeStates.waiting_for_time:
        await state.clear()
        logger.info("User {} cancelled time setting operation", user_id)
        await message.answer("❌ Cancelled setting reminder time.")
    else:
        await message.answer("Nothing to cancel.")


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
    principles = load_principles(user_id)

    if not principles:
        await message.answer(
            "You haven't added any principles yet. Use /add_principle to add your first one!"
        )
        return

    # Convert to the format expected by send_principle_message
    from .parser import PrincipleItem

    principle = random.choice(principles)
    item = PrincipleItem(
        path=[principle.category, principle.title], text=principle.text
    )

    logger.info("Sending test principle '{}' to user {}", principle.title, user_id)
    await send_principle_message(bot, user_id, item)
