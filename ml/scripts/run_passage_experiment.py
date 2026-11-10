"""동일한 합성 지문으로 Random, Legacy Adaptive, Prediction Core V1을 비교한다."""

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuroknot_ml.passage_experiment import compare_passage_policies, summarize_policy  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--users", type=int, default=200)
    parser.add_argument("--passages", type=int, default=100)
    parser.add_argument("--rounds", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=0.01)
    args = parser.parse_args()
    runs = compare_passage_policies(
        n_users=args.users, n_passages=args.passages, rounds=args.rounds,
        seed=args.seed, learning_rate=args.learning_rate,
    )
    print(f"seed={args.seed}, users={args.users}, passages={args.passages}, rounds={args.rounds}, "
          f"learning_rate={args.learning_rate}")
    summary = pd.DataFrame.from_dict({name: summarize_policy(log) for name, log in runs.items()}, orient="index")
    summary["n"] = summary["n"].astype(int)
    print(summary.round(4).to_string())
    print("\ntarget_mae: |p_pred - 0.7| 평균. coverage_gap: 사용자별 최다·최소 스킬 풀이 비율 차이의 평균.")


if __name__ == "__main__":
    main()
