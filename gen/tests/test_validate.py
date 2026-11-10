"""자동 검사가 실제로 걸러 내는지 확인한다.

여기서 보는 건 '검사기가 잘못된 문항을 잡아내는가'이지, 생성 품질이 아니다.
생성 품질은 평가 세트(eval)에서 따로 측정한다.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuroknot_gen.loader import load_passage  # noqa: E402
from neuroknot_gen.schemas import Distractor, Question, QuizSet  # noqa: E402
from neuroknot_gen.skills import ErrorType, Skill  # noqa: E402
from neuroknot_gen.validate import check_quiz  # noqa: E402


@pytest.fixture
def passage():
    return load_passage("fx-001")


def make_question(passage, **overrides) -> Question:
    """fx-001 지문에 대해 검사를 통과하는 문항 하나."""
    evidence = passage.body.split("\n\n")[1]  # 원문 문단을 그대로 인용
    base = dict(
        skill=Skill.FACT,
        stem="실무협의체는 언제부터 운영되는가?",
        options=["이번 달부터", "다음 달부터", "내년 1월부터", "올해 12월부터"],
        answer_index=1,
        evidence=evidence,
        explanation="지문에 실무협의체를 구성해 다음 달부터 본격 운영한다고 적혀 있습니다.",
        distractors=[
            Distractor(option_index=0, why_wrong="지문은 다음 달부터라고 밝혔습니다.",
                       error_type=ErrorType.MISSED_DETAIL),
            Distractor(option_index=2, why_wrong="지문에 없는 시점을 추측한 것입니다.",
                       error_type=ErrorType.OVER_INFERENCE),
            Distractor(option_index=3, why_wrong="12월은 마스터플랜 수립 시점입니다.",
                       error_type=ErrorType.SCOPE_CONFUSION),
        ],
    )
    base.update(overrides)
    return Question(**base)


def make_quiz(passage, first=None) -> QuizSet:
    """검사를 통과하는 문항 3개. 근거 문장은 서로 다른 문단에서 가져온다."""
    paragraphs = passage.body.split("\n\n")
    q1 = first or make_question(passage)
    q2 = make_question(passage, skill=Skill.INFERENCE, evidence=paragraphs[2])
    q3 = make_question(passage, skill=Skill.MAIN_IDEA, evidence=paragraphs[0])
    return QuizSet(difficulty_hint=3, questions=[q1, q2, q3])


def test_정상_문항은_통과한다(passage):
    assert check_quiz(make_quiz(passage), passage) == []


def test_근거_문장이_지문에_없으면_잡아낸다(passage):
    bad = make_question(passage, evidence="지문에 존재하지 않는 문장입니다.")
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("근거 문장이 지문에 없습니다" in p for p in problems)


def test_근거_문장의_공백_차이는_허용한다(passage):
    evidence = passage.body.split("\n\n")[1]
    spaced = make_question(passage, evidence="  " + evidence.replace(" ", "  ") + "  ")
    assert check_quiz(make_quiz(passage, spaced), passage) == []


def test_문제에_정답이_노출되면_잡아낸다(passage):
    bad = make_question(passage, stem="실무협의체는 다음 달부터 운영되는가?")
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("정답 표현이 그대로" in p for p in problems)


def test_선택지가_중복되면_잡아낸다(passage):
    bad = make_question(passage, options=["다음 달부터", "다음 달부터", "내년", "12월"])
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("중복된 선택지" in p for p in problems)


def test_오답설명이_정답을_가리키면_잡아낸다(passage):
    bad = make_question(
        passage,
        distractors=[
            Distractor(option_index=1, why_wrong="정답을 가리키고 있습니다.",
                       error_type=ErrorType.MISSED_DETAIL),
            Distractor(option_index=2, why_wrong="지문에 없는 시점입니다.",
                       error_type=ErrorType.OVER_INFERENCE),
            Distractor(option_index=3, why_wrong="12월은 다른 일정입니다.",
                       error_type=ErrorType.SCOPE_CONFUSION),
        ],
    )
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("가리키는 선택지가 잘못" in p for p in problems)


def test_같은_능력을_중복_측정하면_잡아낸다(passage):
    q = make_question(passage)
    quiz = QuizSet(difficulty_hint=3, questions=[q, q, q])
    problems = check_quiz(quiz, passage)
    assert any("중복 측정" in p for p in problems)


def test_해설이_너무_짧으면_잡아낸다(passage):
    bad = make_question(passage, explanation="정답입니다.")
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("해설이 너무 짧습니다" in p for p in problems)


def test_해설이_선택지를_번호로_부르면_잡아낸다(passage):
    bad = make_question(passage, explanation="지문에 따르면 2번이 옳습니다. 근거가 분명합니다.")
    problems = check_quiz(make_quiz(passage, bad), passage)
    assert any("번호로 지칭" in p for p in problems)


def test_문단_번호_언급은_허용한다(passage):
    ok = make_question(
        passage,
        explanation="지문 6번째 문단에 실무협의체를 다음 달부터 운영한다고 적혀 있습니다.",
    )
    assert check_quiz(make_quiz(passage, ok), passage) == []


def test_여러_문항이_같은_근거를_쓰면_잡아낸다(passage):
    evidence = passage.body.split("\n\n")[1]
    quiz = QuizSet(
        difficulty_hint=3,
        questions=[
            make_question(passage, skill=Skill.FACT, evidence=evidence),
            make_question(passage, skill=Skill.INFERENCE, evidence=evidence),
            make_question(passage, skill=Skill.MAIN_IDEA, evidence=evidence),
        ],
    )
    problems = check_quiz(quiz, passage)
    assert any("같은 근거 문장" in p for p in problems)
