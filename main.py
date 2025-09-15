import asyncio
import logging

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from dotenv import load_dotenv

from bot.common.config import BOT_TOKEN

if not BOT_TOKEN:
    raise ValueError("No bot token found. Set the BOT_TOKEN environment variable.")
from bot.empathy.handlers import handle_forwarded_message
from bot.empathy.handlers import router as empathy_router
from bot.principles.handlers import router as principles_router
from bot.principles.scheduler import (
    load_existing_schedules,
    shutdown_scheduler,
    start_scheduler,
)

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger("merged-bot")


async def set_main_menu(bot: Bot):
    """Set the main menu commands."""
    main_menu_commands = [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/help", description="Show help"),
        # Empathy analysis commands
        BotCommand(command="/empathize", description="Analyze forwarded messages"),
        BotCommand(command="/model", description="Set LLM model (e.g., /model gpt-4o)"),
        BotCommand(command="/clear_buffer", description="Clear message buffer"),
        # Principles commands
        BotCommand(command="/principles", description="Show principles status"),
        BotCommand(command="/update_principles", description="Update your principles"),
        BotCommand(command="/reminder", description="Set daily reminder time"),
        BotCommand(command="/test_principle", description="Send random principle now"),
    ]
    await bot.set_my_commands(main_menu_commands)


@empathy_router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start command handler."""
    await message.answer(
        "Hello! I'm a multi-purpose bot with two main features:\n\n"
        "🧠 **Empathy Analysis**\n"
        "• Forward messages to me, then use /empathize to analyze them using the 4-ears model\n"
        "• Use /model to set your preferred LLM model\n"
        "• Use /clear_buffer to clear stored messages\n\n"
        "📚 **Daily Principles**\n"
        "• Use /update_principles to set your personal principles\n"
        "• Use /reminder to get daily reminders at your preferred time\n"
        "• Use /test_principle to get a random principle now\n\n"
        "Type /help for more details about commands."
    )


@empathy_router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command handler."""
    await message.answer(
        "**Available Commands:**\n\n"
        "**General:**\n"
        "• /start - Welcome message\n"
        "• /help - Show this help\n\n"
        "**Empathy Analysis (4-ears model):**\n"
        "• /empathize - Analyze buffered forwarded messages\n"
        "• /model [name] - Set/view LLM model for analysis\n"
        "• /clear_buffer - Clear message buffer\n\n"
        "**Daily Principles:**\n"
        "• /principles - Show current principles status\n"
        "• /update_principles - Update your principles (Markdown format)\n"
        "• /reminder [HH:MM] - Set/view daily reminder time\n"
        "• /test_principle - Send a random principle immediately\n\n"
        "**Usage:**\n"
        "1. Forward messages to analyze them with empathy model\n"
        "2. Set up principles in Markdown format for daily reminders\n"
        "3. Configure reminder time for daily principle delivery"
    )


@empathy_router.message()
async def handle_all_messages(message: types.Message):
    """Handle all other messages - check if they're forwarded messages for empathy analysis."""
    # Try to handle as forwarded message for empathy analysis
    handled = handle_forwarded_message(message)
    if not handled:
        # If not a forwarded message, let FSM handlers in principles module handle it
        pass


async def main():
    """Main bot function."""
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    dp.include_router(empathy_router)
    dp.include_router(principles_router)

    # Set main menu
    await set_main_menu(bot)

    # Start scheduler and restore existing schedules
    start_scheduler()
    restored = load_existing_schedules(bot)
    logger.info("Restored %d scheduled users from disk", restored)

    # Start polling
    try:
        await dp.start_polling(bot)
    finally:
        shutdown_scheduler()


if __name__ == "__main__":
    asyncio.run(main())
