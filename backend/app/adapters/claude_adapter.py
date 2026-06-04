import anthropic
import tiktoken
from typing import AsyncGenerator
from app.adapters.base import BaseLLMAdapter
from app.core.config import settings

# Claude refusal phrases to detect
CLAUDE_REFUSAL_PHRASES = [
    "I cannot",
    "I'm not able to",
    "I won't",
    "I am not able to",
    "I am unable to",
    "As an AI",
    "as an AI",
    "I don't feel comfortable",
    "I can't assist",
    "I'm unable to",
    "I can't help with",
    "I'm not going to",
]


class ClaudeAdapter(BaseLLMAdapter):
    """
    Adapter for Anthropic's Claude API.
    Supports streaming, prompt caching on system prompt.
    """

    def __init__(self, model: str = "claude-sonnet-4-6"):
        self.model = model
        self.client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)
        # Fallback tokenizer — not exact for Claude but close enough for estimates
        try:
            self._tokenizer = tiktoken.get_encoding("cl100k_base")
        except Exception:
            self._tokenizer = None

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Stream response from Claude.
        Uses prompt caching on the system prompt to reduce costs on repeated calls.
        """
        async with self.client.messages.stream(
            model=self.model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": system_prompt,
                    # Cache the system prompt — saves ~90% on those tokens
                    # after the first call per session
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=messages,
        ) as stream:
            async for text in stream.text_stream:
                yield text

    def count_tokens(self, text: str) -> int:
        """Estimate token count. Uses cl100k_base as a proxy for Claude."""
        if self._tokenizer:
            return len(self._tokenizer.encode(text))
        # Rough fallback: ~4 characters per token
        return len(text) // 4

    def is_refusal(self, response: str) -> bool:
        """Detect Claude-specific refusal phrasing."""
        for phrase in CLAUDE_REFUSAL_PHRASES:
            if phrase in response:
                return True
        return False

    def get_info(self) -> dict:
        return {
            "provider": "anthropic",
            "model": self.model,
            "context_window": 200000,
            "max_output_tokens": 8096,
        }


# ─── Adapter registry ─────────────────────────────────────────────────────────
# Maps model string → adapter instance
# Add new adapters here as they are implemented

def get_adapter(model: str = "claude-sonnet-4-6") -> BaseLLMAdapter:
    """
    Returns the appropriate adapter for a given model string.
    Defaults to Claude Sonnet if model is unrecognised.
    """
    if model.startswith("claude-"):
        return ClaudeAdapter(model=model)
    # Future: add OpenAIAdapter, GeminiAdapter, CustomAdapter here
    # For now fall back to Claude
    return ClaudeAdapter(model="claude-sonnet-4-6")
