from llm import AnalysisResult
from llm import Message as LLMMessage
from llm import query_llm


async def process_messages_with_llm(
    messages: list[tuple[str, str]], model_name: str
) -> str:
    """Process messages using LLM for empathy analysis."""
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
