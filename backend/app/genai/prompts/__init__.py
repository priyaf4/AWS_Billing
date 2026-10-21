from functools import lru_cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent


@lru_cache
def load_prompt(name: str) -> str:
    """Load a prompt template, e.g. load_prompt("billing_assistant") reads billing_assistant.md."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()
