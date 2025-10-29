from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message
from loguru import logger

from .reminders import (
    load_lisa_config,
    save_lisa_config,
    schedule_lisa_reminder,
    unschedule_lisa_reminder,
    generate_lisa_message,
)

router = Router()


@router.message(Command("lisa_on"))
async def cmd_lisa_on(message: Message, bot: Bot):
    """Enable Lisa reminders."""
    user_id = message.from_user.id
    logger.info("Lisa on command received from user {}", user_id)
    
    # Import scheduler from main module
    from ..principles.scheduler import scheduler
    
    save_lisa_config(user_id, enabled=True)
    schedule_lisa_reminder(scheduler, bot, user_id)
    
    await message.answer(
        "💕 **Lisa Reminders Enabled!**\n\n"
        "I'll send you daily reminders about Lisa between 4-8pm with random suggestions from all categories:\n"
        "• поддержка\n"
        "• изучение\n"
        "• подарки\n"
        "• внимание\n"
        "• слова\n\n"
        "Use /lisa_off to disable or /lisa_test to see a sample."
    )


@router.message(Command("lisa_off"))
async def cmd_lisa_off(message: Message):
    """Disable Lisa reminders."""
    user_id = message.from_user.id
    logger.info("Lisa off command received from user {}", user_id)
    
    # Import scheduler from main module
    from ..principles.scheduler import scheduler
    
    save_lisa_config(user_id, enabled=False)
    unschedule_lisa_reminder(scheduler, user_id)
    
    await message.answer(
        "💔 **Lisa Reminders Disabled**\n\n"
        "I won't send daily Lisa reminders anymore.\n"
        "Use /lisa_on to re-enable them anytime."
    )


@router.message(Command("lisa_test"))
async def cmd_lisa_test(message: Message):
    """Send a test Lisa reminder."""
    user_id = message.from_user.id
    logger.info("Lisa test command received from user {}", user_id)
    
    test_message = generate_lisa_message()
    await message.answer(
        f"🧪 **Test Lisa Reminder:**\n\n{test_message}\n\n"
        f"This is what you'll receive daily between 4-8pm if Lisa reminders are enabled.\n"
        f"Use /lisa_on to enable or /lisa_off to disable."
    )


@router.message(Command("lisa_status"))
async def cmd_lisa_status(message: Message):
    """Show Lisa reminder status."""
    user_id = message.from_user.id
    logger.info("Lisa status command received from user {}", user_id)
    
    config = load_lisa_config(user_id)
    
    if not config:
        await message.answer(
            "💕 **Lisa Reminders Status: Not Configured**\n\n"
            "Use /lisa_on to enable daily Lisa reminders."
        )
        return
    
    status = "Enabled ✅" if config.get("enabled", False) else "Disabled ❌"
    await message.answer(
        f"💕 **Lisa Reminders Status: {status}**\n\n"
        f"Daily reminders are sent between 4-8pm with suggestions from all categories.\n\n"
        f"Commands:\n"
        f"• /lisa_on - Enable reminders\n"
        f"• /lisa_off - Disable reminders\n"
        f"• /lisa_test - See a sample reminder"
    )
