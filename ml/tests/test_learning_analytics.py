import json

import pytest

from neuroknot_ml.learning_analytics import analyze_user
from neuroknot_ml.learning_history import CatalogItem, LearningHistory
from neuroknot_ml.skills import SKILLS
from test_learning_events import completion, exposure, submission

ITEMS = tuple(CatalogItem(f"q{i}", "v1", "fact") for i in range(1, 8))


def session(index, at, *, correct=True, user_id="u1"):
    base = {"user_id": user_id, "exposure_id": f"{user_id}-{index}", "occurred_at": at}
    item_id = f"q{index}"
    return [
        exposure(**base, event_id=f"{user_id}-ex-{index}", item_ids=[item_id]),
        submission(**base, event_id=f"{user_id}-ans-{index}", submission_id=f"{user_id}-sub-{index}",
                   item_id=item_id, is_correct=correct),
        completion(**base, event_id=f"{user_id}-done-{index}"),
    ]


def test_summary_separates_first_answers_retries_exposures_and_completed_sessions():
    session_events = session(1, "2026-01-05T00:00:00Z", correct=False)
    retry = {**session_events[1], "event_id": "retry", "submission_id": "retry", "is_retry": True, "is_correct": True}
    other = session(2, "2026-01-05T01:00:00Z", user_id="u2")
    exposed = exposure(event_id="idle", exposure_id="idle", item_ids=["q3"], passage_id="other")
    abandoned = completion(event_id="stop", exposure_id="idle", status="abandoned")
    history = LearningHistory.replay(ITEMS, [
        exposed, abandoned, *session_events[:2], retry, retry, session_events[2], session_events[2], *other,
    ])
    report = analyze_user(history, "u1", as_of="2026-01-05T04:00:00Z")

    assert report["summary"] == {
        "first_attempts": 1, "correct_first_attempts": 0, "observed_accuracy": 0.0,
        "retries": 1, "exposures": 2, "exposed_passages": 2, "completed_sessions": 1,
    }
    assert report["skills"]["fact"]["attempts"] == 1
    assert report["skills"]["fact"]["theta"] == -0.4
    assert report["skills"]["fact"]["status"] == "insufficient_data"
    assert report["skills"]["vocab"]["theta"] is None
    assert report["skills"]["vocab"]["status"] == "no_data"
    assert analyze_user(history, "u2", as_of=report["as_of"])["summary"]["observed_accuracy"] == 1.0
    assert json.loads(json.dumps(report, allow_nan=False)) == report


def test_timezone_and_midnight_move_counts_to_the_correct_local_week():
    events = session(1, "2026-01-04T14:59:59Z") + session(2, "2026-01-04T15:00:00Z")
    history = LearningHistory.replay(ITEMS, events)
    seoul = analyze_user(history, "u1", as_of="2026-01-05T00:00:00Z")
    utc = analyze_user(history, "u1", as_of=seoul["as_of"], timezone_name="UTC")

    assert seoul["weekly"]["week_start"] == "2026-01-05"
    assert seoul["weekly"]["days"][0] == {"date": "2026-01-05", "first_attempts": 1, "completed_sessions": 1}
    assert seoul["weekly"]["first_attempts"] == 1
    assert [row["first_attempts"] for row in seoul["weekly"]["days"]] == [1, 0, 0, 0, 0, 0, 0]
    assert utc["weekly"]["first_attempts"] == 0
    assert (seoul["weekly"]["streak_days"], utc["weekly"]["streak_days"]) == (2, 1)


@pytest.mark.parametrize(("as_of", "streak"), [("2026-01-06", 2), ("2026-01-07", 2), ("2026-01-08", 0)])
def test_streak_survives_yesterday_but_breaks_after_a_gap(as_of, streak):
    events = session(1, "2026-01-05T00:00:00Z") + session(2, "2026-01-06T00:00:00Z")
    history = LearningHistory.replay(ITEMS, events)

    report = analyze_user(history, "u1", as_of=f"{as_of}T00:00:00Z")

    assert report["weekly"]["streak_days"] == streak


def test_exposure_without_answers_and_unknown_user_have_no_accuracy_or_streak():
    history = LearningHistory.replay(ITEMS, [exposure()])
    idle = analyze_user(history, "u1", as_of="2026-01-06T00:00:00Z")
    empty = analyze_user(history, "unknown", as_of=idle["as_of"])

    assert idle["summary"]["exposures"] == 1
    assert empty["data_status"] == "no_activity"
    for report in (idle, empty):
        assert report["summary"]["observed_accuracy"] is None
        assert report["weekly"]["streak_days"] == 0
        assert report["weekly"]["completed_sessions"] == 0
        assert tuple(report["skills"]) == SKILLS
        assert all(skill["theta"] is None and skill["theta_history"] == [] for skill in report["skills"].values())


def test_theta_delta_uses_week_start_and_historical_cutoff_without_future_events():
    past = session(1, "2026-01-04T14:00:00Z")
    present = session(2, "2026-01-04T16:00:00Z", correct=False)
    future = session(3, "2026-01-06T00:00:00Z")
    levels = {"u1": "cruising"}
    full = LearningHistory.replay(ITEMS, past + present + future, onboarding_levels=levels)
    prefix = LearningHistory.replay(ITEMS, past + present, onboarding_levels=levels)
    options = {"as_of": "2026-01-05T00:00:00Z", "min_skill_attempts": 2}
    report = analyze_user(full, "u1", **options)
    fact = report["skills"]["fact"]

    assert report == analyze_user(prefix, "u1", **options)
    assert fact["theta_history"][0]["theta_before"] == -0.3
    assert fact["previous_theta"] == fact["theta_history"][0]["theta"]
    assert fact["theta"] == prefix.user_rating("u1", "fact")
    assert fact["theta_change"] == fact["theta"] - fact["previous_theta"] < 0
    assert fact["status"] == "observed"
    assert fact["has_sufficient_history"]
    assert fact["observed_accuracy"] == 0.5


def test_bad_report_parameters_are_rejected():
    history = LearningHistory(ITEMS)
    with pytest.raises(ValueError, match="as_of"):
        analyze_user(history, "u1", as_of="2026-01-05T00:00:00")
    with pytest.raises(ValueError, match="timezone"):
        analyze_user(history, "u1", as_of="2026-01-05T00:00:00Z", timezone_name="No/Timezone")
    with pytest.raises(ValueError, match="min_skill_attempts"):
        analyze_user(history, "u1", as_of="2026-01-05T00:00:00Z", min_skill_attempts=True)
