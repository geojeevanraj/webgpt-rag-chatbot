import aiohttp
import json
import logging
import re
from typing import Any
from app.core.config import settings

logger = logging.getLogger(__name__)


def extract_questions_from_json(data: Any) -> list[str]:
    """Helper to extract questions list from parsed JSON data structures."""
    if isinstance(data, list):
        return [str(item).strip() for item in data if item]
    elif isinstance(data, dict):
        # If wrapped in a dictionary (e.g. {"questions": [...]}), look for list values
        for val in data.values():
            if isinstance(val, list):
                return [str(item).strip() for item in val if item]
    return []


def parse_questions_defensively(text: str) -> list[str]:
    """Parse the Groq response text defensively to extract exactly 10 questions.

    Handles clean JSON arrays, markdown-fenced JSON code blocks, dictionary wrapping,
    and numbered/bulleted plain text fallbacks.
    """
    cleaned = text.strip()

    # 1. Clean markdown code blocks if present
    if "```" in cleaned:
        parts = cleaned.split("```")
        # Text inside fenced code blocks is at odd indices after split
        for part in parts[1::2]:
            clean_part = part.strip()
            if clean_part.startswith("json"):
                clean_part = clean_part[4:].strip()
            try:
                data = json.loads(clean_part)
                parsed = extract_questions_from_json(data)
                if parsed:
                    return parsed
            except Exception:
                pass

    # 2. Try to parse the entire raw text as JSON
    try:
        data = json.loads(cleaned)
        parsed = extract_questions_from_json(data)
        if parsed:
            return parsed
    except Exception:
        pass

    # 3. Fallback: Parse line-by-line using regular expressions for list items/questions
    questions = []
    lines = cleaned.split("\n")
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove list markers: numbers, dashes, stars, quotes
        cleaned_line = re.sub(r'^["\'\-*\d\.\s]+', '', line)
        cleaned_line = re.sub(r'["\']+,?$', '', cleaned_line).strip()
        if cleaned_line.endswith("?") or len(cleaned_line) > 15:
            questions.append(cleaned_line)
            if len(questions) >= 10:
                break

    return questions[:10]


class GroqService:
    """Service to interact with the Groq API for suggestions generation."""

    def __init__(self) -> None:
        self.api_key = settings.GROQ_API_KEY.strip()
        self.model = settings.GROQ_MODEL.strip() or "llama-3.3-70b-versatile"
        self.api_url = "https://api.groq.com/openai/v1/chat/completions"

    async def generate_suggestions(self, website_content: str) -> list[str]:
        """Generate suggested questions based on website content using the Groq API.

        Future-ready structure: In the future, this method can accept difficulty
        levels or return categorizations/reading recommendations.
        """
        if not self.api_key:
            logger.warning("GROQ_API_KEY environment variable is missing or empty. Skipping suggestions.")
            return []

        # Optimization: Limit content context to ~12,000 - 15,000 characters
        truncated_content = website_content[:15000]

        prompt = (
            "You are an AI educational assistant.\n\n"
            "Based ONLY on the following website content, generate exactly 10 useful questions that users are most likely to ask.\n\n"
            "Requirements:\n"
            "* Cover beginner, intermediate, advanced and expert topics.\n"
            "* Questions must be diverse.\n"
            "* Avoid duplicates.\n"
            "* Questions should encourage exploration.\n"
            "* Do NOT answer them.\n"
            "* Return ONLY a JSON array of strings.\n\n"
            "Website Content:\n"
            f"{truncated_content}"
        )

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.4
        }

        logger.info("Requesting suggested questions from Groq API using model %s...", self.model)
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_url, headers=headers, json=payload, timeout=20) as resp:
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.warning("Groq API returned error status %d: %s", resp.status, error_text)
                        return []

                    result = await resp.json()
                    raw_content = result["choices"][0]["message"]["content"]
                    
                    # Parse the questions list defensively
                    questions = parse_questions_defensively(raw_content)
                    return questions
        except Exception as e:
            logger.warning("Failed to generate suggested questions from Groq: %s", e)
            return []
