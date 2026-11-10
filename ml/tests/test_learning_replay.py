import json

import pytest

from neuroknot_ml.elo import EloModel
from neuroknot_ml.learning_analytics import analyze_user
from neuroknot_ml.learning_history import LearningHistory
from neuroknot_ml.skills import SKILLS
from scripts.run_learning_analytics import build_scenario


@pytest.mark.parametrize("seed", [0, 7, 42])
def test_synthetic_logs_reproduce_shared_elo_and_reports_across_seeds(seed):
    items, levels, events = build_scenario(seed)
    assert (items, levels, events) == build_scenario(seed)
    online = LearningHistory(items, onboarding_levels=levels)
    for event in events:
        online.apply(event)

    replayed = LearningHistory.replay(
        items, json.loads(json.dumps(online.event_log(), allow_nan=False)), onboarding_levels=levels,
    )
    assert online.records == replayed.records
    reference = EloModel()
    for item in items:
        reference.register_item(item.item_id, item.skill, item.difficulty)
    for user_id, level in levels.items():
        reference.register_user(user_id, level)
    first_answers = [event for event in events if event["type"] == "submission" and not event["is_retry"]]
    traces = [record.attempt for record in replayed.records if record.attempt and record.attempt.elo_updated]
    assert len(first_answers) == len(traces) == 32
    assert len({event["item_id"] for event in first_answers}) < len(first_answers)
    for event, trace in zip(first_answers, traces, strict=True):
        user, item = event["user_id"], event["item_id"]
        assert trace.theta_before == reference.user_rating(user, event["skill"])
        assert trace.difficulty_before == reference.item_difficulty(item)
        assert trace.probability == reference.update(user, item, event["is_correct"])
        assert trace.theta_after == reference.user_rating(user, event["skill"])
        assert trace.difficulty_after == reference.item_difficulty(item)
    for item in items:
        assert replayed.item_difficulty(item.item_id) == reference.item_difficulty(item.item_id)

    cutoff = events[-1]["occurred_at"]
    for user in levels:
        report = analyze_user(replayed, user, as_of=cutoff)
        assert report == analyze_user(online, user, as_of=cutoff)
        assert report["summary"]["first_attempts"] == report["summary"]["exposures"] == 8
        assert report["summary"]["correct_first_attempts"] == sum(
            event["is_correct"] for event in first_answers if event["user_id"] == user
        )
        assert report["summary"]["retries"] == sum(
            event["is_retry"] for event in events if event["type"] == "submission" and event["user_id"] == user
        )
        for skill in SKILLS:
            assert replayed.user_rating(user, skill) == reference.user_rating(user, skill)
        assert json.loads(json.dumps(report, allow_nan=False)) == report

    prefix = LearningHistory.replay(items, events[:len(events) // 2], onboarding_levels=levels)
    assert replayed.records[:len(prefix.records)] == prefix.records
