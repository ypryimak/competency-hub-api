"""
Document processing service based on spaCy.

Flow:
1. Run spaCy NER and noun chunk extraction on the input text.
2. Normalize tokens and compare them against competencies from the database.
3. Return matched ids together with unrecognized tokens for further review.

Model setup:
    pip install spacy
    python -m spacy download en_core_web_sm
    python -m spacy download uk_core_news_sm  # optional for Ukrainian resumes
"""
from __future__ import annotations

import re
from typing import Optional

import spacy
from spacy.language import Language

_nlp_cache: dict[str, Language] = {}


def _get_nlp(lang: str = "en") -> Language:
    """Lazy-load and cache the spaCy model."""
    model = "en_core_web_sm" if lang == "en" else "uk_core_news_sm"
    if model not in _nlp_cache:
        try:
            _nlp_cache[model] = spacy.load(model)
        except OSError:
            # Fall back to a blank language model when the package is missing.
            _nlp_cache[model] = spacy.blank(lang)
    return _nlp_cache[model]


def _normalize(text: str) -> str:
    """Normalize a token before comparison."""
    return re.sub(r"\s+", " ", text.lower().strip())


def extract_candidate_tokens(text: str, lang: str = "en") -> list[str]:
    """
    Extract candidate competency tokens from text using:
    - named entities;
    - noun chunks;
    - standalone NOUN/PROPN tokens.

    Returns a normalized list of unique tokens.
    """
    nlp = _get_nlp(lang)
    doc = nlp(text)

    tokens: set[str] = set()

    for ent in doc.ents:
        if ent.label_ in ("SKILL", "ORG", "PRODUCT", "WORK_OF_ART", "GPE"):
            tokens.add(_normalize(ent.text))

    if doc.has_annotation("DEP"):
        for chunk in doc.noun_chunks:
            normalized = _normalize(chunk.text)
            if 2 <= len(normalized) <= 60:
                tokens.add(normalized)

    for token in doc:
        if token.pos_ in ("NOUN", "PROPN") and not token.is_stop and len(token.text) > 2:
            tokens.add(_normalize(token.lemma_))

    return list(tokens)


def _contains_alias(source_text: str, alias: str) -> bool:
    escaped = re.escape(alias)
    if " " in alias:
        return re.search(rf"(?<!\w){escaped}(?!\w)", source_text) is not None
    return re.search(rf"\b{escaped}\b", source_text) is not None


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
    source_text: str | None = None,
) -> tuple[list[int], list[int], list[str]]:
    """
    Match extracted tokens against known competencies.

    Matching strategy:
    1. Exact normalized match.
    2. Limited substring matching for longer multi-word tokens.

    Returns:
        matched_ids
        matched_names
        unrecognized_tokens
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

        # Reduce noise from short generic words such as "model".
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

    normalized_source_text = _normalize(source_text or "")
    if normalized_source_text:
        for cid, aliases in normalized_map.items():
            if cid in used_ids:
                continue
            for alias in aliases:
                if len(alias) < 2:
                    continue
                if _contains_alias(normalized_source_text, alias):
                    matched_ids.append(cid)
                    matched_names.append(display_names.get(cid) or normalized_map[cid][0])
                    used_ids.add(cid)
                    break

    return matched_ids, matched_names, unrecognized


class DocumentProcessingService:
    """Service for parsing competencies from vacancy and resume text."""

    def parse_text(
        self,
        text: str,
        competency_map: dict[int, str | list[str] | tuple[str, ...] | set[str]],
        lang: str = "en",
    ) -> tuple[list[int], list[str], list[str]]:
        """
        Main entry point for competency parsing.

        Args:
            text: vacancy or resume text
            competency_map: {id: name} or aliases loaded from the database
            lang: input language, for example "en" or "uk"

        Returns:
            (matched_ids, matched_names, unrecognized_tokens)
        """
        tokens = extract_candidate_tokens(text, lang)
        return match_competencies(tokens, competency_map, source_text=text)


document_processing_service = DocumentProcessingService()
