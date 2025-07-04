import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command, CommandObject
from aiogram.types import BotCommand
from dotenv import load_dotenv

from llm import AnalysisResult
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
user_model_selection = {}


async def send_long_message(message: types.Message, text: str, parse_mode: str | None = None):
    if len(text) <= 500:
        await message.answer(text, parse_mode=parse_mode)
        return

    lines = text.split('\n')
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


async def set_main_menu(bot: Bot):
    main_menu_commands = [
        BotCommand(command="/start", description="Start the bot"),
        BotCommand(command="/empathize", description="Analyze forwarded messages"),
        BotCommand(
            command="/model",
            description="Set the model for analysis (e.g., /model gpt-4o)",
        ),
    ]
    await bot.set_my_commands(main_menu_commands)


async def process_messages_with_llm(
    messages: list[tuple[str, str]], model_name: str
) -> str:
    if not messages:
        return "No messages to process."

    conversation = "\n".join([f"{sender}: {text}" for sender, text in messages])

    prompt = f"""Проанализируй следующий диалог, используя четырехстороннюю модель Шульца фон Туна ("модель 4 ушей"). Для каждого сообщения проанализируй четыре уровня:

1.  **Фактическая информация**: Каково буквальное, объективное содержание сообщения?
2.  **Самораскрытие**: Что сообщение говорит о личности, ценностях, эмоциях или текущем состоянии отправителя?
3.  **Отношения**: Что сообщение подразумевает об отношениях между отправителем и получателем? Как отправитель воспринимает получателя?
4.  **Призыв**: Что отправитель хочет, чтобы получатель сделал, подумал или почувствовал? Каков основной запрос или заявка на установление контакта?

Основываясь на этой модели, предоставь резюме того, о чем мог думать каждый человек, каковы были его заявки на установление контакта и каковы могли быть его основные запросы ("bids for connection").

В конце для каждой стороны диалога предложи несколько примеров ответов на русском языке (продолжающих текущий диалог), для обоих сторон.

Вот диалог:
{conversation}
"""

    history = [LLMMessage(text=prompt)]
    analysis_result = await query_llm(history, model_name, text_format=AnalysisResult)

    if isinstance(analysis_result, str):
        return analysis_result

    response_parts = []
    for analysis in analysis_result.analysis:
        response_parts.append(f"**Отправитель: {analysis.sender}**")
        response_parts.append(
            f"*Фактическая информация*: {analysis.factual_information}"
        )
        response_parts.append(f"*Самораскрытие*: {analysis.self_revelation}")
        response_parts.append(f"*Отношения*: {analysis.relationship}")
        response_parts.append(f"*Призыв*: {analysis.appeal}")
        response_parts.append(f"*Заявка на контакт*: {analysis.bid_for_connection}")
        response_parts.append("\n")

    response_parts.append("**Примеры продолжения диалога:**")
    for continuation in analysis_result.continuations:
        response_parts.append(f"*Для {continuation.sender}:*")
        for i, example in enumerate(continuation.example_continuations, 1):
            response_parts.append(f"{i}. {example}")
        response_parts.append("\n")

    return "\n".join(response_parts)


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "Hello! Forward me some messages. When you're ready, use the /empathize command to get a summary."
    )


@dp.message(Command("model"))
async def cmd_model(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    if command.args:
        model_name = command.args
        user_model_selection[user_id] = model_name
        await message.answer(f"Model set to: {model_name}")
    else:
        current_model = user_model_selection.get(user_id, "gpt-4.1")
        await message.answer(
            f"Current model: {current_model}. To set a new model, use /model <modelname>."
        )


@dp.message(Command("empathize"))
async def cmd_empathize(message: types.Message):
    user_id = message.from_user.id
    buffered_messages = message_buffer.get(user_id, [])

    if not buffered_messages:
        await message.answer("Your buffer is empty. Forward some messages first.")
        return

    model_name = user_model_selection.get(user_id, "gpt-4.1")
    await message.answer(
        f"Processing {len(buffered_messages)} messages with {model_name}..."
    )

    analysis = await process_messages_with_llm(buffered_messages, model_name)
    await send_long_message(message, analysis, parse_mode="Markdown")

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
    await set_main_menu(bot)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())