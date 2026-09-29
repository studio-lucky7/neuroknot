"""가상 데이터로 모델별 예측 성능과 θ 복원력을 비교한다.

    python scripts/run_experiment.py [--seed 42] [--users 200] [--items 300]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuroknot_ml.baselines import GlobalMeanBaseline, OracleModel, UserMeanBaseline  # noqa: E402
from neuroknot_ml.elo import EloModel  # noqa: E402
from neuroknot_ml.evaluate import run_online, score, theta_recovery  # noqa: E402
from neuroknot_ml.simulate import SimulationConfig, simulate  # noqa: E402

COLD_START_N = 10  # 유저별 첫 N문제를 콜드스타트 구간으로 본다


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--items", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    args = parser.parse_args()

    sim = simulate(
        SimulationConfig(n_users=args.users, n_items=args.items, learning_rate=args.learning_rate, seed=args.seed)
    )
    attempts = sim.attempts

    elo = EloModel()
    elo.register_users(sim.users)
    elo.register_items(sim.items)
    # prior의 효과를 보기 위한 비교군: 온보딩 레벨/별 개수를 무시하고 모두 0에서 시작
    elo_no_prior = EloModel(level_prior={}, star_prior={})
    elo_no_prior.register_users(sim.users)
    elo_no_prior.register_items(sim.items)

    models = {
        "oracle": OracleModel.from_simulation(sim),  # 진짜 확률로 예측하는 상한선
        "global_mean": GlobalMeanBaseline(),
        "user_mean": UserMeanBaseline(),
        "elo_no_prior": elo_no_prior,
        "elo": elo,
    }

    rows = []
    for name, model in models.items():
        pred = run_online(model, attempts)
        cold = pred[pred["n_prior"] < COLD_START_N]
        overall, cold_s = score(pred["is_correct"], pred["p_pred"]), score(cold["is_correct"], cold["p_pred"])
        rec = theta_recovery(model, sim.user_skills)
        rows.append(
            {
                "model": name,
                "auc": overall["auc"],
                "log_loss": overall["log_loss"],
                "brier": overall["brier"],
                f"cold_auc(<{COLD_START_N})": cold_s["auc"],
                f"cold_logloss(<{COLD_START_N})": cold_s["log_loss"],
                "rho_theta_skill": rec["spearman_skill"],
                "rho_theta_user": rec["spearman_overall"],
            }
        )

    print(f"== 데이터: 유저 {args.users}명, 문제 {args.items}개, 풀이 {len(attempts)}건, "
          f"정답률 {attempts['is_correct'].mean():.3f}, seed={args.seed}, learning_rate={args.learning_rate}")
    print(f"   콜드스타트 구간(유저별 첫 {COLD_START_N}문제): {(pred['n_prior'] < COLD_START_N).sum()}건\n")
    table = pd.DataFrame(rows).set_index("model")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(table.round(4).to_string(na_rep="-"))

    est_b = [elo.item_difficulty(i) for i in sim.items["item_id"]]
    print(f"\n== Elo 문제 난이도 복원: Spearman(b, 추정 b) = {spearmanr(sim.items['b'], est_b)[0]:.4f}")
    print("   (rho_theta_*: 진짜 θ와 추정치의 Spearman 상관. global_mean은 유저 추정치가 없어 '-')")


if __name__ == "__main__":
    main()
