
import asyncio
import logging
import os
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

from llm import Message as LLMMessage, query_llm

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)

# Get bot token from environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No bot token found. Set the BOT_TOKEN environment variable.")

# Initialize bot and dispatcher
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# In-memory buffer for messages, keyed by user ID
message_buffer = {}

async def process_messages_with_llm(messages: list[tuple[str, str]]) -> str:
    """
    Processes a list of messages with an LLM and returns a single summary string.
    """
    if not messages:
        return "No messages to process."

    history = [LLMMessage(text=f"{sender}: {text}") for sender, text in messages]
    
    # Prepend a system prompt to guide the LLM
    # The current llm.py implementation will send this as a user message.
    prompt = "Summarize the following messages, extracting the key points and any action items."
    history.insert(0, LLMMessage(text=prompt))

    # Using gpt-4o as a default, this can be changed.
    summary = await query_llm(history, "gpt-4o")
    return summary

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """
    This handler will be called when user sends `/start` command
    """
    await message.answer("Hello! Forward me some messages. When you're ready, use the /empathize command to get a summary.")

@dp.message(Command("empathize"))
async def cmd_empathize(message: types.Message):
    """
    This handler processes the buffered messages and sends the summary.
    """
    user_id = message.from_user.id
    buffered_messages = message_buffer.get(user_id, [])

    if not buffered_messages:
        await message.answer("Your buffer is empty. Forward some messages first.")
        return

    await message.answer(f"Processing {len(buffered_messages)} messages...")

    summary = await process_messages_with_llm(buffered_messages)
    await message.answer(summary)

    # Clear the buffer for the user
    message_buffer[user_id] = []


@dp.message()
async def handle_forwarded_messages(message: types.Message):
    """
    This handler will be called for any message that is not a command.
    We'll check if it's a forwarded message and add it to the buffer.
    """
    user_id = message.from_user.id
    sender = None
    text = message.text or message.caption # handle photos with captions

    if message.forward_from:
        sender = message.forward_from.full_name
    elif message.forward_from_chat:
        sender = message.forward_from_chat.title
    
    if sender and text:
        if user_id not in message_buffer:
            message_buffer[user_id] = []
        message_buffer[user_id].append((sender, text))
        # Silently accept the message
    else:
        # Ignore non-forwarded messages
        pass


async def main():
    """
    This function will start the bot.
    """
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
