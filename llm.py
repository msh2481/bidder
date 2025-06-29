import asyncio
import base64
import io
from dataclasses import dataclass, field
from typing import List

from openai import AsyncOpenAI
from PIL import Image
from pydantic import BaseModel

client = AsyncOpenAI()


def pil_image_to_base64(image: Image.Image, format: str = "JPEG") -> str:
    # Resize image to have largest dimension <= 512px
    width, height = image.size
    max_size = 512
    if width > max_size or height > max_size:
        scale = max_size / max(width, height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    image.save(buffer, format=format)
    b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return f"data:image/{format.lower()};base64,{b64}"


@dataclass
class Message:
    text: str
    image_urls: list[str] = field(default_factory=list)
    image_b64s: list[str] = field(default_factory=list)


class FourEars(BaseModel):
    sender: str
    factual_information: str
    self_revelation: str
    relationship: str
    appeal: str
    bid_for_connection: str


class Continuation(BaseModel):
    sender: str
    example_continuations: List[str]


class AnalysisResult(BaseModel):
    analysis: List[FourEars]
    continuations: List[Continuation]


async def query_llm(
    history: list[Message],
    model: str,
    text_format=None,
) -> dict | str:
    input = []
    for msg in history:
        content: list[dict] = []
        if msg.text:
            content.append({"type": "input_text", "text": msg.text})
        for img_url in msg.image_urls:
            content.append({"type": "input_image", "image_url": img_url})
        for img_b64 in msg.image_b64s:
            content.append({"type": "input_image", "image_url": img_b64})
        input.append({"role": "user", "content": content})
    if text_format:
        res = await client.responses.parse(
            model=model,
            input=input,
            text_format=text_format,
        )
        assert res.output_parsed is not None, f"Output parsed is None for {input}"
        return res.output_parsed
    else:
        res = await client.responses.create(
            model=model,
            input=input,
        )
        assert res.output_text is not None, f"Output text is None for {input}"
        return res.output_text
