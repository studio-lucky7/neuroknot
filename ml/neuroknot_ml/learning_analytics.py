"""학습 이력에서 기준 시점의 사용자별 JSON 리포트를 만든다."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .learning_events import Completion, Exposure, Submission, parse_timestamp, require_id
from .learning_history import AttemptTrace, LearningHistory
from .skills import SKILLS


def _current_streak(completed_days: set[date], today: date) -> int:
    day = today
    if day not in completed_days:
        day -= timedelta(days=1)
    streak = 0
    while day in completed_days:
        streak += 1
        day -= timedelta(days=1)
    return streak


def _skill_report(
    answers: list[tuple[Submission, AttemptTrace]], zone: ZoneInfo, week_start: date, minimum: int,
) -> dict:
    count = len(answers)
    correct = sum(event.is_correct for event, _ in answers)
    theta = answers[-1][1].theta_after if answers else None
    before_week = next(
        (trace.theta_before for event, trace in answers if event.occurred_at.astimezone(zone).date() >= week_start),
        theta,
    )
    sufficient = count >= minimum
    return {
        "attempts": count,
        "correct": correct,
        "observed_accuracy": correct / count if count else None,
        "theta": theta,
        "previous_theta": before_week,
        "theta_change": theta - before_week if count else None,
        "theta_history": [
            {
                "event_id": event.event_id,
                "occurred_at": event.occurred_at.isoformat().replace("+00:00", "Z"),
                "theta_before": trace.theta_before,
                "theta": trace.theta_after,
            }
            for event, trace in answers
        ],
        "has_sufficient_history": sufficient,
        "status": "no_data" if not count else ("observed" if sufficient else "insufficient_data"),
    }


def analyze_user(
    history: LearningHistory,
    user_id: str,
    *,
    as_of: str,
    timezone_name: str = "Asia/Seoul",
    min_skill_attempts: int = 5,
) -> dict:
    """기준 시각(포함)까지의 활동과 주간 시작 대비 Elo 변화량을 반환한다."""
    require_id(user_id, "user_id")
    cutoff = parse_timestamp(as_of, "as_of")
    require_id(timezone_name, "timezone_name")
    try:
        zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as error:
        raise ValueError(f"unknown IANA timezone: {timezone_name!r}") from error
    if type(min_skill_attempts) is not int or min_skill_attempts < 1:
        raise ValueError("min_skill_attempts must be a positive integer")
    today = cutoff.astimezone(zone).date()
    week_start = today - timedelta(days=today.weekday())

    passages: set[str] = set()
    exposures = retries = 0
    daily_answers: Counter[date] = Counter()
    daily_completions: Counter[date] = Counter()
    answers: dict[str, list[tuple[Submission, AttemptTrace]]] = {skill: [] for skill in SKILLS}
    for record in history.records:
        event = record.event
        if event.occurred_at > cutoff:
            break
        if event.user_id != user_id:
            continue
        if isinstance(event, Exposure):
            exposures += 1
            passages.add(event.passage_id)
        elif isinstance(event, Completion):
            if event.status == "completed":
                daily_completions[event.occurred_at.astimezone(zone).date()] += 1
        elif event.is_retry:
            retries += 1
        else:
            assert record.attempt is not None
            answers[event.skill].append((event, record.attempt))
            daily_answers[event.occurred_at.astimezone(zone).date()] += 1

    skills = {skill: _skill_report(rows, zone, week_start, min_skill_attempts) for skill, rows in answers.items()}
    attempts = daily_answers.total()
    correct = sum(report["correct"] for report in skills.values())
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    return {
        "version": 1,
        "user_id": user_id,
        "as_of": cutoff.isoformat().replace("+00:00", "Z"),
        "timezone": timezone_name,
        "data_status": "available" if exposures else "no_activity",
        "summary": {
            "first_attempts": attempts,
            "correct_first_attempts": correct,
            "observed_accuracy": correct / attempts if attempts else None,
            "retries": retries,
            "exposures": exposures,
            "exposed_passages": len(passages),
            "completed_sessions": daily_completions.total(),
        },
        "weekly": {
            "week_start": week_start.isoformat(),
            "first_attempts": sum(daily_answers[day] for day in days),
            "completed_sessions": sum(daily_completions[day] for day in days),
            "streak_days": _current_streak(set(daily_completions), today),
            "days": [
                {"date": day.isoformat(), "first_attempts": daily_answers[day], "completed_sessions": daily_completions[day]}
                for day in days
            ],
        },
        "min_skill_attempts": min_skill_attempts,
        "skills": skills,
    }
