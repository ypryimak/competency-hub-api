"""
OPA — Ordinal Priority Approach
Джерело: Ataei et al. (2020), Applied Soft Computing

Вхід:
    experts:      [{id, rank}]           — ранги експертів (менший ранг = вищий пріоритет)
    criteria:     [{id, rank}]           — ранги критеріїв для кожного експерта
    alternatives: [{id, rank, crit_id}]  — ранги альтернатив за критерієм для експерта

LP модель:
    Max Z
    Z ≤ r_i * (r_j * (w_ijk_rk - w_ijk_rk+1))   ∀ i,j,rk
    Z ≤ r_i * r_j * r_m * w_ijk_rm               ∀ i,j,rm  (остання альтернатива)
    Σ w_ijk = 1
    w_ijk ≥ 0

Виходи:
    w_k  = Σ_i Σ_j w_ijk   — вага альтернативи k
    w_j  = Σ_i Σ_k w_ijk   — вага критерію j
    w_i  = Σ_j Σ_k w_ijk   — вага експерта i
"""
from __future__ import annotations
from dataclasses import dataclass
import pulp


@dataclass
class ExpertInput:
    id: int
    rank: int   # 1 = найвищий пріоритет


@dataclass
class CriterionInput:
    id: int
    expert_id: int
    rank: int


@dataclass
class AlternativeInput:
    id: int
    expert_id: int
    criterion_id: int
    rank: int


@dataclass
class OPAOutput:
    expert_weights: dict[int, float]
    criterion_weights: dict[int, float]
    alternative_weights: dict[int, float]
    solved: bool
    message: str


def run_opa(
    experts: list[ExpertInput],
    criteria: list[CriterionInput],
    alternatives: list[AlternativeInput],
) -> OPAOutput:
    """
    Запускає OPA і повертає ваги для експертів, критеріїв та альтернатив.
    """
    if not experts or not criteria or not alternatives:
        return OPAOutput(
            expert_weights={},
            criterion_weights={},
            alternative_weights={},
            solved=False,
            message="Недостатньо даних для запуску OPA",
        )

    # ── Індексування вхідних даних ──────────────────────────
    expert_ids = [e.id for e in experts]
    expert_rank = {e.id: e.rank for e in experts}

    # criteria per expert: {expert_id: [{id, rank}]}
    crit_by_expert: dict[int, list[CriterionInput]] = {e.id: [] for e in experts}
    for c in criteria:
        crit_by_expert[c.expert_id].append(c)

    # alternatives per expert+criterion: {(expert_id, criterion_id): [{id, rank}]}
    alt_by_exp_crit: dict[tuple[int, int], list[AlternativeInput]] = {}
    for a in alternatives:
        key = (a.expert_id, a.criterion_id)
        alt_by_exp_crit.setdefault(key, []).append(a)

    # ── LP модель ───────────────────────────────────────────
    prob = pulp.LpProblem("OPA", pulp.LpMaximize)
    Z = pulp.LpVariable("Z", lowBound=0)
    prob += Z  # maximize Z

    # Змінні w_ijk: {(expert_id, criterion_id, alternative_id): LpVariable}
    w: dict[tuple[int, int, int], pulp.LpVariable] = {}
    for e in experts:
        for c in crit_by_expert.get(e.id, []):
            for a in alt_by_exp_crit.get((e.id, c.id), []):
                key = (e.id, c.id, a.id)
                w[key] = pulp.LpVariable(f"w_{e.id}_{c.id}_{a.id}", lowBound=0)

    if not w:
        return OPAOutput(
            expert_weights={},
            criterion_weights={},
            alternative_weights={},
            solved=False,
            message="Не вдалося побудувати змінні LP — перевірте повноту оцінок",
        )

    # Обмеження: сума всіх w = 1
    prob += pulp.lpSum(w.values()) == 1

    # Обмеження на ранги альтернатив (основні обмеження OPA)
    for e in experts:
        r_i = expert_rank[e.id]
        for c in crit_by_expert.get(e.id, []):
            r_j = c.rank
            alts_sorted = sorted(
                alt_by_exp_crit.get((e.id, c.id), []),
                key=lambda a: a.rank,
            )
            for idx, alt in enumerate(alts_sorted):
                key = (e.id, c.id, alt.id)
                if key not in w:
                    continue
                if idx < len(alts_sorted) - 1:
                    # Z ≤ r_i * r_j * (w_ijk_rk - w_ijk_rk+1)
                    next_alt = alts_sorted[idx + 1]
                    next_key = (e.id, c.id, next_alt.id)
                    if next_key in w:
                        prob += Z <= r_i * r_j * (w[key] - w[next_key])
                else:
                    # Остання альтернатива: Z ≤ r_i * r_j * r_m * w_ijk_rm
                    r_m = alt.rank
                    prob += Z <= r_i * r_j * r_m * w[key]

    # ── Розв'язок ───────────────────────────────────────────
    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return OPAOutput(
            expert_weights={},
            criterion_weights={},
            alternative_weights={},
            solved=False,
            message=f"LP не знайшов оптимального рішення: {pulp.LpStatus[prob.status]}",
        )

    # ── Агрегація результатів ───────────────────────────────
    # По OPA:
    #   w_k (альтернатива) = Σ_i Σ_j w_ijk
    #   w_j (критерій)     = Σ_i Σ_k w_ijk  (сума по всіх альтернативах і експертах)
    #   w_i (експерт)      = Σ_j Σ_k w_ijk
    # Всі три суми = 1 лише при нормалізації. Повертаємо сирі суми — нормалізацію
    # робить сервіс при необхідності.
    alt_ids = list({a.id for a in alternatives})
    crit_ids = list({c.id for c in criteria})
    alternative_weights: dict[int, float] = {aid: 0.0 for aid in alt_ids}
    criterion_weights: dict[int, float] = {cid: 0.0 for cid in crit_ids}
    expert_weights: dict[int, float] = {e.id: 0.0 for e in experts}

    for (eid, cid, aid), var in w.items():
        val = pulp.value(var) or 0.0
        alternative_weights[aid] = round(alternative_weights.get(aid, 0.0) + val, 6)
        criterion_weights[cid] = round(criterion_weights.get(cid, 0.0) + val, 6)
        expert_weights[eid] = round(expert_weights.get(eid, 0.0) + val, 6)

    # Нормалізуємо criterion_weights (ділимо на кількість альтернатив)
    # щоб w_j відображав реальний пріоритет критерію, а не множився на |alternatives|
    n_alts = len(alt_ids) if alt_ids else 1
    criterion_weights = {
        cid: round(w_val / n_alts, 6)
        for cid, w_val in criterion_weights.items()
    }

    return OPAOutput(
        expert_weights=expert_weights,
        criterion_weights=criterion_weights,
        alternative_weights=alternative_weights,
        solved=True,
        message="OK",
    )
