from aiogram import Router, types
from aiogram.filters.command import Command, CommandObject

from ..common.utils import send_long_message
from .processor import process_messages_with_llm

router = Router()

# In-memory storage for message buffers and user model selection
message_buffer: dict[int, list[tuple[str, str]]] = {}
user_model_selection: dict[int, str] = {}


@router.message(Command("empathize"))
async def cmd_empathize(message: types.Message):
    """Analyze buffered forwarded messages using empathy model."""
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


@router.message(Command("model"))
async def cmd_model(message: types.Message, command: CommandObject):
    """Set or view the LLM model for empathy analysis."""
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


@router.message(Command("clear_buffer"))
async def cmd_clear_buffer(message: types.Message):
    """Clear the message buffer for empathy analysis."""
    user_id = message.from_user.id
    count = len(message_buffer.get(user_id, []))
    message_buffer[user_id] = []
    await message.answer(f"Cleared {count} messages from your buffer.")


def handle_forwarded_message(message: types.Message) -> bool:
    """Handle forwarded messages for empathy analysis. Returns True if message was handled."""
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
        return True

    return False
