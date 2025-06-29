import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command
from dotenv import load_dotenv

from llm import Message as LLMMessage
from llm import query_llm

load_dotenv()

logging.basicConfig(level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("No bot token found. Set the BOT_TOKEN environment variable.")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

message_buffer = {}


async def process_messages_with_llm(messages: list[tuple[str, str]]) -> str:
    if not messages:
        return "No messages to process."

    conversation = "\n".join([f"{sender}: {text}" for sender, text in messages])

    prompt = f"""Analyze the following conversation using Schulz von Thun's four-sides model (the "4-ear model"). For each message, please analyze the four layers:

1.  **Factual Information**: What is the literal, objective content of the message?
2.  **Self-Revelation**: What does the message reveal about the sender's personality, values, emotions, or current state?
3.  **Relationship**: What does the message imply about the relationship between the sender and receiver? How does the sender view the receiver?
4.  **Appeal**: What does the sender want the receiver to do, think, or feel? What is the underlying request or bid for connection?

Based on this model, provide a summary of what each person might have been thinking, what their bids for connection were, and what their underlying requests might be.

Finally, for each side of the conversation, provide a few example responses in Russian.

Here is the conversation:
{conversation}
"""

    history = [LLMMessage(text=prompt)]
    analysis = await query_llm(history, "gpt-4.5")
    return analysis


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Hello! Forward me some messages. When you're ready, use the /empathize command to get a summary."
    )


@dp.message(Command("empathize"))
async def cmd_empathize(message: types.Message):
    user_id = message.from_user.id
    buffered_messages = message_buffer.get(user_id, [])

    if not buffered_messages:
        await message.answer("Your buffer is empty. Forward some messages first.")
        return

    await message.answer(f"Processing {len(buffered_messages)} messages...")

    analysis = await process_messages_with_llm(buffered_messages)
    await message.answer(analysis)

    message_buffer[user_id] = []


@dp.message()
async def handle_forwarded_messages(message: types.Message):
    user_id = message.from_user.id
    sender = None
    text = message.text or message.caption

    if message.forward_from:
        sender = message.forward_from.full_name
    elif message.forward_from_chat:
        sender = message.forward_from_chat.title

    if sender and text:
        if user_id not in message_buffer:
            message_buffer[user_id] = []
        message_buffer[user_id].append((sender, text))


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
