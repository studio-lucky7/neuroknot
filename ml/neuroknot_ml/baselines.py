"""Elo와 비교할 단순 baseline 모델.

EloModel과 같은 predict(user_id, item_id) / update(user_id, item_id, is_correct)
인터페이스를 따른다. 문제 정보(스킬, 난이도)는 쓰지 않는다.
"""

from __future__ import annotations

import math


class GlobalMeanBaseline:
    """지금까지의 전체 평균 정답률을 모든 예측에 쓴다.

    첫 예측이 0/1로 튀지 않도록 0.5에서 prior_count만큼의 가상 풀이로 시작한다.
    """

    def __init__(self, prior_mean: float = 0.5, prior_count: float = 1.0) -> None:
        self._correct = prior_mean * prior_count
        self._n = prior_count

    def predict(self, user_id: str, item_id: str) -> float:
        return self._correct / self._n

    def update(self, user_id: str, item_id: str, is_correct: bool) -> float:
        p = self.predict(user_id, item_id)
        self._correct += float(is_correct)
        self._n += 1
        return p


class UserMeanBaseline:
    """유저별 누적 정답률. 풀이가 적을 땐 전체 평균 쪽으로 당긴다.

    P = (유저 정답 수 + smoothing · 전체 평균) / (유저 풀이 수 + smoothing)
    """

    def __init__(self, smoothing: float = 1.0) -> None:
        self.smoothing = smoothing
        self._global = GlobalMeanBaseline()
        self._stats: dict[str, list[float]] = {}  # user -> [정답 수, 풀이 수]

    def predict(self, user_id: str, item_id: str) -> float:
        correct, n = self._stats.get(user_id, (0.0, 0.0))
        prior = self._global.predict(user_id, item_id)
        return (correct + self.smoothing * prior) / (n + self.smoothing)

    def update(self, user_id: str, item_id: str, is_correct: bool) -> float:
        p = self.predict(user_id, item_id)
        stats = self._stats.setdefault(user_id, [0.0, 0.0])
        stats[0] += float(is_correct)
        stats[1] += 1
        self._global.update(user_id, item_id, is_correct)
        return p

    def estimate_theta(self, user_id: str, skill: str | None = None) -> float:
        """정답률의 로짓. 스킬 구분이 없으므로 skill은 무시한다."""
        correct, n = self._stats.get(user_id, (0.0, 0.0))
        p = (correct + self.smoothing * self._global.predict(user_id, "")) / (n + self.smoothing)
        p = min(max(p, 1e-6), 1 - 1e-6)
        return math.log(p / (1 - p))


class OracleModel:
    """시뮬레이터의 진짜 확률 P = sigmoid(θ_skill - b)로 예측하는 상한선.

    진짜 θ와 b를 알고 있으므로 어떤 모델도 기대값 기준으로 이보다 나을 수 없다.
    학습 효과도 시뮬레이터와 똑같이 따라간다 (풀 때마다 그 스킬 θ += learning_rate).
    """

    def __init__(self, user_skills, items, learning_rate: float = 0.0) -> None:
        self.learning_rate = learning_rate
        self._theta = {
            (u, s): float(t)
            for u, s, t in zip(user_skills["user_id"], user_skills["skill"], user_skills["theta_initial"])
        }
        self._item = {i: (s, float(b)) for i, s, b in zip(items["item_id"], items["skill"], items["b"])}

    @classmethod
    def from_simulation(cls, sim) -> "OracleModel":
        return cls(sim.user_skills, sim.items, sim.config.learning_rate)

    def predict(self, user_id: str, item_id: str) -> float:
        skill, b = self._item[item_id]
        return 1.0 / (1.0 + math.exp(-(self._theta[(user_id, skill)] - b)))

    def update(self, user_id: str, item_id: str, is_correct: bool) -> float:
        p = self.predict(user_id, item_id)
        self._theta[(user_id, self._item[item_id][0])] += self.learning_rate
        return p

    def estimate_theta(self, user_id: str, skill: str | None = None) -> float:
        if skill is not None:
            return self._theta[(user_id, skill)]
        values = [t for (u, _), t in self._theta.items() if u == user_id]
        return sum(values) / len(values)
