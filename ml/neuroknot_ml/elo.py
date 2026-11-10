"""유저-스킬별 실력과 문제 난이도를 동시에 갱신하는 Elo 모델.

로짓 척도에서 동작하므로 시뮬레이터의 θ, b와 바로 비교할 수 있다.
    P(정답) = sigmoid(θ[user, skill] - b[item])
    θ ← θ + K_user(n) · (y - P)
    b ← b - K_item(n) · (y - P)
K는 풀이 수 n이 적을 때 크고 점점 줄어든다 (콜드스타트 때 빠르게 보정).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from math import isfinite

import numpy as np
import pandas as pd

# 온보딩 레벨별 초기 실력 prior. TODO(Day 0): 임시값, 실데이터가 쌓이면 재추정한다.
DEFAULT_LEVEL_PRIOR: dict[str, float] = {
    "warming_up": -1.0,
    "cruising": -0.3,
    "high_speed": 0.3,
    "autonomous": 1.0,
}

# Prediction에서 사용하는 별 개수별 초기 난이도 prior. TODO(Day 0): 실데이터로 재추정한다.
DEFAULT_STAR_PRIOR: dict[int, float] = {1: -1.6, 2: -0.8, 3: 0.0, 4: 0.8, 5: 1.6}


@dataclass(frozen=True)
class KSchedule:
    """K(n) = max(k_min, k0 / (1 + decay · n)). n은 지금까지의 갱신 횟수."""

    k0: float
    decay: float
    k_min: float

    def __call__(self, n: int) -> float:
        return max(self.k_min, self.k0 / (1.0 + self.decay * n))


DEFAULT_USER_K = KSchedule(k0=0.8, decay=0.1, k_min=0.1)
DEFAULT_ITEM_K = KSchedule(k0=0.4, decay=0.1, k_min=0.05)
_STATE_VERSION = 1


def _state_object(value: object, path: str, *fields: str) -> dict:
    if not isinstance(value, dict) or any(not isinstance(key, str) for key in value):
        raise ValueError(f"{path} must be an object with string keys")
    if fields:
        expected = set(fields)
        if value.keys() != expected:
            missing = sorted(expected - value.keys())
            extra = sorted(value.keys() - expected)
            raise ValueError(f"{path} has missing fields {missing} and unexpected fields {extra}")
    return value


def _state_number(value: object, path: str) -> float:
    if isinstance(value, (int, float, np.integer, np.floating)) and not isinstance(value, bool):
        try:
            number = float(value)
        except OverflowError:
            pass
        else:
            if isfinite(number):
                return number
    raise ValueError(f"{path} must be a finite number")


def _state_attempts(value: object, path: str) -> int:
    if type(value) is not int or value < 0:
        raise ValueError(f"{path} must be a nonnegative integer")
    _state_number(value, path)
    return value


def _state_schedule(value: object, path: str) -> dict[str, float]:
    fields = _state_object(value, path, "k0", "decay", "k_min")
    params = {key: _state_number(number, f"{path}.{key}") for key, number in fields.items()}
    for key, number in params.items():
        if number < 0:
            raise ValueError(f"{path}.{key} must be nonnegative")
    return params


class EloModel:
    """유저-스킬별 Elo + 문제 난이도 Elo.

    사용 전에 register_item으로 문제의 스킬(과 별 개수)을 알려줘야 한다.
    유저는 register_user로 온보딩 레벨을 알려주면 그 prior에서 시작하고,
    등록하지 않은 유저는 0.0에서 시작한다.
    """

    def __init__(
        self,
        level_prior: Mapping[str, float] | None = None,
        star_prior: Mapping[int, float] | None = None,
        user_k: KSchedule = DEFAULT_USER_K,
        item_k: KSchedule = DEFAULT_ITEM_K,
    ) -> None:
        self.level_prior = dict(DEFAULT_LEVEL_PRIOR if level_prior is None else level_prior)
        self.star_prior = dict(DEFAULT_STAR_PRIOR if star_prior is None else star_prior)
        self.user_k = user_k
        self.item_k = item_k
        self._user_prior: dict[str, float] = {}
        self._item_skill: dict[str, str] = {}
        self._user_state: dict[tuple[str, str], list] = {}  # (user, skill) -> [θ, n]
        self._item_state: dict[str, list] = {}  # item -> [b, n]

    # 등록
    def register_user(self, user_id: str, onboarding_level: str | None = None) -> None:
        self._user_prior[user_id] = self.level_prior.get(onboarding_level, 0.0)

    def register_item(self, item_id: str, skill: str, difficulty: int | None = None) -> None:
        self._item_skill[item_id] = skill
        if item_id not in self._item_state:
            self._item_state[item_id] = [self.star_prior.get(difficulty, 0.0), 0]

    def register_users(self, users: pd.DataFrame) -> None:
        """user_id, onboarding_level 컬럼을 가진 DataFrame으로 한꺼번에 등록한다."""
        for user_id, level in zip(users["user_id"], users["onboarding_level"]):
            self.register_user(user_id, level)

    def register_items(self, items: pd.DataFrame) -> None:
        """item_id, skill, (선택) difficulty 컬럼을 가진 DataFrame으로 한꺼번에 등록한다."""
        stars = items["difficulty"] if "difficulty" in items else [None] * len(items)
        for item_id, skill, star in zip(items["item_id"], items["skill"], stars):
            self.register_item(item_id, skill, None if pd.isna(star) else int(star))

    # 상태 조회
    def _item(self, item_id: str) -> list:
        if item_id not in self._item_state:
            raise KeyError(f"unregistered item: {item_id!r} (call register_item first)")
        return self._item_state[item_id]

    def _user(self, user_id: str, skill: str) -> list:
        key = (user_id, skill)
        if key not in self._user_state:
            self._user_state[key] = [self._user_prior.get(user_id, 0.0), 0]
        return self._user_state[key]

    def user_rating(self, user_id: str, skill: str) -> float:
        key = (user_id, skill)
        if key in self._user_state:
            return self._user_state[key][0]
        return self._user_prior.get(user_id, 0.0)

    def item_difficulty(self, item_id: str) -> float:
        return self._item(item_id)[0]

    def estimate_theta(self, user_id: str, skill: str | None = None) -> float:
        """지정 스킬의 θ, 등록된 스킬의 평균, 또는 스킬이 없을 때 초기 prior."""
        if skill is not None:
            return self.user_rating(user_id, skill)
        skills = sorted(set(self._item_skill.values()))
        if not skills:
            return self._user_prior.get(user_id, 0.0)
        return float(np.mean([self.user_rating(user_id, s) for s in skills]))

    # 예측/갱신
    def predict(self, user_id: str, item_id: str) -> float:
        b = self._item(item_id)[0]
        theta = self.user_rating(user_id, self._item_skill[item_id])
        return float(1.0 / (1.0 + np.exp(-(theta - b))))

    def update(self, user_id: str, item_id: str, is_correct: bool) -> float:
        """결과를 반영하고, 갱신 전 예측 확률을 돌려준다."""
        p = self.predict(user_id, item_id)
        err = float(is_correct) - p
        user = self._user(user_id, self._item_skill[item_id])
        item = self._item(item_id)
        user[0] += self.user_k(user[1]) * err
        item[0] -= self.item_k(item[1]) * err
        user[1] += 1
        item[1] += 1
        return p

    def to_state(self) -> dict:
        """설정과 학습 상태를 json.dumps에 전달할 수 있는 독립적인 스냅샷으로 내보낸다."""
        user_skills: dict[str, dict] = {}
        for (user_id, skill), (theta, attempts) in self._user_state.items():
            user_skills.setdefault(user_id, {})[skill] = {
                "theta": _state_number(theta, f"user_skills.{user_id}.{skill}.theta"),
                "attempts": attempts,
            }
        return {
            "version": _STATE_VERSION,
            "config": {
                "level_prior": {
                    key: _state_number(value, f"config.level_prior.{key}") for key, value in self.level_prior.items()
                },
                "star_prior": {
                    str(key): _state_number(value, f"config.star_prior.{key}") for key, value in self.star_prior.items()
                },
                "user_k": _state_schedule(asdict(self.user_k), "config.user_k"),
                "item_k": _state_schedule(asdict(self.item_k), "config.item_k"),
            },
            "user_prior": {key: _state_number(value, f"user_prior.{key}") for key, value in self._user_prior.items()},
            "user_skills": user_skills,
            "items": {
                item_id: {
                    "skill": self._item_skill[item_id],
                    "difficulty": _state_number(difficulty, f"items.{item_id}.difficulty"),
                    "attempts": attempts,
                }
                for item_id, (difficulty, attempts) in self._item_state.items()
            },
        }

    @classmethod
    def from_state(cls, state: object) -> EloModel:
        """to_state 또는 json.loads의 스냅샷으로 새 모델을 만든다.

        버전, 필드 구조 또는 값이 유효하지 않으면 필드 경로를 포함한 ValueError를 발생시킨다.
        """
        data = _state_object(state, "state", "version", "config", "user_prior", "user_skills", "items")
        if type(data["version"]) is not int or data["version"] != _STATE_VERSION:
            raise ValueError(f"unsupported state.version; expected integer {_STATE_VERSION}")

        config = _state_object(data["config"], "config", "level_prior", "star_prior", "user_k", "item_k")
        levels = _state_object(config["level_prior"], "config.level_prior")
        stars = _state_object(config["star_prior"], "config.star_prior")
        star_prior = {}
        for key, value in stars.items():
            try:
                star = int(key)
            except ValueError:
                raise ValueError("config.star_prior keys must be canonical integer strings") from None
            if str(star) != key:
                raise ValueError("config.star_prior keys must be canonical integer strings")
            star_prior[star] = _state_number(value, f"config.star_prior.{key}")
        model = cls(
            level_prior={key: _state_number(value, f"config.level_prior.{key}") for key, value in levels.items()},
            star_prior=star_prior,
            user_k=KSchedule(**_state_schedule(config["user_k"], "config.user_k")),
            item_k=KSchedule(**_state_schedule(config["item_k"], "config.item_k")),
        )
        for user_id, prior in _state_object(data["user_prior"], "user_prior").items():
            model._user_prior[user_id] = _state_number(prior, f"user_prior.{user_id}")
        for user_id, skills in _state_object(data["user_skills"], "user_skills").items():
            for skill, record in _state_object(skills, f"user_skills.{user_id}").items():
                path = f"user_skills.{user_id}.{skill}"
                fields = _state_object(record, path, "theta", "attempts")
                model._user_state[user_id, skill] = [
                    _state_number(fields["theta"], f"{path}.theta"),
                    _state_attempts(fields["attempts"], f"{path}.attempts"),
                ]
        for item_id, record in _state_object(data["items"], "items").items():
            path = f"items.{item_id}"
            fields = _state_object(record, path, "skill", "difficulty", "attempts")
            if not isinstance(fields["skill"], str):
                raise ValueError(f"{path}.skill must be a string")
            model._item_skill[item_id] = fields["skill"]
            model._item_state[item_id] = [
                _state_number(fields["difficulty"], f"{path}.difficulty"),
                _state_attempts(fields["attempts"], f"{path}.attempts"),
            ]
        return model
