"""The offline language detector (lingua-py), for Sources whose metadata states no language."""

from functools import lru_cache

from lingua import Language, LanguageDetector, LanguageDetectorBuilder

# Enough text for a confident answer; detection time grows with the text.
SAMPLE_WORDS = 1500


@lru_cache
def _detector() -> LanguageDetector:
    # Low accuracy mode needs far less memory and is reliable on long texts like these.
    return LanguageDetectorBuilder.from_all_languages().with_low_accuracy_mode().build()


def detect(text: str) -> str | None:
    """The base language code of `text` (`en`), or None when the detector cannot tell."""
    sample = " ".join(text.split()[:SAMPLE_WORDS])
    if not sample:
        return None
    language = _detector().detect_language_of(sample)
    return language.iso_code_639_1.name.lower() if language else None


def known_languages() -> list[str]:
    """Every language code the detector knows, which is also what the user can choose from."""
    return sorted(language.iso_code_639_1.name.lower() for language in Language.all())
