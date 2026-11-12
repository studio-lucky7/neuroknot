"""생성 단계에서 코드가 정하는 것(스킬 배정, 난이도 합산)을 확인한다. 모델은 부르지 않는다."""

import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuroknot_gen import generate  # noqa: E402
from neuroknot_gen.loader import load_passage  # noqa: E402
from neuroknot_gen.schemas import DifficultyFactors  # noqa: E402
from neuroknot_gen.skills import Skill  # noqa: E402

from test_validate import make_quiz  # noqa: E402


def test_배정_스킬은_서로_다른_세_개이고_다시_불러도_같다():
    skills = generate.assigned_skills("fx-001")
    assert len(skills) == 3 and len(set(skills)) == 3
    assert generate.assigned_skills("fx-001") == skills
    assert skills == [s for s in Skill if s in skills]  # 순서는 스킬 정의 순서


def test_지문이_많으면_네_스킬이_고르게_나온다():
    counts = Counter(s for i in range(2000) for s in generate.assigned_skills(f"p-{i}"))
    assert set(counts) == set(Skill)
    assert all(1400 <= n <= 1600 for n in counts.values())  # 기대값 1500 (2000 × 3/4)


def test_옛_프롬프트는_모델이_스킬을_고른다():
    assert generate.skills_for("fx-001", "quiz_v2") is None
    assert generate.skills_for("fx-001", "quiz_v3") == generate.assigned_skills("fx-001")


def test_배정_스킬이_요청에_들어간다():
    passage = load_passage("fx-001")
    text = generate.build_user_content(passage, skills=[Skill.FACT, Skill.VOCAB, Skill.MAIN_IDEA])
    assert "<출제할 능력>" in text
    assert "1. fact\n2. vocab\n3. main_idea" in text
    assert "<출제할 능력>" not in generate.build_user_content(passage)


@pytest.mark.parametrize("scores, hint", [
    ((0, 0, 0, 0), 1), ((1, 0, 0, 0), 1), ((1, 1, 0, 0), 2), ((1, 1, 1, 1), 3),
    ((2, 1, 1, 1), 3), ((2, 2, 1, 1), 4), ((2, 2, 2, 1), 4), ((2, 2, 2, 2), 5),
])
def test_난이도는_요소_합계로_정한다(scores, hint):
    terms, density, structure, abstraction = scores
    assert DifficultyFactors(terms=terms, density=density, structure=structure,
                             abstraction=abstraction).to_hint() == hint


class FakeClient:
    """generate_content가 정해 둔 QuizSet을 돌려주는 가짜 Gemini 클라이언트."""

    def __init__(self, quiz):
        self.calls = []
        self.models = SimpleNamespace(generate_content=self._generate)
        self._quiz = quiz

    def _generate(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(parsed=self._quiz, prompt_feedback=None)


def test_요소_점수가_있으면_모델이_쓴_난이도를_덮어쓴다():
    passage = load_passage("fx-001")
    quiz = make_quiz(passage)
    quiz.difficulty_hint = 2
    quiz.difficulty_factors = DifficultyFactors(terms=2, density=2, structure=1, abstraction=1)
    client = FakeClient(quiz)

    generated = generate.generate_quiz(passage, prompt_version="quiz_v3", client=client)

    assert generated.quiz.difficulty_hint == 4
    assert "<출제할 능력>" in client.calls[0]["contents"]


def test_요소_점수가_없으면_모델_난이도를_그대로_쓴다():
    passage = load_passage("fx-001")
    quiz = make_quiz(passage)
    quiz.difficulty_hint = 2
    client = FakeClient(quiz)

    generated = generate.generate_quiz(passage, prompt_version="quiz_v2", client=client)

    assert generated.quiz.difficulty_hint == 2
    assert "<출제할 능력>" not in client.calls[0]["contents"]
