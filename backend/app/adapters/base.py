from abc import ABC, abstractmethod
from typing import AsyncGenerator


class BaseLLMAdapter(ABC):
    """
    Abstract base class for all LLM adapters.
    Every provider (Claude, OpenAI, Gemini, custom) implements this interface.
    The rest of the app never calls a provider SDK directly — always through here.
    """

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: str,
        max_tokens: int = 1024,
    ) -> AsyncGenerator[str, None]:
        """
        Stream a chat response token by token.
        messages: list of {"role": "user"|"assistant", "content": "..."}
        system_prompt: fully assembled system prompt string
        Yields string chunks as they arrive.
        """
        pass

    @abstractmethod
    def count_tokens(self, text: str) -> int:
        """Estimate token count for a string."""
        pass

    @abstractmethod
    def is_refusal(self, response: str) -> bool:
        """Detect whether a completed response is a refusal."""
        pass

    @abstractmethod
    def get_info(self) -> dict:
        """Return model name, context window size, max output tokens."""
        pass
