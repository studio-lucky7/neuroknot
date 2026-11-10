"""학습 이력에서 기준 시점의 사용자별 JSON 리포트를 만든다."""

from __future__ import annotations

from collections import Counter
from datetime import date, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .learning_events import Completion, Exposure, parse_sequence, parse_timestamp, require_id
from .learning_history import EventRecord, LearningHistory
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
    answers: list[EventRecord], zone: ZoneInfo, week_start: date, minimum: int,
) -> dict:
    count = len(answers)
    correct = sum(record.event.is_correct for record in answers)
    theta = answers[-1].attempt.theta_after if answers else None
    before_week = next(
        (record.attempt.theta_before for record in answers
         if (record.applied_at or record.event.occurred_at).astimezone(zone).date() >= week_start),
        theta,
    )
    points = []
    for record in answers:
        point = {
            "event_id": record.event.event_id,
            "occurred_at": record.event.occurred_at.isoformat().replace("+00:00", "Z"),
            "theta_before": record.attempt.theta_before,
            "theta": record.attempt.theta_after,
        }
        if record.applied_at is not None:
            point["sequence"] = str(record.sequence)
            point["applied_at"] = record.applied_at.isoformat().replace("+00:00", "Z")
        points.append(point)
    sufficient = count >= minimum
    return {
        "attempts": count,
        "correct": correct,
        "observed_accuracy": correct / count if count else None,
        "theta": theta,
        "previous_theta": before_week,
        "theta_change": theta - before_week if count else None,
        "theta_history": points,
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
    through_sequence: int | str | None = None,
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
    cursor, records = history.read_records()
    if through_sequence is not None:
        requested = parse_sequence(through_sequence, allow_zero=True)
        if cursor is None or requested > cursor:
            raise ValueError("through_sequence is outside the available sequenced history")
        cursor = requested
    answers: dict[str, list[EventRecord]] = {skill: [] for skill in SKILLS}
    for record in records:
        event = record.event
        if (record.applied_at or event.occurred_at) > cutoff:
            break
        if record.sequence is not None and record.sequence > cursor:
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
            answers[event.skill].append(record)
            daily_answers[event.occurred_at.astimezone(zone).date()] += 1

    skills = {skill: _skill_report(rows, zone, week_start, min_skill_attempts) for skill, rows in answers.items()}
    attempts = daily_answers.total()
    correct = sum(report["correct"] for report in skills.values())
    days = [week_start + timedelta(days=offset) for offset in range(7)]
    report = {
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
    if cursor is not None:
        report["through_sequence"] = str(cursor)
    return report
