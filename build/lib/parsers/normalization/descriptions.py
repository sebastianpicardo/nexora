from __future__ import annotations

import re
import unicodedata

from rapidfuzz import fuzz

ABBREVIATIONS = {
    "pza": "pieza",
    "pzas": "piezas",
    "und": "unidad",
    "unds": "unidades",
    "un": "unidad",
    "u": "unidad",
    "ea": "unidad",
    "each": "unidad",
    "kg": "kilogramo",
    "kgs": "kilogramo",
    "kilo": "kilogramo",
    "kilos": "kilogramo",
    "gr": "gramo",
    "grs": "gramo",
    "g": "gramo",
    "l": "litro",
    "lt": "litro",
    "lts": "litro",
    "ml": "mililitro",
    "cc": "mililitro",
    "mt": "metro",
    "mts": "metro",
    "m": "metro",
    "cm": "centimetro",
    "mm": "milimetro",
    "m2": "metro cuadrado",
    "m3": "metro cubico",
    "inox": "inoxidable",
    "acero inox": "acero inoxidable",
    "npt": "npt",
    "sch": "schedule",
    "diam": "diametro",
    "diam.": "diametro",
    "aprox": "aproximado",
    "c/u": "cada uno",
    "c/u.": "cada uno",
}

PHRASE_ABBREVIATIONS = {
    "acero inox": "acero inoxidable",
    "acero inox.": "acero inoxidable",
    "cada uno": "unidad",
    "c/u": "unidad",
}


def strip_accents(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_text(value: str) -> str:
    text = strip_accents(value or "").lower()
    text = text.replace("&", " y ")
    text = text.replace("²", "2").replace("³", "3")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def normalize_description(value: str) -> str:
    text = normalize_text(value)
    for phrase, replacement in PHRASE_ABBREVIATIONS.items():
        normalized_phrase = normalize_text(phrase)
        if normalized_phrase:
            text = re.sub(rf"\b{re.escape(normalized_phrase)}\b", replacement, text)

    tokens = [ABBREVIATIONS.get(token, token) for token in text.split()]
    return " ".join(tokens).strip()


def normalize_supplier_name(value: str) -> str:
    text = normalize_text(value)
    for suffix in (" s a", " sa", " spa", " ltda", " limitada", " eirl"):
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
    return text


def clean_sku(value: str | None) -> str | None:
    if not value:
        return None
    sku = re.sub(r"\s+", "", str(value).upper())
    sku = re.sub(r"[^A-Z0-9._/-]", "", sku)
    return sku or None


def similarity(left: str, right: str) -> float:
    return float(fuzz.token_set_ratio(normalize_description(left), normalize_description(right)))


def compact_description(value: str, max_length: int = 500) -> str:
    normalized = normalize_description(value)
    return normalized[:max_length].strip()
