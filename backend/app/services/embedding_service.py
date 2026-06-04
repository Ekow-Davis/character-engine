from openai import OpenAI
from app.core.config import settings

# Single client instance
_client = OpenAI(api_key=settings.openai_api_key)

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536


def embed_text(text: str) -> list[float]:
    """
    Generate a vector embedding for a string.
    Uses OpenAI text-embedding-3-small — cheap and accurate enough for RAG.
    Returns a list of 1536 floats.
    """
    text = text.strip().replace("\n", " ")
    if not text:
        return [0.0] * EMBEDDING_DIMENSIONS

    response = _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    Batch embed multiple strings in a single API call.
    More efficient than calling embed_text() in a loop.
    """
    cleaned = [t.strip().replace("\n", " ") for t in texts]
    response = _client.embeddings.create(
        model=EMBEDDING_MODEL,
        input=cleaned,
    )
    return [item.embedding for item in response.data]
