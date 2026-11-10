"""세 배정 정책을 동일한 합성 지문과 풀이 일정에서 비교한다."""

from __future__ import annotations

import numpy as np
import pandas as pd

from .elo import EloModel
from .evaluate import score
from .selection import PassageCandidate, PassageQuestion, SelectionConfig, select_passage
from .simulate import SimulationConfig, SimulationResult, sigmoid, simulate
from .skills import SKILLS

POLICIES = ("random", "legacy_adaptive", "prediction_core_v1")


def compare_passage_policies(
    *,
    n_users: int = 200,
    n_passages: int = 100,
    rounds: int = 16,
    seed: int = 42,
    learning_rate: float = 0.01,
    config: SelectionConfig = SelectionConfig(),
) -> dict[str, pd.DataFrame]:
    """정책별 온라인 예측을 반환한다. 한 라운드는 서로 다른 스킬의 문항 3개다."""
    if n_users < 1 or not 1 <= rounds <= n_passages:
        raise ValueError("n_users must be positive and rounds must be between 1 and n_passages")
    if not np.isfinite(learning_rate) or learning_rate < 0:
        raise ValueError("learning_rate must be finite and nonnegative")

    source = simulate(
        SimulationConfig(
            n_users=n_users, n_items=3 * n_passages, min_attempts=3 * rounds,
            max_attempts=3 * rounds, seed=seed, learning_rate=0.0,
        )
    )
    # 기존 IRT 표본의 난이도를 유지하고, 지문마다 서로 다른 스킬 3개를 순환 배정한다.
    bank = []
    for index in range(n_passages):
        skills = [s for i, s in enumerate(SKILLS) if i != index % len(SKILLS)]
        item_ids = source.items["item_id"].iloc[3 * index:3 * (index + 1)]
        questions = tuple(PassageQuestion(item_id, skill) for item_id, skill in zip(item_ids, skills))
        bank.append(PassageCandidate(f"p{index:04d}", questions))
    items = source.items.assign(skill=[q.skill for candidate in bank for q in candidate.questions])

    starts = source.attempts.groupby("user_id", sort=False).cumcount() % 3 == 0
    schedule = list(source.attempts.loc[starts, ["user_id", "timestamp"]].itertuples(index=False, name=None))
    response_noise = np.random.default_rng([seed, 2]).random((len(schedule), 3))
    return {
        policy: _run_policy(
            policy, source, items, bank, schedule, response_noise, seed, learning_rate, config,
        )
        for policy in POLICIES
    }


def _run_policy(
    policy: str,
    source: SimulationResult,
    items: pd.DataFrame,
    bank: list[PassageCandidate],
    schedule: list,
    response_noise: np.ndarray,
    seed: int,
    learning_rate: float,
    config: SelectionConfig,
) -> pd.DataFrame:
    model = EloModel()
    model.register_users(source.users)
    model.register_items(items)
    theta = {(row.user_id, row.skill): row.theta_initial for row in source.user_skills.itertuples(index=False)}
    difficulty = dict(zip(items["item_id"], items["b"]))
    user_ids = source.users["user_id"]
    counts = {user: dict.fromkeys(SKILLS, 0) for user in user_ids}
    seen_passages: dict[str, set[str]] = {user: set() for user in user_ids}
    seen_items: dict[str, set[str]] = {user: set() for user in user_ids}
    random_choices = np.random.default_rng([seed, 3])
    tie_rng = np.random.default_rng([seed, 1])
    item_ids = items["item_id"].tolist()
    tie_orders = {
        user: {item_ids[index]: rank for rank, index in enumerate(tie_rng.permutation(len(item_ids)))}
        for user in user_ids
    } if policy == "legacy_adaptive" else {}

    rows = []
    for (user, timestamp), noise in zip(schedule, response_noise):
        if policy == "prediction_core_v1":
            result = select_passage(
                model, user, bank, seen_passage_ids=seen_passages[user], seen_item_ids=seen_items[user],
                skill_attempts=counts[user], config=config,
            )
            candidate = result.passage
            if candidate is None:
                raise RuntimeError("synthetic passage bank exhausted before the final round")
        else:
            available = [p for p in bank if p.passage_id not in seen_passages[user]]
            if policy == "random":
                candidate = available[random_choices.integers(len(available))]
            else:
                # 기존 규칙의 가장 가까운 개별 문항을 찾고 해당 지문 전체를 선택한다.
                candidate = min(available, key=lambda p: min(
                    (abs(model.predict(user, q.item_id) - config.target_p), tie_orders[user][q.item_id])
                    for q in p.questions
                ))
        seen_passages[user].add(candidate.passage_id)
        n_prior = sum(counts[user].values())
        for index, (question, draw) in enumerate(zip(candidate.questions, noise)):
            key = (user, question.skill)
            correct = bool(draw < sigmoid(theta[key] - difficulty[question.item_id]))
            predicted = model.update(user, question.item_id, correct)
            rows.append((
                user, timestamp, candidate.passage_id, question.item_id, question.skill, correct, predicted,
                n_prior + index,
            ))
            theta[key] += learning_rate
            counts[user][question.skill] += 1
            seen_items[user].add(question.item_id)
    return pd.DataFrame(
        rows, columns=["user_id", "timestamp", "passage_id", "item_id", "skill", "is_correct", "p_pred", "n_prior"],
    )


def summarize_policy(attempts: pd.DataFrame, config: SelectionConfig = SelectionConfig()) -> dict[str, float]:
    y, p = attempts["is_correct"], attempts["p_pred"]
    by_skill = pd.crosstab(attempts["user_id"], attempts["skill"]).reindex(columns=SKILLS, fill_value=0)
    coverage_gap = (by_skill.max(axis=1) - by_skill.min(axis=1)) / by_skill.sum(axis=1)
    return {
        **score(y, p),
        "accuracy": float(y.mean()),
        "cold_accuracy": float(y[attempts["n_prior"] < config.cold_start_attempts].mean()),
        "target_mae": float((p - config.target_p).abs().mean()),
        "coverage_gap": float(coverage_gap.mean()),
    }
