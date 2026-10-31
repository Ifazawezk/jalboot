"""Text normalization for Arabic and English.

Customers type on phones, so the same Arabic word arrives with or without
hamza, with ة or ه, and with ى or ي. Both the query and the documents pass
through the same folding before they are compared.
"""

from __future__ import annotations

import re
import unicodedata

DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۜ۟-۪ۨ-ۭ]")
TATWEEL = "ـ"
ALEF_FORMS = re.compile("[آأإٱٲٳ]")
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
PUNCTUATION = str.maketrans({"،": ",", "؛": ";", "؟": "?", "٪": "%"})
INVISIBLE = re.compile("[​-‏‪-‮⁠-⁩﻿]")
ARABIC_CHAR = re.compile("[؀-ۿ]")
LATIN_CHAR = re.compile("[A-Za-z]")


def normalize_arabic(text: str) -> str:
    text = DIACRITICS.sub("", text).replace(TATWEEL, "")
    text = ALEF_FORMS.sub("ا", text)
    return text.replace("ة", "ه").replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")


def strip_invisible(text: str) -> str:
    """Zero width and bidi control characters are removed before any check runs,
    because they can split a word so that a pattern no longer matches it."""
    return INVISIBLE.sub("", text)


def normalize(text: str) -> str:
    """Fold mixed Arabic and English text for matching."""
    text = unicodedata.normalize("NFKC", text)
    text = strip_invisible(text).translate(DIGITS).translate(PUNCTUATION)
    return normalize_arabic(text).lower()


def detect_language(text: str, default: str = "en") -> str:
    """Return "ar" when Arabic letters are at least as common as Latin ones."""
    arabic = len(ARABIC_CHAR.findall(text))
    latin = len(LATIN_CHAR.findall(text))
    if not arabic and not latin:
        return default
    return "ar" if arabic and arabic >= latin else "en"
