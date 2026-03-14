"""
OPA - Ordinal Priority Approach
Source: Ataei et al. (2020), Applied Soft Computing

Inputs:
    experts:      [{id, rank}]          expert ranks (lower rank = higher priority)
    criteria:     [{id, rank}]          criterion ranks per expert
    alternatives: [{id, rank, crit_id}] alternative ranks per criterion and expert

Linear program:
    Max Z
    Z <= r_i * (r_j * (w_ijk_rk - w_ijk_rk+1))   for all i,j,rk
    Z <= r_i * r_j * r_m * w_ijk_rm              for all i,j,rm
    Sum(w_ijk) = 1
    w_ijk >= 0

Outputs:
    w_k = sum_i sum_j w_ijk   alternative weight
    w_j = sum_i sum_k w_ijk   criterion weight
    w_i = sum_j sum_k w_ijk   expert weight
"""
from __future__ import annotations

from dataclasses import dataclass

import pulp


@dataclass
class ExpertInput:
    id: int
    rank: int  # 1 = highest priority


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
    """Run OPA and return weights for experts, criteria, and alternatives."""
    if not experts or not criteria or not alternatives:
        return OPAOutput(
            expert_weights={},
            criterion_weights={},
            alternative_weights={},
            solved=False,
            message="Not enough data to run OPA",
        )

    expert_ids = [e.id for e in experts]
    expert_rank = {e.id: e.rank for e in experts}

    crit_by_expert: dict[int, list[CriterionInput]] = {e.id: [] for e in experts}
    for c in criteria:
        crit_by_expert[c.expert_id].append(c)

    alt_by_exp_crit: dict[tuple[int, int], list[AlternativeInput]] = {}
    for a in alternatives:
        key = (a.expert_id, a.criterion_id)
        alt_by_exp_crit.setdefault(key, []).append(a)

    prob = pulp.LpProblem("OPA", pulp.LpMaximize)
    z = pulp.LpVariable("Z", lowBound=0)
    prob += z

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
            message="Failed to build LP variables - check ranking completeness",
        )

    prob += pulp.lpSum(w.values()) == 1

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
                    next_alt = alts_sorted[idx + 1]
                    next_key = (e.id, c.id, next_alt.id)
                    if next_key in w:
                        prob += z <= r_i * r_j * (w[key] - w[next_key])
                else:
                    r_m = alt.rank
                    prob += z <= r_i * r_j * r_m * w[key]

    prob.solve(pulp.PULP_CBC_CMD(msg=0))

    if pulp.LpStatus[prob.status] != "Optimal":
        return OPAOutput(
            expert_weights={},
            criterion_weights={},
            alternative_weights={},
            solved=False,
            message=f"LP did not find an optimal solution: {pulp.LpStatus[prob.status]}",
        )

    alt_ids = list({a.id for a in alternatives})
    crit_ids = list({c.id for c in criteria})
    alternative_weights: dict[int, float] = {aid: 0.0 for aid in alt_ids}
    criterion_weights: dict[int, float] = {cid: 0.0 for cid in crit_ids}
    expert_weights: dict[int, float] = {eid: 0.0 for eid in expert_ids}

    for (eid, cid, aid), var in w.items():
        val = pulp.value(var) or 0.0
        alternative_weights[aid] = round(alternative_weights.get(aid, 0.0) + val, 6)
        criterion_weights[cid] = round(criterion_weights.get(cid, 0.0) + val, 6)
        expert_weights[eid] = round(expert_weights.get(eid, 0.0) + val, 6)

    # Divide by the number of alternatives so criterion weights reflect
    # criterion importance rather than criterion*alternative aggregation.
    n_alts = len(alt_ids) if alt_ids else 1
    criterion_weights = {
        cid: round(weight / n_alts, 6)
        for cid, weight in criterion_weights.items()
    }

    return OPAOutput(
        expert_weights=expert_weights,
        criterion_weights=criterion_weights,
        alternative_weights=alternative_weights,
        solved=True,
        message="OK",
    )
