"""Conversation router — intent detection for pre-RAG short-circuit responses.

This module classifies incoming user messages into conversational intents
(greetings, small-talk, identity, gratitude, farewell) and returns a static
contextual response when a match is found.

When a match is detected the caller should return the response immediately
and skip the RAG pipeline entirely — no embeddings, no vector search, no LLM.
"""

import re
import logging
from typing import Union

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Intent definitions
# ---------------------------------------------------------------------------

# Each entry maps an intent name to a tuple of literal trigger phrases.
# Matching is case-insensitive and ignores leading/trailing punctuation/spaces.
_INTENT_PATTERNS: dict[str, list[str]] = {
    "greeting": [
        "hi", "hello", "hey", "hiya", "howdy",
        "good morning", "good afternoon", "good evening", "good night",
        "what's up", "whats up", "sup",
    ],
    "small_talk": [
        "how are you", "how are you doing", "how do you do",
        "how's it going", "how is it going",
        "are you ok", "are you okay",
        "how have you been",
    ],
    "identity": [
        "who are you", "what are you", "what is webgpt",
        "tell me about yourself", "what can you do", "what do you do",
        "what is this", "what's this", "whats this",
    ],
    "gratitude": [
        "thanks", "thank you", "thank you so much", "thanks a lot",
        "appreciate it", "appreciated", "many thanks", "cheers",
        "ty", "thx",
    ],
    "farewell": [
        "bye", "goodbye", "good bye", "see you", "see ya",
        "take care", "later", "cya", "ttyl", "so long",
    ],
}

# Pre-compile patterns once at module load time for performance.
# Each pattern is anchored to the full normalised string (after stripping
# punctuation and collapsing whitespace) so "hi!" still matches "hi".
_COMPILED: dict[str, list[re.Pattern[str]]] = {
    intent: [re.compile(r"^\s*" + re.escape(phrase) + r"\s*$", re.IGNORECASE)
             for phrase in phrases]
    for intent, phrases in _INTENT_PATTERNS.items()
}


def _normalise(text: str) -> str:
    """Strip trailing/leading punctuation and collapse internal whitespace."""
    text = text.strip()
    # Remove trailing punctuation common in conversational messages
    text = re.sub(r"[!?.,:;~]+$", "", text).strip()
    # Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)
    return text


def detect_intent(message: str) -> Union[str, None]:
    """Classify a user message into a conversational intent.

    Args:
        message: The raw user message string.

    Returns:
        The intent name (e.g. ``"greeting"``) if matched, else ``None``.
    """
    normalised = _normalise(message)
    for intent, patterns in _COMPILED.items():
        for pattern in patterns:
            if pattern.match(normalised):
                logger.debug(
                    "Conversation router matched intent '%s' for message: %r",
                    intent,
                    message,
                )
                return intent
    return None


def build_response(
    intent: str,
    *,
    source_title: Union[str, None] = None,
    source_url: Union[str, None] = None,
) -> str:
    """Return an appropriate static response for a detected conversational intent.

    Args:
        intent: The intent name returned by :func:`detect_intent`.
        source_title: Optional title of the currently active scraped source.
        source_url: Optional URL of the currently active scraped source.

    Returns:
        A markdown-safe response string.
    """
    if intent == "greeting":
        if source_title:
            label = f'**{source_title}**'
            if source_url:
                label = f'[{source_title}]({source_url})'
            return (
                "Hello! 👋\n\n"
                f"You're currently exploring: {label}\n\n"
                "Ask me anything about this website."
            )
        return (
            "Hello! 👋\n\n"
            "I'm **WebGPT**.\n\n"
            "Ask me anything after indexing a website, and I'll answer using only "
            "the information extracted from that website."
        )

    if intent == "small_talk":
        return (
            "I'm doing great — ready to help! 🤖\n\n"
            "Ask me anything about the website you've indexed and I'll find the answer."
        )

    if intent == "identity":
        return (
            "I'm **WebGPT**.\n\n"
            "I specialise in answering questions using the content of the website "
            "you've indexed, rather than relying on general internet knowledge.\n\n"
            "Simply index a website and ask me anything about it."
        )

    if intent == "gratitude":
        return (
            "You're welcome! 😊\n\n"
            "Feel free to ask anything else about the indexed website."
        )

    if intent == "farewell":
        return (
            "Goodbye! 👋\n\n"
            "Come back anytime you need help exploring a website."
        )

    # Fallback — should never reach here if called after detect_intent succeeds
    return "How can I help you?"
