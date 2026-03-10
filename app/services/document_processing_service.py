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


def match_competencies(
    candidate_tokens: list[str],
    competency_map: dict[int, str],  # {id: name}
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
    normalized_map = {cid: _normalize(name) for cid, name in competency_map.items()}
    exact_lookup: dict[str, list[int]] = {}
    for cid, cname in normalized_map.items():
        exact_lookup.setdefault(cname, []).append(cid)

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
            matched_names.append(competency_map[cid])
            used_ids.add(cid)
            found = True
            break

        if found:
            continue

        # 2. Обмежене часткове входження тільки для довших multi-word token-ів.
        # Це зменшує шум типу "model" -> десятки нерелевантних skills.
        if " " in token and len(token) >= 6:
            for cid, cname in normalized_map.items():
                if cid in used_ids:
                    continue
                if len(cname) < 4 or " " not in cname:
                    continue
                if cname in token or token in cname:
                    matched_ids.append(cid)
                    matched_names.append(competency_map[cid])
                    used_ids.add(cid)
                    found = True
                    break

        if not found and len(token) > 3:
            unrecognized.append(token)

    return matched_ids, matched_names, unrecognized


class DocumentProcessingService:
    """Сервіс для парсингу компетенцій з текстів вакансій і резюме."""

    def parse_text(
        self,
        text: str,
        competency_map: dict[int, str],
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
