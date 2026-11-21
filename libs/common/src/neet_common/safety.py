"""Detect retrieved text that looks like instructions aimed at the model (project rules).

Retrieved text is data, never instructions. Chunks matching these patterns are logged and dropped
before they reach a prompt. The patterns are deliberately conservative: MCC notices are formal prose
and never address an AI model.
"""

import re

_INSTRUCTION_PATTERNS = [
    r"\bignore\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier)\b",
    r"\bdisregard\s+(?:all\s+|any\s+|the\s+)?(?:previous|prior|above|earlier|instructions)\b",
    r"\b(?:system|developer)\s+prompt\b",
    r"\byou\s+are\s+(?:now\s+)?(?:an?\s+)?(?:ai|assistant|chatbot|language\s+model)\b",
    r"\b(?:new|hidden|secret)\s+instructions?\b",
    r"\breveal\s+(?:your|the)\s+(?:instructions|prompt|secrets?|password)\b",
    r"<\s*/?\s*(?:system|source|assistant|user)\b",
]
_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE)


def looks_like_instruction(text: str) -> bool:
    """True when `text` contains phrasing typical of a prompt injection."""
    return _INSTRUCTION_RE.search(text) is not None
