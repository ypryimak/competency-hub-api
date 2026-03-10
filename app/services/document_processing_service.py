"""
Document processing service — MVP версія на базі spaCy.

Логіка:
1. Запускаємо spaCy NER на тексті → отримуємо іменовані сутності та noun chunks.
2. Нормалізуємо (lowercase, strip) і звіряємо з переліком компетенцій з БД.
3. Повертаємо matched ids + нерозпізнані токени (для валідації юзером).

Для встановлення моделі:
    pip install spacy
    python -m spacy download en_core_web_sm
    python -m spacy download uk_core_news_sm  # для українських резюме (опційно)
"""
from __future__ import annotations

import re
from typing import Optional
import spacy
from spacy.language import Language

_nlp_cache: dict[str, Language] = {}


def _get_nlp(lang: str = "en") -> Language:
    """Lazy-load spaCy модель (кешується)."""
    model = "en_core_web_sm" if lang == "en" else "uk_core_news_sm"
    if model not in _nlp_cache:
        try:
            _nlp_cache[model] = spacy.load(model)
        except OSError:
            # Fallback: якщо модель не встановлена — використовуємо blank
            _nlp_cache[model] = spacy.blank(lang)
    return _nlp_cache[model]


def _normalize(text: str) -> str:
    """Нормалізація токену для порівняння."""
    return re.sub(r"\s+", " ", text.lower().strip())


def extract_candidate_tokens(text: str, lang: str = "en") -> list[str]:
    """
    Витягує з тексту кандидатів на компетенції:
    - NER entities (SKILL, ORG, PRODUCT — часто містять технології)
    - Noun chunks (словосполучення-іменники)
    - Окремі слова з тегами NOUN/PROPN

    Повертає нормалізований список унікальних токенів.
    """
    nlp = _get_nlp(lang)
    doc = nlp(text)

    tokens: set[str] = set()

    # NER entities
    for ent in doc.ents:
        if ent.label_ in ("SKILL", "ORG", "PRODUCT", "WORK_OF_ART", "GPE"):
            tokens.add(_normalize(ent.text))

    # Noun chunks
    for chunk in doc.noun_chunks:
        normalized = _normalize(chunk.text)
        if 2 <= len(normalized) <= 60:
            tokens.add(normalized)

    # Окремі значущі іменники
    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and not token.is_stop and len(token.text) > 2:
            tokens.add(_normalize(token.lemma_))

    return list(tokens)


def _normalize_competency_terms(
    competency_terms: dict[int, str | list[str] | tuple[str, ...] | set[str]]
) -> dict[int, list[str]]:
    normalized: dict[int, list[str]] = {}
    for competency_id, value in competency_terms.items():
        if isinstance(value, str):
            raw_terms = [value]
        else:
            raw_terms = list(value)
        cleaned: list[str] = []
        seen: set[str] = set()
        for term in raw_terms:
            normalized_term = _normalize(term)
            if not normalized_term or normalized_term in seen:
                continue
            seen.add(normalized_term)
            cleaned.append(normalized_term)
        if cleaned:
            normalized[competency_id] = cleaned
    return normalized


def match_competencies(
    candidate_tokens: list[str],
    competency_terms: dict[int, str | list[str] | tuple[str, ...] | set[str]],
) -> tuple[list[int], list[int], list[str]]:
    """
    Звіряє токени з переліком компетенцій.

    Стратегії збігу (від точного до нечіткого):
    1. Точний збіг (normalized == normalized)
    2. Входження: токен містить назву компетенції або навпаки

    Повертає:
        matched_ids      — id компетенцій, що знайдені
        matched_names    — їх назви
        unrecognized     — токени, що не знайшли пари
    """
    display_names = {
        competency_id: value if isinstance(value, str) else next(iter(value), "")
        for competency_id, value in competency_terms.items()
    }
    normalized_map = _normalize_competency_terms(competency_terms)
    exact_lookup: dict[str, list[int]] = {}
    for cid, aliases in normalized_map.items():
        for alias in aliases:
            exact_lookup.setdefault(alias, []).append(cid)

    matched_ids: list[int] = []
    matched_names: list[str] = []
    unrecognized: list[str] = []
    used_ids: set[int] = set()

    for token in candidate_tokens:
        found = False
        # 1. Точний збіг
        for cid in exact_lookup.get(token, []):
            if cid in used_ids:
                continue
            matched_ids.append(cid)
            matched_names.append(display_names.get(cid) or normalized_map[cid][0])
            used_ids.add(cid)
            found = True
            break

        if found:
            continue

        # 2. Обмежене часткове входження тільки для довших multi-word token-ів.
        # Це зменшує шум типу "model" -> десятки нерелевантних skills.
        if " " in token and len(token) >= 6:
            for cid, aliases in normalized_map.items():
                if cid in used_ids:
                    continue
                for alias in aliases:
                    if len(alias) < 4 or " " not in alias:
                        continue
                    if alias in token or token in alias:
                        matched_ids.append(cid)
                        matched_names.append(display_names.get(cid) or normalized_map[cid][0])
                        used_ids.add(cid)
                        found = True
                        break
                if found:
                    break

        if not found and len(token) > 3:
            unrecognized.append(token)

    return matched_ids, matched_names, unrecognized


class DocumentProcessingService:
    """Сервіс для парсингу компетенцій з текстів вакансій і резюме."""

    def parse_text(
        self,
        text: str,
        competency_map: dict[int, str | list[str] | tuple[str, ...] | set[str]],
        lang: str = "en",
    ) -> tuple[list[int], list[str], list[str]]:
        """
        Головний метод: текст → matched competency ids.

        Args:
            text: текст вакансії або резюме
            competency_map: {id: name} з БД
            lang: мова тексту ("en" або "uk")

        Returns:
            (matched_ids, matched_names, unrecognized_tokens)
        """
        tokens = extract_candidate_tokens(text, lang)
        return match_competencies(tokens, competency_map)


document_processing_service = DocumentProcessingService()
