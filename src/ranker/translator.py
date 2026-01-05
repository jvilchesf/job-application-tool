"""
LLM-based job description translator.
Translates German job descriptions to English using OpenAI.
"""

import re
from typing import Optional

from loguru import logger
from openai import AsyncOpenAI

from shared.config import Settings, get_settings


class JobTranslator:
    """Translates job descriptions using OpenAI."""

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self._client: Optional[AsyncOpenAI] = None

    @property
    def client(self) -> AsyncOpenAI:
        """Get or create OpenAI client."""
        if self._client is None:
            self._client = AsyncOpenAI(
                api_key=self.settings.openai_api_key.get_secret_value()
            )
        return self._client

    def _detect_language(self, text: str) -> str:
        """Simple language detection based on common words."""
        german_indicators = [
            "und", "der", "die", "das", "ist", "wir", "sie", "für",
            "mit", "von", "auf", "bei", "zur", "zum", "eine", "einen",
            "sowie", "oder", "auch", "als", "ihre", "unser", "werden",
            "anforderungen", "aufgaben", "erfahrung", "kenntnisse",
        ]

        text_lower = text.lower()
        german_count = sum(
            1 for word in german_indicators
            if re.search(r'\b' + word + r'\b', text_lower)
        )

        # If more than 5 German indicator words, likely German
        if german_count > 5:
            return "de"
        return "en"

    async def translate_if_needed(
        self,
        text: str,
        target_language: str = "en",
    ) -> tuple[str, bool]:
        """
        Translate text if not in target language.

        Returns:
            Tuple of (translated_text, was_translated)
        """
        detected = self._detect_language(text)

        if detected == target_language:
            logger.debug("Text already in target language, skipping translation")
            return text, False

        logger.info(f"Translating text from {detected} to {target_language}")
        translated = await self.translate(text, target_language)
        return translated, True

    async def translate(
        self,
        text: str,
        target_language: str = "en",
    ) -> str:
        """
        Translate text to target language.

        Args:
            text: Text to translate
            target_language: Target language code (e.g., "en", "de")

        Returns:
            Translated text
        """
        if not text.strip():
            return text

        language_names = {
            "en": "English",
            "de": "German",
            "fr": "French",
        }
        target_name = language_names.get(target_language, target_language)

        prompt = f"""Translate the following job description to {target_name}.
Keep the formatting and structure intact.
Only output the translation, nothing else.

Text to translate:
{text}"""

        try:
            response = await self.client.chat.completions.create(
                model=self.settings.openai_model_mini,  # Use mini model for translation
                messages=[
                    {
                        "role": "system",
                        "content": f"You are a professional translator. Translate job descriptions accurately to {target_name}.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            translated = response.choices[0].message.content
            return translated.strip() if translated else text

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text  # Return original on error
