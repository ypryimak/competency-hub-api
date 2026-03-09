"""
VIKOR — VIseKriterijumska Optimizacija I Kompromisno Resenje

Використовується для ранжування кандидатів на основі їх оцінок за компетенціями.

Алгоритм:
1. Будуємо матрицю оцінок (candidates × competencies) — зважена агрегація по експертах
2. Визначаємо f*_j (ідеал) і f-_j (антиідеал) для кожної компетенції
3. Розраховуємо S_i (сума зважених відстаней), R_i (макс. зважена відстань)
4. Розраховуємо Q_i = v*(S-S*)/(S- - S*) + (1-v)*(R-R*)/(R- - R*)
5. Сортуємо за Q_i (менше = краще)

Параметр v = 0.5 (компроміс між більшістю і опонентом)
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass
class VIKORInput:
    candidate_id: int
    competency_id: int
    aggregated_score: float     # вже зважена агрегована оцінка по всіх експертах


@dataclass
class VIKOROutput:
    candidate_id: int
    s_score: float              # utility measure
    r_score: float              # regret measure
    q_score: float              # компромісний рейтинг (менше = краще)
    rank: int


def run_vikor(
    scores: list[VIKORInput],
    competency_weights: dict[int, float],   # {competency_id: weight} з МК
    v: float = 0.5,
) -> list[VIKOROutput]:
    """
    Запускає VIKOR і повертає ранжований список кандидатів.

    Args:
        scores: агреговані оцінки кандидатів по компетенціях
        competency_weights: ваги компетенцій з МК (final_weight після OPA)
        v: параметр компромісу [0, 1], зазвичай 0.5
    """
    if not scores:
        return []

    # ── Збираємо унікальні id ────────────────────────────
    candidate_ids = list({s.candidate_id for s in scores})
    competency_ids = list({s.competency_id for s in scores})

    if len(candidate_ids) < 2:
        # Для одного кандидата VIKOR не має сенсу — повертаємо rank=1
        return [VIKOROutput(
            candidate_id=candidate_ids[0],
            s_score=0.0, r_score=0.0, q_score=0.0, rank=1
        )]

    # ── Матриця оцінок: {(candidate_id, competency_id): score} ──
    score_matrix: dict[tuple[int, int], float] = {
        (s.candidate_id, s.competency_id): s.aggregated_score
        for s in scores
    }

    # ── Нормалізовані ваги компетенцій ──────────────────
    total_w = sum(competency_weights.get(cid, 0) for cid in competency_ids)
    if total_w == 0:
        # Рівні ваги якщо не задані
        w = {cid: 1.0 / len(competency_ids) for cid in competency_ids}
    else:
        w = {cid: competency_weights.get(cid, 0) / total_w for cid in competency_ids}

    # ── Ідеал f* і антиідеал f- для кожної компетенції ──
    # Вища оцінка = краще (benefit criterion)
    f_best: dict[int, float] = {}
    f_worst: dict[int, float] = {}
    for cid in competency_ids:
        vals = [
            score_matrix.get((aid, cid), 0.0)
            for aid in candidate_ids
        ]
        f_best[cid] = max(vals)
        f_worst[cid] = min(vals)

    # ── S і R для кожного кандидата ─────────────────────
    s_scores: dict[int, float] = {}
    r_scores: dict[int, float] = {}

    for aid in candidate_ids:
        weighted_diffs = []
        for cid in competency_ids:
            diff_range = f_best[cid] - f_worst[cid]
            if diff_range == 0:
                normalized = 0.0
            else:
                normalized = (f_best[cid] - score_matrix.get((aid, cid), 0.0)) / diff_range
            weighted_diffs.append(w[cid] * normalized)

        s_scores[aid] = sum(weighted_diffs)
        r_scores[aid] = max(weighted_diffs) if weighted_diffs else 0.0

    # ── Q score ──────────────────────────────────────────
    s_best = min(s_scores.values())
    s_worst = max(s_scores.values())
    r_best = min(r_scores.values())
    r_worst = max(r_scores.values())

    q_scores: dict[int, float] = {}
    for aid in candidate_ids:
        if s_worst - s_best == 0:
            s_term = 0.0
        else:
            s_term = v * (s_scores[aid] - s_best) / (s_worst - s_best)

        if r_worst - r_best == 0:
            r_term = 0.0
        else:
            r_term = (1 - v) * (r_scores[aid] - r_best) / (r_worst - r_best)

        q_scores[aid] = round(s_term + r_term, 6)

    # ── Ранжування (менший Q = кращий кандидат) ─────────
    sorted_candidates = sorted(candidate_ids, key=lambda aid: q_scores[aid])

    return [
        VIKOROutput(
            candidate_id=aid,
            s_score=round(s_scores[aid], 6),
            r_score=round(r_scores[aid], 6),
            q_score=q_scores[aid],
            rank=rank + 1,
        )
        for rank, aid in enumerate(sorted_candidates)
    ]
