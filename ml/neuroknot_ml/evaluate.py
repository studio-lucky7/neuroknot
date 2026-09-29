"""시간 순서대로 "예측 먼저 → 결과 보고 갱신" 방식의 온라인 평가.

실제 서비스와 똑같이, 각 풀이 시점에는 그 이전 기록만 보고 예측한다.
"""

from __future__ import annotations

from typing import Protocol

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

_EPS = 1e-6


class Predictor(Protocol):
    def predict(self, user_id: str, item_id: str) -> float: ...

    def update(self, user_id: str, item_id: str, is_correct: bool) -> float: ...


def run_online(model: Predictor, attempts: pd.DataFrame) -> pd.DataFrame:
    """attempts를 timestamp 순으로 돌며 예측 후 갱신한다.

    반환값은 attempts에 두 컬럼을 붙인 사본이다.
    - p_pred: 그 풀이 직전에 모델이 낸 정답 확률
    - n_prior: 그 유저가 그 전에 푼 문제 수 (콜드스타트 구간 분석용)
    """
    df = attempts.sort_values("timestamp", kind="stable").reset_index(drop=True)
    preds = np.empty(len(df))
    for i, (user_id, item_id, correct) in enumerate(zip(df["user_id"], df["item_id"], df["is_correct"])):
        preds[i] = model.predict(user_id, item_id)
        model.update(user_id, item_id, bool(correct))
    out = df.copy()
    out["p_pred"] = preds
    out["n_prior"] = df.groupby("user_id").cumcount()
    return out


def score(y_true, p_pred) -> dict[str, float]:
    """AUC, log loss, Brier score. 한 클래스만 있으면 AUC는 NaN."""
    y = np.asarray(y_true, dtype=int)
    p = np.clip(np.asarray(p_pred, dtype=float), _EPS, 1 - _EPS)
    auc = roc_auc_score(y, p) if len(np.unique(y)) == 2 else float("nan")
    return {
        "n": int(len(y)),
        "auc": float(auc),
        "log_loss": float(log_loss(y, p, labels=[0, 1])),
        "brier": float(brier_score_loss(y, p)),
    }


def theta_recovery(model, user_skills: pd.DataFrame) -> dict[str, float]:
    """시뮬레이터의 진짜 θ와 모델 추정치의 Spearman 상관.

    user_skills는 SimulationResult.user_skills (user_id, skill, theta_final).
    학습 효과가 있으면 실력이 변하므로 평가가 끝난 시점의 θ(theta_final)와 비교한다.
    - skill: (유저, 스킬) 단위 θ_skill vs 모델의 스킬별 추정치
    - overall: 유저 단위 스킬 평균 θ vs 모델의 전체 추정치
    모델에 estimate_theta가 없으면 NaN.
    """
    if not hasattr(model, "estimate_theta"):
        return {"spearman_skill": float("nan"), "spearman_overall": float("nan")}
    est_skill = [model.estimate_theta(u, s) for u, s in zip(user_skills["user_id"], user_skills["skill"])]
    overall_true = user_skills.groupby("user_id", sort=True)["theta_final"].mean()
    est_overall = [model.estimate_theta(u) for u in overall_true.index]
    return {
        "spearman_skill": float(spearmanr(user_skills["theta_final"], est_skill)[0]),
        "spearman_overall": float(spearmanr(overall_true.to_numpy(), est_overall)[0]),
    }
