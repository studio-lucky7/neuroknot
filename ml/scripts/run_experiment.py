"""가상 데이터로 모델별 예측 성능, 보정도, θ 복원력을 비교한다.

    python scripts/run_experiment.py [--seed 42] [--users 200] [--items 300]

신뢰도 그래프는 ml/results/reliability_<selection>.png로 저장한다.
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
from neuroknot_ml.evaluate import (  # noqa: E402
    calibration_in_the_large,
    reliability_table,
    run_online,
    score,
    theta_recovery,
)
from neuroknot_ml.simulate import SimulationConfig, simulate  # noqa: E402

COLD_START_N = 10  # 유저별 첫 N문제를 콜드스타트 구간으로 본다
RESULTS_DIR = Path(__file__).resolve().parents[1] / "results"
MIN_BIN_COUNT = 20  # 신뢰도 그래프에서 풀이가 이보다 적은 구간은 노이즈라 점을 찍지 않는다


def make_elo(sim, **kwargs) -> EloModel:
    model = EloModel(**kwargs)
    model.register_users(sim.users)
    model.register_items(sim.items)
    return model


def run_condition(sim) -> dict[str, pd.DataFrame]:
    """한 시뮬레이션 조건에 대해 모델별 결과표를 출력하고, 모델별 온라인 예측을 돌려준다."""
    attempts = sim.attempts
    elo = make_elo(sim)
    models = {
        "oracle": OracleModel.from_simulation(sim),  # 진짜 확률로 예측하는 상한선
        "global_mean": GlobalMeanBaseline(),
        "user_mean": UserMeanBaseline(),
        # prior의 효과를 보기 위한 비교군: 온보딩 레벨/별 개수를 무시하고 모두 0에서 시작
        "elo_no_prior": make_elo(sim, level_prior={}, star_prior={}),
        "elo": elo,
    }

    rows, preds = [], {}
    for name, model in models.items():
        pred = preds[name] = run_online(model, attempts)
        cold = pred[pred["n_prior"] < COLD_START_N]
        overall, cold_s = score(pred["is_correct"], pred["p_pred"]), score(cold["is_correct"], cold["p_pred"])
        rec = theta_recovery(model, sim.user_skills)
        rows.append(
            {
                "model": name,
                "auc": overall["auc"],
                "log_loss": overall["log_loss"],
                "brier": overall["brier"],
                "ece": overall["ece"],
                f"cold_auc(<{COLD_START_N})": cold_s["auc"],
                f"cold_logloss(<{COLD_START_N})": cold_s["log_loss"],
                "rho_theta_skill": rec["spearman_skill"],
                "rho_theta_user": rec["spearman_overall"],
            }
        )

    cfg = sim.config
    user_acc = attempts.groupby("user_id")["is_correct"].mean()
    print(f"== selection={cfg.selection}: 유저 {cfg.n_users}명, 문제 {cfg.n_items}개, 풀이 {len(attempts)}건, "
          f"seed={cfg.seed}, learning_rate={cfg.learning_rate}")
    print(f"   정답률 {attempts['is_correct'].mean():.3f}, 유저별 정답률 표준편차 {user_acc.std():.3f}, "
          f"콜드스타트 구간(유저별 첫 {COLD_START_N}문제) {(pred['n_prior'] < COLD_START_N).sum()}건\n")
    table = pd.DataFrame(rows).set_index("model")
    with pd.option_context("display.width", 200, "display.max_columns", None):
        print(table.round(4).to_string(na_rep="-"))

    est_b = [elo.item_difficulty(i) for i in sim.items["item_id"]]
    print(f"\n   Elo 문제 난이도 복원: Spearman(b, 추정 b) = {spearmanr(sim.items['b'], est_b)[0]:.4f}\n")

    if cfg.selection == "adaptive":
        y, p = preds["elo"]["is_correct"], preds["elo"]["p_pred"]
        cal = calibration_in_the_large(y, p)
        print(f"== adaptive / elo 신뢰도 표 (평균 예측 {cal['mean_pred']:.4f} vs 실제 정답률 {cal['mean_actual']:.4f}, "
              f"차이 {cal['diff']:+.4f})")
        print(reliability_table(y, p).round(4).to_string(index=False, na_rep="-"))
        print()
    return preds


def plot_reliability(preds: dict[str, pd.DataFrame], selection: str, path: Path) -> None:
    """모델별 신뢰도 그래프(구간별 예측 평균 vs 실제 정답률)를 png로 저장한다."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(6.5, 6.5))
    ax.plot([0, 1], [0, 1], linestyle="--", color="gray", linewidth=1, label="perfect calibration")
    for name, pred in preds.items():
        table = reliability_table(pred["is_correct"], pred["p_pred"])
        table = table[table["count"] >= MIN_BIN_COUNT]
        ece = score(pred["is_correct"], pred["p_pred"])["ece"]
        ax.plot(table["mean_pred"], table["accuracy"], marker="o", label=f"{name} (ECE {ece:.3f})")
    ax.set(
        xlim=(0, 1),
        ylim=(0, 1),
        xlabel="mean predicted probability",
        ylabel="observed accuracy",
        title=f"Reliability diagram: selection={selection}\n(10 bins, bins with n < {MIN_BIN_COUNT} hidden)",
    )
    ax.set_aspect("equal")
    ax.grid(alpha=0.3)
    ax.legend(loc="upper left", fontsize=9)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=120)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--items", type=int, default=300)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    args = parser.parse_args()

    for selection in ("random", "adaptive"):
        cfg = SimulationConfig(
            n_users=args.users,
            n_items=args.items,
            learning_rate=args.learning_rate,
            seed=args.seed,
            selection=selection,
        )
        preds = run_condition(simulate(cfg))
        plot_reliability(preds, selection, RESULTS_DIR / f"reliability_{selection}.png")
    print("(ece: 예측 확률 구간 10개 기준 Expected Calibration Error. 0에 가까울수록 예측 확률 = 실제 정답률)")
    print("(rho_theta_*: 진짜 θ와 추정치의 Spearman 상관. global_mean은 유저 추정치가 없어 '-')")
    print(f"신뢰도 그래프 저장: {RESULTS_DIR}")


if __name__ == "__main__":
    main()
