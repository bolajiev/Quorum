from openai import OpenAI
from app.config import QWEN_API_KEY, QWEN_BASE_URL

_client: OpenAI | None = None


def get_client() -> OpenAI:
    global _client
    if _client is None:
        if not QWEN_API_KEY:
            raise RuntimeError("QWEN_API_KEY is not set. Add it to your .env file.")
        _client = OpenAI(api_key=QWEN_API_KEY, base_url=QWEN_BASE_URL)
    return _client


def chat(model: str, messages: list[dict], temperature: float = 0.7, **kwargs) -> str:
    """Single blocking chat call. Returns the assistant message content."""
    response = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    return response.choices[0].message.content


def chat_with_usage(
    model: str, messages: list[dict], temperature: float = 0.7, **kwargs
) -> tuple[str, dict]:
    """Like chat() but also returns a usage dict {prompt_tokens, completion_tokens, total_tokens}."""
    response = get_client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        **kwargs,
    )
    usage = {
        "prompt_tokens": response.usage.prompt_tokens,
        "completion_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens,
    }
    return response.choices[0].message.content, usage
