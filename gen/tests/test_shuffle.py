"""선택지를 섞어도 정답과 해설이 제 짝을 유지하는지 확인한다.

여기서 깨지면 사용자가 맞은 답이 틀렸다고 나오거나, 엉뚱한 선택지에 해설이 붙는다.
"""

import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuroknot_gen.schemas import Distractor, Question, QuizSet  # noqa: E402
from neuroknot_gen.shuffle import shuffle_quiz  # noqa: E402
from neuroknot_gen.skills import ErrorType, Skill  # noqa: E402

ERRORS = [ErrorType.MISSED_DETAIL, ErrorType.OVER_INFERENCE, ErrorType.SCOPE_CONFUSION]


def make_question(skill: Skill, answer_index: int = 0) -> Question:
    """선택지 내용과 해설을 짝지어 둬서, 섞인 뒤에도 짝이 유지되는지 확인할 수 있다."""
    others = [i for i in range(4) if i != answer_index]
    return Question(
        skill=skill,
        stem="문제 문장입니다.",
        options=[f"선택지{i}" for i in range(4)],
        answer_index=answer_index,
        evidence=f"근거 문장 {skill.value}",
        explanation="정답에 대한 해설입니다. 충분히 깁니다.",
        distractors=[
            Distractor(
                option_index=i,
                why_wrong=f"선택지{i}에 대한 설명입니다.",  # 내용에 원래 번호를 심어 둔다
                error_type=ERRORS[n],
            )
            for n, i in enumerate(others)
        ],
    )


def make_quiz(answer_index: int = 0) -> QuizSet:
    return QuizSet(
        difficulty_hint=3,
        questions=[
            make_question(Skill.FACT, answer_index),
            make_question(Skill.INFERENCE, answer_index),
            make_question(Skill.MAIN_IDEA, answer_index),
        ],
    )


def test_정답_내용이_그대로_유지된다():
    quiz = make_quiz(answer_index=0)
    shuffled = shuffle_quiz(quiz, seed="fx-001")
    for before, after in zip(quiz.questions, shuffled.questions):
        assert after.options[after.answer_index] == before.options[before.answer_index]


def test_오답_해설이_원래_선택지를_따라간다():
    """why_wrong 안에 심어 둔 원래 선택지 이름과, 새 위치의 선택지가 일치해야 한다."""
    shuffled = shuffle_quiz(make_quiz(), seed="fx-002")
    for q in shuffled.questions:
        for d in q.distractors:
            assert d.why_wrong.startswith(q.options[d.option_index])


def test_오답_설명이_정답을_가리키지_않는다():
    shuffled = shuffle_quiz(make_quiz(), seed="fx-003")
    for q in shuffled.questions:
        assert q.answer_index not in [d.option_index for d in q.distractors]
        assert sorted(d.option_index for d in q.distractors) == sorted(
            i for i in range(4) if i != q.answer_index
        )


def test_선택지_구성은_바뀌지_않는다():
    quiz = make_quiz()
    shuffled = shuffle_quiz(quiz, seed="fx-004")
    for before, after in zip(quiz.questions, shuffled.questions):
        assert sorted(after.options) == sorted(before.options)


def test_한_지문_안에서_정답_위치가_겹치지_않는다():
    shuffled = shuffle_quiz(make_quiz(), seed="fx-005")
    positions = [q.answer_index for q in shuffled.questions]
    assert len(set(positions)) == len(positions)


def test_같은_seed_면_결과가_같다():
    a = shuffle_quiz(make_quiz(), seed="fx-001")
    b = shuffle_quiz(make_quiz(), seed="fx-001")
    assert [q.answer_index for q in a.questions] == [q.answer_index for q in b.questions]


def test_정답_위치가_한쪽으로_몰리지_않는다():
    """지문 100편을 섞었을 때 네 위치에 고르게 퍼지는지 본다."""
    counts: Counter[int] = Counter()
    for n in range(100):
        shuffled = shuffle_quiz(make_quiz(), seed=f"fx-{n:03d}")
        counts.update(q.answer_index for q in shuffled.questions)
    assert set(counts) == {0, 1, 2, 3}
    # 300문항이 완전히 고르면 각 75개. 넉넉히 50~100 사이면 쏠림이 없다고 본다.
    assert all(50 <= c <= 100 for c in counts.values()), counts


def test_오답_설명이_선택지_번호순으로_정렬된다():
    shuffled = shuffle_quiz(make_quiz(), seed="fx-006")
    for q in shuffled.questions:
        indexes = [d.option_index for d in q.distractors]
        assert indexes == sorted(indexes)
