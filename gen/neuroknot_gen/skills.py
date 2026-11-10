"""문항에 붙는 스킬과, 오답 선택지에 붙는 오답 유형.

스킬(skill)과 오답 유형(error_type)은 다른 개념이다.
- 스킬        : 이 문항이 **무엇을 측정하는가**. 문항 하나에 하나.
                슬라이스 3(성장 예측)이 스킬별로 학습자 실력을 추정한다.
- 오답 유형    : 이 오답 선택지가 **어떤 오류를 유도하도록 설계되었는가**. 틀린 선택지마다 하나.
                출제 시점의 의도를 기록한 값이다.

  주의: 학습자가 그 선택지를 골랐다고 해서 실제로 그 실수를 했다고 확정할 수는 없다.
  찍었을 수도 있고 다른 이유로 골랐을 수도 있다. 한 번의 선택은 **신호**일 뿐이며,
  여러 번의 기록이 쌓였을 때 취약점 분석과 추천에 의미가 생긴다.

스킬 목록은 `ml/neuroknot_ml/skills.py`(슬라이스 3)와 **반드시 같아야 한다.**
바꿀 때는 협업 가이드 6절에 따라 팀 합의가 필요하다.
"""

from enum import Enum


class Skill(str, Enum):
    FACT = "fact"  # 사실 확인 — 지문에 적힌 정보를 정확히 찾아내는가
    INFERENCE = "inference"  # 추론 — 직접 적혀 있지 않은 내용을 근거로 이끌어내는가
    VOCAB = "vocab"  # 어휘 — 핵심 용어의 뜻을 문맥에서 파악하는가
    MAIN_IDEA = "main_idea"  # 중심 내용 — 글 전체의 요지를 잡아내는가


class ErrorType(str, Enum):
    MISSED_DETAIL = "missed_detail"  # 지문에 있는 정보를 놓침
    OVER_INFERENCE = "over_inference"  # 지문에 없는 내용까지 추론함
    VOCAB_CONFUSION = "vocab_confusion"  # 핵심 어휘를 잘못 이해함
    SCOPE_CONFUSION = "scope_confusion"  # 일부를 전체로, 전체를 일부로 착각함
    PRIOR_KNOWLEDGE = "prior_knowledge"  # 지문 대신 배경지식으로 답함


SKILL_DESCRIPTIONS = {
    Skill.FACT: "지문에 명시된 정보를 정확히 찾아내는 능력",
    Skill.INFERENCE: "지문의 근거로부터 직접 서술되지 않은 내용을 이끌어내는 능력",
    Skill.VOCAB: "핵심 용어나 표현의 의미를 문맥에서 파악하는 능력",
    Skill.MAIN_IDEA: "글 전체의 요지와 글쓴이의 관점을 파악하는 능력",
}

# 각 오답 선택지가 '유도하려는' 오류. 학습자가 실제로 그렇게 틀렸다는 뜻은 아니다.
ERROR_TYPE_DESCRIPTIONS = {
    ErrorType.MISSED_DETAIL: "지문에 분명히 적혀 있는 정보를 놓친 사람이 고르도록 설계된 선택지",
    ErrorType.OVER_INFERENCE: "지문이 뒷받침하지 않는 내용까지 추론한 사람이 고르도록 설계된 선택지",
    ErrorType.VOCAB_CONFUSION: "핵심 용어의 의미를 잘못 이해한 사람이 고르도록 설계된 선택지",
    ErrorType.SCOPE_CONFUSION: "일부를 전체로, 전체를 일부로 착각한 사람이 고르도록 설계된 선택지",
    ErrorType.PRIOR_KNOWLEDGE: "지문 대신 평소 상식으로 답한 사람이 고르도록 설계된 선택지",
}
