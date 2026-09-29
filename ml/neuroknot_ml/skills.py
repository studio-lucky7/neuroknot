"""문제에 붙는 스킬 태그 목록.

TODO(Day 0): 문제 생성 파트와 스킬 체계를 확정할 때까지 쓰는 임시값이다.
확정되면 이 목록만 바꾸면 시뮬레이터/모델이 그대로 따라간다.
"""

FACT = "fact"  # 사실 확인
INFERENCE = "inference"  # 추론
VOCAB = "vocab"  # 어휘
MAIN_IDEA = "main_idea"  # 중심 내용 파악

SKILLS: tuple[str, ...] = (FACT, INFERENCE, VOCAB, MAIN_IDEA)
