"""기존 IRT 시뮬레이터에서 학습 이벤트를 만들고 사용자 JSON 리포트를 출력한다."""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from neuroknot_ml.learning_analytics import analyze_user  # noqa: E402
from neuroknot_ml.learning_history import CatalogItem, LearningHistory  # noqa: E402
from neuroknot_ml.simulate import SimulationConfig, simulate  # noqa: E402


def build_scenario(seed: int) -> tuple[list[CatalogItem], dict[str, str], list[dict]]:
    sim = simulate(SimulationConfig(n_users=4, n_items=12, min_attempts=8, max_attempts=8, seed=seed))
    items = [
        CatalogItem(row.item_id, "v1", row.skill, int(row.difficulty))
        for row in sim.items.itertuples(index=False)
    ]
    levels = dict(zip(sim.users["user_id"], sim.users["onboarding_level"]))
    rng = random.Random(seed)
    events = []
    for index, row in enumerate(sim.attempts.itertuples(index=False)):
        base = {
            "version": 1,
            "user_id": row.user_id,
            "exposure_id": f"x{index}",
            "occurred_at": row.timestamp.tz_localize("UTC").isoformat(timespec="microseconds").replace("+00:00", "Z"),
        }
        passage_id = f"p-{row.item_id}"
        events.append({
            **base, "type": "exposure", "event_id": f"e{index}", "passage_id": passage_id,
            "quiz_version": "v1", "item_ids": [row.item_id], "policy_version": "synthetic-irt",
        })
        first = {
            **base, "type": "submission", "event_id": f"a{index}", "submission_id": f"s{index}",
            "passage_id": passage_id, "item_id": row.item_id, "item_version": "v1",
            "skill": row.skill, "is_correct": bool(row.is_correct), "is_retry": False,
        }
        events.append(first)
        if not row.is_correct and rng.random() < 0.5:
            events.append({
                **first, "event_id": f"retry-{index}", "submission_id": f"retry-{index}", "is_retry": True,
                "is_correct": rng.random() < 0.7, "hint_used": True,
            })
        events.append({
            **base, "type": "completion", "event_id": f"c{index}",
            "status": "completed" if rng.random() < 0.8 else "abandoned",
        })
    return items, levels, events


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--user", default="u0000")
    parser.add_argument("--timezone", default="Asia/Seoul")
    args = parser.parse_args()
    if args.seed < 0:
        parser.error("--seed must be nonnegative")

    items, levels, events = build_scenario(args.seed)
    history = LearningHistory.replay(items, events, onboarding_levels=levels)
    report = analyze_user(history, args.user, as_of=events[-1]["occurred_at"], timezone_name=args.timezone)
    print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))


if __name__ == "__main__":
    main()
