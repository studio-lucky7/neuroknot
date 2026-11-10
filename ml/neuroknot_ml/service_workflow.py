"""서버 채점과 LearningHistory를 잇는 단일 프로세스 학습 서비스."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from hashlib import sha256
from threading import RLock

from .learning_analytics import analyze_user
from .learning_events import EVENT_VERSION, Completion, Exposure, Submission, require_id
from .learning_history import EventConflictError, EventRecord, LearningHistory
from .selection import PassageCandidate


def _choice(value: object) -> int:
    if type(value) is not int or not 0 <= value < 4:
        raise ValueError("choice index must be an integer from 0 to 3")
    return value


def _text(value: object, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be nonempty text")
    return value


def _item_ids(passage_id: str, quiz_version: str) -> list[str]:
    return [
        "q-" + sha256(json.dumps([passage_id, quiz_version, slot], separators=(",", ":")).encode()).hexdigest()
        for slot in range(3)
    ]


@dataclass(frozen=True)
class _Question:
    item_id: str
    skill: str
    stem: str
    options: tuple[str, ...]
    answer_index: int

    def public(self) -> dict:
        return {"item_id": self.item_id, "stem": self.stem, "options": list(self.options)}


@dataclass(frozen=True)
class _Quiz:
    candidate: PassageCandidate
    version: str
    body: str
    questions: tuple[_Question, ...]

    def public(self) -> dict:
        return {
            "passage_id": self.candidate.passage_id, "quiz_version": self.version, "passage_body": self.body,
            "questions": [question.public() for question in self.questions],
        }

    def private(self) -> dict:
        return {
            **self.public(),
            "difficulty_hint": self.candidate.difficulty_hint,
            "questions": [
                {**q.public(), "skill": q.skill, "answer_index": q.answer_index} for q in self.questions
            ],
        }

    def question(self, item_id: str) -> _Question:
        for question in self.questions:
            if question.item_id == item_id:
                return question
        raise ValueError("item was not exposed in this quiz")


def _build_quiz(generated: Mapping, version: str, body: str) -> _Quiz:
    require_id(version, "quiz_version")
    passage_id = require_id(generated.get("passage_id"), "passage_id")
    candidate = PassageCandidate.from_generated(generated, _item_ids(passage_id, version))
    questions = []
    for item, question in zip(candidate.questions, generated["quiz"]["questions"], strict=True):
        options = question.get("options")
        if not isinstance(options, list) or len(options) != 4:
            raise ValueError("each question requires four options")
        questions.append(_Question(
            item.item_id, item.skill, _text(question.get("stem"), "stem"),
            tuple(_text(option, "option") for option in options), _choice(question.get("answer_index")),
        ))
    return _Quiz(candidate, version, _text(body, "passage_body"), tuple(questions))


class PredictionService:
    """Generation 결과, 서버 정답 키와 기존 학습 엔진의 단일 소유자를 묶는다."""

    def __init__(self, *, onboarding_levels: Mapping[str, str | None] | None = None) -> None:
        self._history = LearningHistory([], onboarding_levels=onboarding_levels)
        self._lock = RLock()
        self._quizzes: dict[tuple[str, str], _Quiz] = {}
        self._active: dict[str, _Quiz] = {}
        self._choices: dict[str, int] = {}

    def register_quiz(
        self, generated: Mapping, *, quiz_version: str, passage_body: str,
        item_difficulties: Mapping[int, int | None] | None = None,
    ) -> dict:
        """검증된 GeneratedQuiz JSON을 불변 출판 버전으로 등록한다."""
        quiz = _build_quiz(generated, quiz_version, passage_body)
        passage_id = quiz.candidate.passage_id
        key = (passage_id, quiz_version)
        item_ids = [q.item_id for q in quiz.questions]
        overrides = {}
        for slot, stars in (item_difficulties or {}).items():
            if type(slot) is not int or not 0 <= slot < len(item_ids):
                raise ValueError("difficulty override must address a valid question slot")
            if stars is not None and (type(stars) is not int or not 1 <= stars <= 5):
                raise ValueError("difficulty must be an integer from 1 to 5 or null")
            overrides[item_ids[slot]] = stars
        with self._lock:
            existing = self._quizzes.get(key)
            if existing is not None:
                priors = {item.item_id: item.difficulty for item in self._history.catalog}
                hint = quiz.candidate.difficulty_hint
                if existing != quiz or any(
                    priors[item_id] != (hint if overrides.get(item_id) is None else overrides[item_id])
                    for item_id in item_ids
                ):
                    raise EventConflictError("quiz_version is already bound to different content or difficulty")
                return existing.public()
            self._history.register_generated(
                {"passage_id": passage_id, "quiz": {
                    "difficulty_hint": quiz.candidate.difficulty_hint,
                    "questions": [{"skill": q.skill} for q in quiz.questions],
                }},
                item_ids, quiz_version=quiz_version, item_versions=dict.fromkeys(item_ids, quiz_version),
                item_difficulties=overrides,
            )
            self._remember_quiz(quiz)
            return quiz.public()

    def _remember_quiz(self, quiz: _Quiz) -> None:
        passage_id = quiz.candidate.passage_id
        self._quizzes[passage_id, quiz.version] = quiz
        self._active[passage_id] = quiz

    def recommend(self, user_id: str) -> dict:
        """다음 지문을 계산한다. 이 호출은 노출 이벤트를 남기지 않는다."""
        with self._lock:
            result = self._history.recommend(user_id, [quiz.candidate for quiz in self._active.values()])
            candidate = result.selection.passage
            return {
                "through_sequence": str(result.through_sequence),
                "quiz": None if candidate is None else self._active[candidate.passage_id].public(),
            }

    def confirm_exposure(
        self, user_id: str, *, exposure_id: str, passage_id: str, quiz_version: str,
        occurred_at: str, applied_at: str,
    ) -> dict:
        """서버가 실제 제공을 확정할 때 호출한다."""
        require_id(user_id, "user_id")
        require_id(exposure_id, "exposure_id")
        require_id(passage_id, "passage_id")
        require_id(quiz_version, "quiz_version")
        event_id = f"workflow:exposure:{exposure_id}"
        with self._lock:
            previous = self._record(event_id)
            if previous is not None:
                prior = previous.event
                if (prior.user_id, prior.passage_id, prior.quiz_version) != (user_id, passage_id, quiz_version):
                    raise EventConflictError("exposure_id is already bound to a different exposure")
                return self._exposure_result(previous, self._quizzes[passage_id, quiz_version])
            quiz = self._active.get(passage_id)
            if quiz is None or quiz.version != quiz_version:
                raise ValueError("quiz version is not active")
            if any(
                isinstance(record.event, Exposure) and record.event.user_id == user_id
                and record.event.passage_id == passage_id for record in self._history.records
            ):
                raise EventConflictError("passage has already been exposed to this user")
            record = self._accept(
                "exposure", event_id, user_id, exposure_id, occurred_at, applied_at,
                passage_id=passage_id, quiz_version=quiz_version, item_ids=[q.item_id for q in quiz.questions],
            )
            return self._exposure_result(record, quiz)

    def submit_answer(
        self, user_id: str, *, exposure_id: str, item_id: str, submission_id: str, choice_index: int,
        occurred_at: str, applied_at: str,
    ) -> dict:
        """정답 키로 채점하고, 최초 응답 여부는 확정된 이력에서 읽는다."""
        require_id(submission_id, "submission_id")
        require_id(item_id, "item_id")
        choice_index = _choice(choice_index)
        event_id = f"workflow:submission:{submission_id}"
        with self._lock:
            quiz = self._exposed_quiz(user_id, exposure_id)
            question = quiz.question(item_id)
            previous = self._record(event_id)
            if previous is not None:
                prior = previous.event
                if (prior.user_id, prior.exposure_id, prior.item_id, self._choices[submission_id]) != (
                    user_id, exposure_id, item_id, choice_index,
                ):
                    raise EventConflictError("submission_id is already bound to a different answer")
                return self._answer_result(previous)
            retry = any(
                isinstance(record.event, Submission) and record.event.user_id == user_id
                and record.event.item_id == item_id for record in self._history.records
            )
            record = self._accept(
                "submission", event_id, user_id, exposure_id, occurred_at, applied_at,
                submission_id=submission_id, passage_id=quiz.candidate.passage_id, item_id=item_id,
                item_version=quiz.version, skill=question.skill, is_correct=choice_index == question.answer_index,
                is_retry=retry,
            )
            self._choices[submission_id] = choice_index
            return self._answer_result(record)

    def complete_learning(self, user_id: str, *, exposure_id: str, occurred_at: str, applied_at: str) -> dict:
        with self._lock:
            self._exposed_quiz(user_id, exposure_id)
            event_id = f"workflow:completion:{exposure_id}"
            record = self._record(event_id)
            if record is None:
                record = self._accept(
                    "completion", event_id, user_id, exposure_id, occurred_at, applied_at, status="completed",
                )
            return {"exposure_id": exposure_id, "status": record.event.status, "sequence": str(record.sequence)}

    def analyze(self, user_id: str, *, as_of: str, timezone_name: str = "Asia/Seoul") -> dict:
        return analyze_user(self._history, user_id, as_of=as_of, timezone_name=timezone_name)

    def _accept(self, kind, event_id, user_id, exposure_id, occurred_at, applied_at, **fields) -> EventRecord:
        return self._history.accept_event({
            "version": EVENT_VERSION, "type": kind, "event_id": event_id, "user_id": user_id,
            "exposure_id": exposure_id, "occurred_at": occurred_at, **fields,
        }, applied_at=applied_at)

    def _record(self, event_id: str) -> EventRecord | None:
        return next((record for record in self._history.records if record.event.event_id == event_id), None)

    def _exposed_quiz(self, user_id: str, exposure_id: str) -> _Quiz:
        require_id(user_id, "user_id")
        require_id(exposure_id, "exposure_id")
        record = self._record(f"workflow:exposure:{exposure_id}")
        if record is None or record.event.user_id != user_id:
            raise ValueError("unknown exposure for this user")
        return self._quizzes[record.event.passage_id, record.event.quiz_version]

    @staticmethod
    def _exposure_result(record: EventRecord, quiz: _Quiz) -> dict:
        return {"exposure_id": record.event.exposure_id, "sequence": str(record.sequence), "quiz": quiz.public()}

    @staticmethod
    def _answer_result(record: EventRecord) -> dict:
        event = record.event
        return {
            "submission_id": event.submission_id, "is_correct": event.is_correct, "is_retry": event.is_retry,
            "sequence": str(record.sequence),
        }

    def checkpoint(self) -> dict:
        """내부 보관용 체크포인트. 정답 키와 선택값을 포함한다."""
        with self._lock:
            return {
                "version": 1, "history": self._history.checkpoint(), "choices": dict(self._choices),
                "quizzes": [quiz.private() for quiz in self._quizzes.values()],
            }

    @classmethod
    def from_checkpoint(cls, state: Mapping) -> PredictionService:
        if not isinstance(state, Mapping) or state.keys() != {"version", "history", "quizzes", "choices"}:
            raise ValueError("invalid workflow checkpoint fields")
        if type(state["version"]) is not int or state["version"] != 1:
            raise ValueError("unsupported workflow checkpoint version")
        if not isinstance(state["quizzes"], list) or not isinstance(state["choices"], dict):
            raise ValueError("invalid workflow checkpoint catalog or receipts")
        service = cls()
        service._history = LearningHistory.from_checkpoint(state["history"])
        catalog = {item.item_id: item for item in service._history.catalog}
        manifests = {(quiz.passage_id, quiz.quiz_version): quiz.item_ids for quiz in service._history.quiz_catalog}
        for data in state["quizzes"]:
            try:
                quiz = _build_quiz({"passage_id": data["passage_id"], "quiz": data},
                                   data["quiz_version"], data["passage_body"])
                ids = tuple(question["item_id"] for question in data["questions"])
            except (KeyError, TypeError) as error:
                raise ValueError("invalid workflow checkpoint quiz") from error
            key = (quiz.candidate.passage_id, quiz.version)
            if manifests.pop(key, None) != ids or ids != tuple(q.item_id for q in quiz.questions):
                raise ValueError("checkpoint quiz does not match registered manifest")
            if any((catalog[q.item_id].skill, catalog[q.item_id].item_version) != (q.skill, quiz.version)
                   for q in quiz.questions):
                raise ValueError("checkpoint quiz does not match registered items")
            service._remember_quiz(quiz)
        if manifests or set(catalog) != {q.item_id for quiz in service._quizzes.values() for q in quiz.questions}:
            raise ValueError("checkpoint workflow catalog is incomplete")
        service._restore_choices(state["choices"])
        return service

    def _restore_choices(self, choices: dict) -> None:
        submissions = {}
        exposures = {}
        for record in self._history.records:
            event = record.event
            if isinstance(event, Exposure):
                expected = f"workflow:exposure:{event.exposure_id}"
                exposures[event.exposure_id] = event
            elif isinstance(event, Completion):
                expected = f"workflow:completion:{event.exposure_id}"
                if event.status != "completed":
                    raise ValueError("invalid workflow completion status")
            else:
                expected = f"workflow:submission:{event.submission_id}"
                submissions[event.submission_id] = event
            if event.event_id != expected:
                raise ValueError("checkpoint contains a non-workflow event")
        if submissions.keys() != choices.keys():
            raise ValueError("checkpoint receipts do not match submissions")
        for submission_id, event in submissions.items():
            exposure = exposures[event.exposure_id]
            quiz = self._quizzes[exposure.passage_id, exposure.quiz_version]
            choice = _choice(choices[submission_id])
            if (choice == quiz.question(event.item_id).answer_index) != event.is_correct:
                raise ValueError("checkpoint receipt does not match recorded grade")
            self._choices[submission_id] = choice
