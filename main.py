import asyncio

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from loguru import logger

from bot.common.config import BOT_TOKEN

if not BOT_TOKEN:
    raise ValueError("No bot token found. Set the BOT_TOKEN environment variable.")
from bot.empathy.handlers import router as empathy_router
from bot.lisa.handlers import router as lisa_router
from bot.principles.handlers import router as principles_router
from bot.principles.scheduler import (
    load_existing_schedules,
    shutdown_scheduler,
    start_scheduler,
)
from bot.lisa.reminders import load_existing_lisa_schedules


async def set_main_menu(bot: Bot):
    """Set the main menu commands."""
    logger.info("Setting up main menu commands")
    main_menu_commands = [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/help", description="Show help"),
        # Empathy analysis commands
        BotCommand(
            command="/start_empathy", description="Start empathy analysis session"
        ),
        BotCommand(command="/process", description="Process collected messages"),
        BotCommand(command="/cancel_empathy", description="Cancel empathy session"),
        BotCommand(command="/model", description="Set LLM model (e.g., /model gpt-4o)"),
        # Principles commands
        BotCommand(command="/principles", description="List all your principles"),
        BotCommand(command="/add_principle", description="Add a new principle"),
        BotCommand(command="/remove_principle", description="Remove a principle by ID"),
        BotCommand(command="/reminder", description="Set daily reminder time"),
        BotCommand(command="/test_principle", description="Send random principle now"),
        # Lisa reminders
        BotCommand(command="/lisa_on", description="Enable Lisa reminders"),
        BotCommand(command="/lisa_off", description="Disable Lisa reminders"),
        BotCommand(command="/lisa_test", description="Test Lisa reminder"),
    ]
    await bot.set_my_commands(main_menu_commands)
    logger.info("Main menu commands set successfully")


@empathy_router.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start command handler."""
    logger.info("Start command received from user {}", message.from_user.id)
    await message.answer(
        "Hello! I'm a multi-purpose bot with two main features:\n\n"
        "🧠 **Empathy Analysis**\n"
        "• Use /start_empathy to begin a session\n"
        "• Forward or type messages during the session\n"
        "• Use /process to analyze with the 4-ears model\n"
        "• Use /model to set your preferred LLM model\n\n"
        "📚 **Daily Principles**\n"
        "• Use /add_principle to add principles one by one\n"
        "• Use /principles to see all your principles\n"
        "• Use /reminder to get daily reminders at your preferred time\n"
        "• Use /test_principle to get a random principle now\n\n"
        "💕 **Lisa Reminders**\n"
        "• Use /lisa_on to enable daily Lisa reminders (4-8pm)\n"
        "• Use /lisa_test to see a sample reminder\n\n"
        "Type /help for more details about commands."
    )


@empathy_router.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command handler."""
    logger.info("Help command received from user {}", message.from_user.id)
    await message.answer(
        "**Available Commands:**\n\n"
        "**General:**\n"
        "• /start - Welcome message\n"
        "• /help - Show this help\n\n"
        "**Empathy Analysis (4-ears model):**\n"
        "• /start_empathy - Start empathy analysis session\n"
        "• /process - Process collected messages\n"
        "• /cancel_empathy - Cancel active session\n"
        "• /model [name] - Set/view LLM model for analysis\n\n"
        "**Daily Principles:**\n"
        "• /principles - List all your principles\n"
        "• /add_principle - Add a new principle (guided process)\n"
        "• /remove_principle <id> - Remove a principle by ID\n"
        "• /reminder [HH:MM] - Set/view daily reminder time\n"
        "• /test_principle - Send a random principle immediately\n\n"
        "**Lisa Reminders:**\n"
        "• /lisa_on - Enable daily Lisa reminders (4-8pm)\n"
        "• /lisa_off - Disable Lisa reminders\n"
        "• /lisa_test - Test Lisa reminder message\n\n"
        "**Usage:**\n"
        "1. Use /start_empathy → forward/type messages → /process to analyze\n"
        "2. Use /add_principle to build your principles collection\n"
        "3. Configure reminder time for daily principle delivery\n"
        "4. Use /lisa_on for daily Lisa reminders with relationship suggestions"
    )


async def main():
    """Main bot function."""
    logger.info("Starting merged bot...")
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())

    # Include routers
    logger.info("Including routers...")
    dp.include_router(empathy_router)
    dp.include_router(principles_router)
    dp.include_router(lisa_router)

    # Set main menu
    await set_main_menu(bot)

    # Start scheduler and restore existing schedules
    logger.info("Starting scheduler...")
    start_scheduler()
    restored_principles = load_existing_schedules(bot)
    from bot.principles.scheduler import scheduler
    restored_lisa = load_existing_lisa_schedules(scheduler, bot)
    logger.info("Restored {} principle schedules and {} Lisa schedules from disk", 
               restored_principles, restored_lisa)

    # Start polling
    logger.info("Starting bot polling...")
    try:
        await dp.start_polling(bot)
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error("Bot stopped due to error: {}", e)
    finally:
        logger.info("Shutting down scheduler...")
        shutdown_scheduler()
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    asyncio.run(main())
