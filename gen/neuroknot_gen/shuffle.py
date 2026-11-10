"""선택지 순서 섞기.

모델에게 "정답 위치를 골고루 배치하라"고 부탁하는 대신 코드로 처리한다.
실제로 샘플 5편(15문항)을 생성했을 때 정답의 80%가 1번에 몰렸는데,
지문을 읽지 않고 1번만 찍어도 맞는 문제가 되어 훈련이 되지 않는다.

섞을 때 함께 움직여야 하는 값이 두 개 있다. 하나라도 어긋나면 채점이 틀리거나
해설이 엉뚱한 선택지에 붙으므로, 옮긴 자리를 한 곳에서 계산해 모두에게 적용한다.
  - Question.answer_index
  - Distractor.option_index
"""

import random

from .schemas import Distractor, Question, QuizSet

OPTION_COUNT = 4


def _place_answer_at(question: Question, target: int, rng: random.Random) -> Question:
    """정답을 target 위치로 옮기고 나머지 선택지는 무작위로 재배치한다."""
    old_answer = question.answer_index
    others = [i for i in range(OPTION_COUNT) if i != old_answer]
    rng.shuffle(others)

    # new_to_old[새 위치] = 원래 위치
    new_to_old: list[int] = []
    remaining = iter(others)
    for position in range(OPTION_COUNT):
        new_to_old.append(old_answer if position == target else next(remaining))

    # old_to_new[원래 위치] = 새 위치
    old_to_new = {old: new for new, old in enumerate(new_to_old)}

    return question.model_copy(
        update={
            "options": [question.options[old] for old in new_to_old],
            "answer_index": old_to_new[old_answer],
            # 섞고 나면 원래 순서가 뒤죽박죽이므로 선택지 번호 순으로 정렬한다
            "distractors": sorted(
                (
                    Distractor(
                        option_index=old_to_new[d.option_index],
                        why_wrong=d.why_wrong,
                        error_type=d.error_type,
                    )
                    for d in question.distractors
                ),
                key=lambda d: d.option_index,
            ),
        }
    )


def shuffle_quiz(quiz: QuizSet, seed: str) -> QuizSet:
    """한 지문의 문항들을 섞는다.

    같은 seed(지문 ID)면 항상 같은 결과가 나오므로 다시 돌려도 재현되고 테스트할 수 있다.
    한 지문 안의 문항들은 **서로 다른 위치**에 정답이 가도록 자리를 나눠 갖는다.
    """
    rng = random.Random(seed)
    count = len(quiz.questions)
    if count <= OPTION_COUNT:
        targets = rng.sample(range(OPTION_COUNT), count)
    else:  # 문항이 선택지 수보다 많아지면 자리를 나눠 가질 수 없으므로 무작위로
        targets = [rng.randrange(OPTION_COUNT) for _ in range(count)]
    return quiz.model_copy(
        update={
            "questions": [
                _place_answer_at(q, t, rng) for q, t in zip(quiz.questions, targets)
            ]
        }
    )
