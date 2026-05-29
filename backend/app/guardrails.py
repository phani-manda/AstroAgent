import re
import logging
from typing import Tuple

logger = logging.getLogger(__name__)

DISALLOWED_CATEGORIES = [
    "medical", "legal", "financial", "stock", "investment",
    "prescription", "diagnosis", "lawsuit", "attorney", "sue",
    "criminal", "illegal", "hack", "exploit", "malware",
    "drug", "suicide", "self-harm", "weapon", "violence",
]

PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(your|all|previous)\s+(instructions?|guardrails?)",
    r"pretend\s+you\s+(are|were)",
    r"you\s+are\s+now\s+(a|an)\s+",
    r"system\s*:\s*",
    r"<\|system\|>",
    r"forget\s+(everything|all)",
    r"new\s+instructions?\s*:",
    r"override\s+",
    r"bypass\s+",
    r"jailbreak",
]

SAFE_FALLBACK_MEDICAL = "I'm sorry, but I can't provide medical advice. Astrology is for spiritual exploration, not health decisions. Please consult a qualified healthcare professional."
SAFE_FALLBACK_LEGAL = "I'm sorry, I can't help with legal matters. I'm here to discuss astrology and spiritual topics."
SAFE_FALLBACK_FINANCIAL = "I'm sorry, I can't give financial or investment advice. Let's talk about what the stars have to say instead!"
SAFE_FALLBACK_INJECTION = "I'm sorry, I can't help with that. I'm an astrology assistant here to explore birth charts and transits."
SAFE_FALLBACK_GENERIC = "I'm sorry, I can't help with that. I'm here to assist with astrology-related questions."


def check_content_safety(content: str) -> Tuple[bool, str]:
    content_lower = content.lower()

    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, content_lower):
            logger.warning(f"Prompt injection detected: {content[:100]}")
            return False, SAFE_FALLBACK_INJECTION

    for category in DISALLOWED_CATEGORIES:
        if category.replace("-", " ") in content_lower.replace("-", " "):
            if category in ("medical", "prescription", "diagnosis", "drug", "drugs", "suicide", "self-harm"):
                return False, SAFE_FALLBACK_MEDICAL
            elif category in ("legal", "lawsuit", "attorney", "sue", "criminal"):
                return False, SAFE_FALLBACK_LEGAL
            elif category in ("financial", "stock", "investment"):
                return False, SAFE_FALLBACK_FINANCIAL
            elif category in ("illegal", "hack", "exploit", "malware", "weapon", "violence"):
                return False, SAFE_FALLBACK_INJECTION

    return True, ""
