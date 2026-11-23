"""
ai_client.py
------------
Small shared helper so grammar.py / rewrite.py / suggestions.py can all use
the same optional Claude-powered upgrade path.

Everything in the `ai` package produces solid results with zero setup, using
rule-based checks. If the user sets an ANTHROPIC_API_KEY environment
variable and has the `anthropic` package installed, the same functions
transparently use Claude for higher-quality, more nuanced feedback.
No key configured -> silently falls back to rule-based only. No errors,
no required setup.
"""

import os

# Lightweight, cost-effective model — plenty for grammar/rewrite feedback.
# Swap to "claude-opus-4-8" for maximum quality, or another current model
# string (see https://docs.claude.com for the latest list).
DEFAULT_MODEL = "claude-sonnet-5"


def is_ai_available() -> bool:
    """True only if an API key is set AND the anthropic package is importable."""
    if not os.environ.get("ANTHROPIC_API_KEY"):
        return False
    try:
        import anthropic  # noqa: F401
        return True
    except ImportError:
        return False


def call_claude(prompt: str, system: str = None, max_tokens: int = 1024,
                 model: str = DEFAULT_MODEL):
    """
    Returns Claude's plain-text response, or None if AI isn't configured or
    the call fails for any reason. Callers should always handle a None
    return by falling back to their rule-based logic — AI here is an
    enhancement, never a hard dependency.
    """
    if not is_ai_available():
        return None
    try:
        import anthropic
        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        kwargs = {"system": system} if system else {}
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
            **kwargs,
        )
        return "".join(
            block.text for block in response.content if block.type == "text"
        ).strip()
    except Exception:
        return None


if __name__ == "__main__":
    if is_ai_available():
        print(call_claude("Say hello in five words or fewer."))
    else:
        print("AI not configured — set ANTHROPIC_API_KEY and `pip install anthropic` to enable.")
