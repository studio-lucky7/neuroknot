"""IRT(1PL) 기반 가상 풀이 기록 시뮬레이터.

진짜 실력(θ)을 알고 있는 가상 데이터를 만들어, 예측 모델이 그 실력을
얼마나 잘 복원하는지 검증하는 데 쓴다.

생성 규칙
- 유저: 전체 능력 θ ~ N(0, 1), 스킬별 θ_skill = θ + N(0, skill_sd)
- 학습 효과(옵션): 한 스킬을 한 번 풀 때마다 그 스킬의 θ_skill이 learning_rate만큼 오른다
- 온보딩 레벨: 자가평가라서 θ에 노이즈를 더한 값을 4단계로 자른다
- 문제: 스킬 태그 1개, 난이도 b ~ N(0, item_sd), b를 별 1~5개로 매핑
- 정답 확률: P = sigmoid(θ_skill - b)
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .skills import SKILLS

ONBOARDING_LEVELS: tuple[str, ...] = ("warming_up", "cruising", "high_speed", "autonomous")

# 자가평가 점수(θ + 노이즈)를 온보딩 레벨로 자르는 경계값. N(0,1)의 사분위 근처.
_LEVEL_CUTS = (-0.67, 0.0, 0.67)
# 난이도 b를 별 개수로 자르는 경계값. b < -1.2 → 별 1개, ..., b >= 1.2 → 별 5개.
_STAR_CUTS = (-1.2, -0.4, 0.4, 1.2)


def sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def difficulty_to_stars(b) -> np.ndarray:
    """난이도 b(로짓 척도)를 별 1~5개로 매핑한다."""
    return np.digitize(b, _STAR_CUTS) + 1


def self_report_to_level(score) -> np.ndarray:
    """자가평가 점수를 온보딩 레벨 문자열로 매핑한다."""
    idx = np.digitize(score, _LEVEL_CUTS)
    return np.asarray(ONBOARDING_LEVELS, dtype=object)[idx]


@dataclass(frozen=True)
class SimulationConfig:
    n_users: int = 200
    n_items: int = 300
    min_attempts: int = 20  # 유저별 풀이 수는 [min_attempts, max_attempts]에서 균등하게 뽑는다
    max_attempts: int = 80
    skill_sd: float = 0.5  # 스킬별 편차의 표준편차
    item_sd: float = 1.0  # 난이도 b의 표준편차
    onboarding_noise_sd: float = 0.8  # 자가평가 노이즈의 표준편차
    learning_rate: float = 0.01  # 풀이 1회당 해당 스킬 θ 상승량. 0이면 학습 효과 없음
    seed: int = 42
    start: str = "2026-01-01"


@dataclass
class SimulationResult:
    config: SimulationConfig
    users: pd.DataFrame  # user_id, onboarding_level, theta
    user_skills: pd.DataFrame  # user_id, skill, theta_initial, theta_final
    items: pd.DataFrame  # item_id, skill, b, difficulty
    attempts: pd.DataFrame  # user_id, item_id, skill, difficulty, is_correct, timestamp


def simulate(config: SimulationConfig | None = None) -> SimulationResult:
    """가상 유저/문제/풀이 기록을 만든다. 같은 config(seed 포함)면 결과가 같다."""
    cfg = config or SimulationConfig()
    if cfg.min_attempts > cfg.max_attempts:
        raise ValueError("min_attempts must be <= max_attempts")
    rng = np.random.default_rng(cfg.seed)
    n_skills = len(SKILLS)

    # 유저
    user_ids = np.array([f"u{i:04d}" for i in range(cfg.n_users)], dtype=object)
    theta = rng.normal(0.0, 1.0, cfg.n_users)
    skill_theta0 = theta[:, None] + rng.normal(0.0, cfg.skill_sd, (cfg.n_users, n_skills))
    self_report = theta + rng.normal(0.0, cfg.onboarding_noise_sd, cfg.n_users)
    levels = self_report_to_level(self_report)

    # 문제
    item_ids = np.array([f"q{i:04d}" for i in range(cfg.n_items)], dtype=object)
    item_skill = rng.integers(0, n_skills, cfg.n_items)
    b = rng.normal(0.0, cfg.item_sd, cfg.n_items)
    stars = difficulty_to_stars(b)

    # 풀이 기록
    start = pd.Timestamp(cfg.start)
    skill_theta_final = skill_theta0.copy()
    cols: dict[str, list] = {k: [] for k in ("user_id", "item_id", "skill", "difficulty", "is_correct", "timestamp")}
    for u in range(cfg.n_users):
        n = min(int(rng.integers(cfg.min_attempts, cfg.max_attempts + 1)), cfg.n_items)
        order = rng.choice(cfg.n_items, size=n, replace=False)
        # 문제 사이 간격은 평균 90초, 10% 확률로 0.5~2일 쉬었다가 다음 세션을 시작한다
        gaps = rng.exponential(90.0, n)
        gaps += (rng.random(n) < 0.1) * rng.uniform(0.5, 2.0, n) * 86400.0
        offsets = rng.uniform(0.0, 14.0) * 86400.0 + np.cumsum(gaps)
        cur = skill_theta0[u].copy()
        for i, offset in zip(order, offsets):
            s = item_skill[i]
            correct = rng.random() < sigmoid(cur[s] - b[i])
            cols["user_id"].append(user_ids[u])
            cols["item_id"].append(item_ids[i])
            cols["skill"].append(SKILLS[s])
            cols["difficulty"].append(int(stars[i]))
            cols["is_correct"].append(bool(correct))
            cols["timestamp"].append(start + pd.Timedelta(seconds=float(offset)))
            cur[s] += cfg.learning_rate
        skill_theta_final[u] = cur

    attempts = pd.DataFrame(cols).sort_values("timestamp", kind="stable").reset_index(drop=True)
    users = pd.DataFrame({"user_id": user_ids, "onboarding_level": levels, "theta": theta})
    user_skills = pd.DataFrame(
        {
            "user_id": np.repeat(user_ids, n_skills),
            "skill": np.tile(np.asarray(SKILLS, dtype=object), cfg.n_users),
            "theta_initial": skill_theta0.ravel(),
            "theta_final": skill_theta_final.ravel(),
        }
    )
    items = pd.DataFrame(
        {
            "item_id": item_ids,
            "skill": np.asarray(SKILLS, dtype=object)[item_skill],
            "b": b,
            "difficulty": stars,
        }
    )
    return SimulationResult(cfg, users, user_skills, items, attempts)
