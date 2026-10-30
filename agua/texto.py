"""Utilidades de texto: tokens e comparação de títulos."""
from __future__ import annotations

from .scoring import norm

STOPWORDS = {
    "a", "o", "as", "os", "um", "uma", "de", "da", "do", "das", "dos",
    "e", "em", "no", "na", "nos", "nas", "por", "para", "com", "sem",
    "que", "se", "ao", "aos", "apos", "sobre", "mais", "ja", "nao",
    "the", "of", "and", "to",
}


def tokens(titulo: str) -> set[str]:
    return {t for t in norm(titulo).split() if t and t not in STOPWORDS}


def parecido(a: set[str], b: set[str], limite: float) -> bool:
    """Mesmo fato? Compara por contenção: títulos diferentes, mesmas palavras."""
    if len(a) < 3 or len(b) < 3:
        return a == b
    return len(a & b) / min(len(a), len(b)) >= limite
