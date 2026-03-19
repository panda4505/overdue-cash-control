"""
LLM client with automatic fallback.

OpenAI is the primary provider. DeepSeek is the fallback.
The rest of the codebase calls `llm_complete()` and never knows
which provider answered.
"""

import logging
from openai import AsyncOpenAI
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# OpenAI — primary
_openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None

# DeepSeek — fallback (OpenAI-compatible API)
_deepseek_client = (
    AsyncOpenAI(
        api_key=settings.DEEPSEEK_API_KEY,
        base_url="https://api.deepseek.com",
    )
    if settings.DEEPSEEK_API_KEY
    else None
)

# Default models
OPENAI_MODEL = "gpt-4o-mini"  # cheap + fast for column mapping
DEEPSEEK_MODEL = "deepseek-chat"


async def llm_complete(
    prompt: str,
    system: str = "You are a helpful assistant.",
    model: str | None = None,
    temperature: float = 0.0,
    max_tokens: int = 2000,
) -> str:
    """
    Send a completion request. Tries OpenAI first, falls back to DeepSeek.

    Returns the assistant's response text.
    Raises RuntimeError if both providers fail.
    """
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt},
    ]

    # Try OpenAI first
    if _openai_client:
        try:
            response = await _openai_client.chat.completions.create(
                model=model or OPENAI_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.warning(f"OpenAI failed, falling back to DeepSeek: {e}")

    # Fallback to DeepSeek
    if _deepseek_client:
        try:
            response = await _deepseek_client.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"DeepSeek also failed: {e}")

    raise RuntimeError("All LLM providers failed. Check API keys and connectivity.")
