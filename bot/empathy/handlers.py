from aiogram import F, Router, types
from aiogram.filters.command import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from loguru import logger

from ..common.utils import send_long_message
from .processor import process_messages_with_llm

router = Router()


class EmpathyStates(StatesGroup):
    collecting_messages = State()


# In-memory storage for message buffers and user model selection
message_buffer: dict[int, list[tuple[str, str]]] = {}
user_model_selection: dict[int, str] = {}


@router.message(Command("start_empathy"))
async def cmd_start_empathy(message: types.Message, state: FSMContext):
    """Start empathy analysis session."""
    user_id = message.from_user.id
    logger.info("Start empathy session command received from user {}", user_id)

    # Clear any existing buffer
    message_buffer[user_id] = []

    await state.set_state(EmpathyStates.collecting_messages)
    await message.answer(
        "🧠 **Empathy Analysis Session Started**\n\n"
        "Now you can:\n"
        "• Forward messages to me\n"
        "• Type messages directly\n"
        "• Use /process when ready to analyze\n"
        "• Use /cancel_empathy to cancel\n\n"
        "I'll collect all your messages until you run /process."
    )


@router.message(Command("process"))
async def cmd_process(message: types.Message, state: FSMContext):
    """Process collected messages for empathy analysis."""
    user_id = message.from_user.id
    logger.info("Process command received from user {}", user_id)

    current_state = await state.get_state()
    if current_state != EmpathyStates.collecting_messages:
        await message.answer(
            "You need to start an empathy session first with /start_empathy"
        )
        return

    buffered_messages = message_buffer.get(user_id, [])

    if not buffered_messages:
        logger.info("User {} has empty buffer", user_id)
        await message.answer(
            "Your buffer is empty. Forward or type some messages first."
        )
        return

    model_name = user_model_selection.get(user_id, "gpt-4.1")
    logger.info(
        "Processing {} messages for user {} with model {}",
        len(buffered_messages),
        user_id,
        model_name,
    )
    await message.answer(
        f"Processing {len(buffered_messages)} messages with {model_name}..."
    )

    analysis = await process_messages_with_llm(buffered_messages, model_name)
    await send_long_message(message, analysis, parse_mode="Markdown")
    logger.info("Analysis completed for user {}", user_id)

    # Clear buffer and state
    message_buffer[user_id] = []
    await state.clear()

    await message.answer(
        "✅ Analysis complete! Start a new session with /start_empathy if needed."
    )


@router.message(Command("cancel_empathy"))
async def cmd_cancel_empathy(message: types.Message, state: FSMContext):
    """Cancel empathy analysis session."""
    user_id = message.from_user.id
    logger.info("Cancel empathy command received from user {}", user_id)

    current_state = await state.get_state()
    if current_state != EmpathyStates.collecting_messages:
        await message.answer("No active empathy session to cancel.")
        return

    count = len(message_buffer.get(user_id, []))
    message_buffer[user_id] = []
    await state.clear()

    await message.answer(f"❌ Empathy session cancelled. Cleared {count} messages.")


@router.message(EmpathyStates.collecting_messages, F.text | F.caption)
async def collect_message(message: types.Message, state: FSMContext):
    """Collect messages during empathy analysis session."""
    user_id = message.from_user.id

    # Handle forwarded messages
    if message.forward_from or message.forward_from_chat:
        sender = None
        if message.forward_from:
            sender = message.forward_from.full_name
        elif message.forward_from_chat:
            sender = message.forward_from_chat.title

        text = message.text or message.caption
        if sender and text:
            if user_id not in message_buffer:
                message_buffer[user_id] = []
            message_buffer[user_id].append((sender, text))
            logger.info(
                "Collected forwarded message from {} for user {} (buffer size: {})",
                sender,
                user_id,
                len(message_buffer[user_id]),
            )
            await message.answer(
                f"✅ Collected forwarded message from {sender} ({len(message_buffer[user_id])} total)"
            )
            return

    # Handle regular messages
    text = message.text or message.caption
    if text:
        sender = message.from_user.full_name or f"User {user_id}"
        if user_id not in message_buffer:
            message_buffer[user_id] = []
        message_buffer[user_id].append((sender, text))
        logger.info(
            "Collected direct message from user {} (buffer size: {})",
            user_id,
            len(message_buffer[user_id]),
        )
        await message.answer(
            f"✅ Collected your message ({len(message_buffer[user_id])} total)"
        )


@router.message(Command("model"))
async def cmd_model(message: types.Message, command: CommandObject):
    """Set or view the LLM model for empathy analysis."""
    user_id = message.from_user.id
    logger.info("Model command received from user {}", user_id)
    if command.args:
        model_name = command.args
        user_model_selection[user_id] = model_name
        logger.info("User {} set model to {}", user_id, model_name)
        await message.answer(f"Model set to: {model_name}")
    else:
        current_model = user_model_selection.get(user_id, "gpt-4.1")
        logger.info("User {} requested current model: {}", user_id, current_model)
        await message.answer(
            f"Current model: {current_model}. To set a new model, use /model <modelname>."
        )
