import spacy

from app.services import document_processing_service as document_processing_module
from app.services.document_processing_service import document_processing_service


def test_parse_text_falls_back_when_spacy_model_has_no_parser(monkeypatch):
    monkeypatch.setattr(document_processing_module, "_get_nlp", lambda lang="en": spacy.blank(lang))

    matched_ids, matched_names, unrecognized_tokens = document_processing_service.parse_text(
        text="Experienced in Python, project management, and stakeholder communication.",
        competency_map={
            1: "python",
            2: "project management",
            3: "leadership",
        },
    )

    assert matched_ids == [1, 2]
    assert matched_names == ["python", "project management"]
    assert "leadership" not in matched_names
    assert isinstance(unrecognized_tokens, list)


def test_parse_text_matches_aliases_in_deduplicated_pdf_text(monkeypatch):
    monkeypatch.setattr(document_processing_module, "_get_nlp", lambda lang="en": spacy.blank(lang))

    matched_ids, matched_names, _ = document_processing_service.parse_text(
        text="HHaarrddwwoorrkkiinngg,, ggoooodd ccoommmmuunniiccaattiioonn aanndd oorrggaanniizzaattiioonnaall sskkiillllss",
        competency_map={
            1: ["interpersonal skills", "communication"],
            2: ["organizational skills"],
            3: ["network administration"],
        },
    )

    assert matched_ids == [1, 2]
    assert matched_names == ["interpersonal skills", "organizational skills"]
