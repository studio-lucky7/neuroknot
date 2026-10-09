"""생성된 문항을 사람이 보기 전에 기계가 먼저 거르는 검사.

Pydantic이 이미 걸러 주는 것(선택지 개수, 번호 범위, 오답 유형 값)은 여기서
다시 검사하지 않는다. 여기서는 **지문과 대조해야만 알 수 있는 것**을 본다.
"""

import re

from .schemas import Passage, Question, QuizSet

MIN_EXPLANATION = 20  # 해설 최소 길이(자)
MIN_WHY_WRONG = 10

# "2번이 옳습니다" 처럼 선택지를 번호로 부르는 표현.
# 앱에서 선택지 순서가 달라지면 번호가 어긋나므로 쓰면 안 된다.
# '6번째 문단'은 선택지 번호가 아니므로 제외한다.
OPTION_NUMBER = re.compile(r"[1-9]\s*번(?!째)")


def _norm(text: str) -> str:
    """공백 차이만 무시하고 비교하기 위한 정규화."""
    return re.sub(r"\s+", " ", text).strip()


def check_question(q: Question, passage: Passage, index: int) -> list[str]:
    where = f"문항 {index + 1}"
    problems: list[str] = []

    options = [o.strip() for o in q.options]

    if any(not o for o in options):
        problems.append(f"{where}: 빈 선택지가 있습니다.")
    if len(set(options)) != len(options):
        problems.append(f"{where}: 중복된 선택지가 있습니다.")

    # 근거 문장이 지문에 실제로 존재하는가 — 환각을 잡는 핵심 검사
    if _norm(q.evidence) not in _norm(passage.body):
        problems.append(f"{where}: 근거 문장이 지문에 없습니다 → {q.evidence[:40]!r}")

    # 문제 문장에 정답이 그대로 노출되었는가
    answer = options[q.answer_index]
    if len(answer) >= 3 and _norm(answer) in _norm(q.stem):
        problems.append(f"{where}: 문제 문장에 정답 표현이 그대로 들어 있습니다.")

    # 오답 설명이 정답을 제외한 세 선택지를 정확히 한 번씩 가리키는가
    expected = {i for i in range(4) if i != q.answer_index}
    actual = [d.option_index for d in q.distractors]
    if sorted(actual) != sorted(expected):
        problems.append(
            f"{where}: 오답 설명이 가리키는 선택지가 잘못됐습니다. "
            f"기대 {sorted(expected)}, 실제 {sorted(actual)}"
        )

    if len(_norm(q.explanation)) < MIN_EXPLANATION:
        problems.append(f"{where}: 해설이 너무 짧습니다.")
    for d in q.distractors:
        if len(_norm(d.why_wrong)) < MIN_WHY_WRONG:
            problems.append(f"{where}: 선택지 {d.option_index + 1}의 오답 설명이 너무 짧습니다.")

    # 해설이 선택지를 번호로 지칭하면 번호가 어긋났을 때 학습자가 혼란스럽다
    if OPTION_NUMBER.search(q.explanation):
        problems.append(f"{where}: 해설이 선택지를 번호로 지칭합니다. 내용을 인용하세요.")
    for d in q.distractors:
        if OPTION_NUMBER.search(d.why_wrong):
            problems.append(
                f"{where}: 선택지 {d.option_index + 1}의 오답 설명이 선택지를 번호로 지칭합니다."
            )

    return problems


def check_quiz(quiz: QuizSet, passage: Passage) -> list[str]:
    """문제가 없으면 빈 리스트를 돌려준다."""
    problems: list[str] = []

    skills = [q.skill for q in quiz.questions]
    if len(set(skills)) != len(skills):
        problems.append(f"문항들이 같은 능력을 중복 측정합니다 → {[s.value for s in skills]}")

    # 같은 문장으로 여러 문항을 만들면 지문 전체를 읽을 이유가 없어진다
    evidences = [_norm(q.evidence) for q in quiz.questions]
    if len(set(evidences)) != len(evidences):
        problems.append("여러 문항이 같은 근거 문장을 씁니다. 서로 다른 대목에서 출제하세요.")

    for i, q in enumerate(quiz.questions):
        problems.extend(check_question(q, passage, i))

    return problems
