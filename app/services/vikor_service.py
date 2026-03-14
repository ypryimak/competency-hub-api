"""
VIKOR - VIseKriterijumska Optimizacija I Kompromisno Resenje

Used to rank candidates based on their competency-related scores.

Algorithm:
1. Build a candidate x competency score matrix using expert-weighted aggregation.
2. Compute best and worst values for each criterion.
3. Compute S_i (group utility) and R_i (individual regret).
4. Compute Q_i = v*(S-S*)/(S- - S*) + (1-v)*(R-R*)/(R- - R*).
5. Sort by Q_i where lower is better.

Default compromise parameter: v = 0.5.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class VIKORInput:
    candidate_id: int
    criterion_id: int
    aggregated_score: float  # already aggregated across all experts


@dataclass
class VIKOROutput:
    candidate_id: int
    s_score: float
    r_score: float
    q_score: float  # lower is better
    rank: int


def run_vikor(
    scores: list[VIKORInput],
    criterion_weights: dict[int, float],  # {criterion_id: weight}
    v: float = 0.5,
) -> list[VIKOROutput]:
    """
    Run VIKOR and return candidates sorted by final ranking.

    Args:
        scores: aggregated candidate scores per criterion
        criterion_weights: selection criterion weights
        v: compromise parameter in the [0, 1] range
    """
    if not scores:
        return []

    candidate_ids = list({s.candidate_id for s in scores})
    criterion_ids = list({s.criterion_id for s in scores})

    if len(candidate_ids) < 2:
        return [
            VIKOROutput(
                candidate_id=candidate_ids[0],
                s_score=0.0,
                r_score=0.0,
                q_score=0.0,
                rank=1,
            )
        ]

    score_matrix: dict[tuple[int, int], float] = {
        (s.candidate_id, s.criterion_id): s.aggregated_score
        for s in scores
    }

    total_w = sum(criterion_weights.get(cid, 0) for cid in criterion_ids)
    if total_w == 0:
        w = {cid: 1.0 / len(criterion_ids) for cid in criterion_ids}
    else:
        w = {cid: criterion_weights.get(cid, 0) / total_w for cid in criterion_ids}

    f_best: dict[int, float] = {}
    f_worst: dict[int, float] = {}
    for cid in criterion_ids:
        vals = [score_matrix.get((aid, cid), 0.0) for aid in candidate_ids]
        f_best[cid] = max(vals)
        f_worst[cid] = min(vals)

    s_scores: dict[int, float] = {}
    r_scores: dict[int, float] = {}

    for aid in candidate_ids:
        weighted_diffs = []
        for cid in criterion_ids:
            diff_range = f_best[cid] - f_worst[cid]
            if diff_range == 0:
                normalized = 0.0
            else:
                normalized = (f_best[cid] - score_matrix.get((aid, cid), 0.0)) / diff_range
            weighted_diffs.append(w[cid] * normalized)

        s_scores[aid] = sum(weighted_diffs)
        r_scores[aid] = max(weighted_diffs) if weighted_diffs else 0.0

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
