# Prediction Core V1 설계

## 입력과 출력

| 입력 | 계약 |
| --- | --- |
| Generation 결과 | 검수된 `GeneratedQuiz` JSON의 `passage_id`, `quiz.difficulty_hint`, `quiz.questions[*].skill`을 읽는다. 지문마다 서로 다른 스킬의 문항 3개가 필요하다. |
| 문항 ID | 호출자가 퀴즈 버전별로 안정적인 문자열 ID 3개를 원래 문항 순서대로 제공한다. 같은 지문의 여러 퀴즈 버전 중 노출 가능한 버전 하나를 선택해서 전달한다. |
| 모델 | `predict(user_id, item_id)`와 `user_rating(user_id, skill)`을 제공한다. Elo에 문항을 등록할 때 후보와 같은 스킬을 사용한다. 문항별 난이도는 Prediction에서 정하며, 없으면 기존 기본 prior `0.0`을 적용한다. `difficulty_hint`는 지문 메타데이터로 보존한다. |
| 사용자 이력 | `seen_passage_ids`와 `seen_item_ids`는 사용자에게 이미 노출한 ID 집합이다. `skill_attempts`는 스킬별 누적 첫 응답 수다. 생략한 스킬의 횟수는 0이다. |

`SelectionResult`는 선택한 `passage`, `scores`, `reasons`와 평가 가능·기노출·미등록 후보 수를 담는다.
점수에는 후보의 문항 순서와 같은 순서의 예측 확률, 평균 확률, 적용 목표, 목표 거리, 취약 스킬·커버리지 보너스, 최종 점수가 들어간다.
이유 코드는 `target_fit` 또는 `cold_start`와, 양수인 보너스에 대응하는 `weak_skill`, `skill_coverage`다.

```python
import json

from neuroknot_ml.elo import EloModel
from neuroknot_ml.selection import PassageCandidate, select_passage

model = EloModel()
model.register_user("u1", "cruising")
candidate = PassageCandidate.from_generated(generated_quiz, ["q101", "q102", "q103"])
for question in candidate.questions:
    model.register_item(question.item_id, question.skill)  # 문항별 prior가 있으면 difficulty 전달

result = select_passage(
    model,
    "u1",
    [candidate],
    seen_passage_ids=set(),
    seen_item_ids=set(),
    skill_attempts={},
)
if result.passage is not None:
    selected_passage_id = result.passage.passage_id

# 실제 채점 이후에만 모델을 갱신하고, 호출자가 노출 ID와 첫 응답 이력을 기록한다.
payload = json.dumps(model.to_state(), allow_nan=False)
restored = EloModel.from_state(json.loads(payload))
```

상태 스키마 버전 1은 모델 설정·K 스케줄, 사용자 온보딩 prior, 사용자·스킬별 θ와 풀이 수,
문항별 스킬·난이도·풀이 수를 저장한다. 같은 후보군·설정·이력을 넘기면 복원 후에도 같은 지문을 선택한다.

## 선택 정책

1. 동일 후보는 한 번만 평가한다. 이미 노출한 지문이나, 노출된 문항이 하나라도 있는 지문을 제외한다.
   Elo에서 등록되지 않은 문항을 조회하면 발생하는 `KeyError`는 해당 지문을 제외하는 신호다.
2. Elo의 세 문항 예측값을 읽는다. 일반 목표는 `0.70`이다. 첫 응답이 6건 미만이면 콜드스타트로 보고,
   일반 목표와 콜드스타트 목표 `0.80` 중 높은 값을 사용한다. 세 문항 각각의 목표 절대 오차를 평균해 목표 거리를 계산한다.
3. 콜드스타트 이후, 두 스킬 이상에 각각 응답이 2건 이상 있고 해당 θ에 차이가 있으면 가장 낮은 θ의 스킬을 취약 스킬로 둔다.
   후보 문항 중 그 스킬들이 차지하는 비율에 `0.20`을 곱해 가산한다.
4. 전체 스킬 중 가장 많이 푼 횟수를 `M`이라 할 때, 각 후보 스킬의 부족분 `(M - 스킬 풀이 수) / M`을 평균한 뒤
   `0.15`를 곱해 가산한다. 풀이가 0건이면 커버리지 보너스도 0이다.
5. `1 - 목표 거리 + 취약 스킬 보너스 + 커버리지 보너스`가 가장 높은 지문을 고른다.
   동점이면 목표 거리가 작은 지문을 고르고, 계속 같으면 사용자 ID와 지문 ID의 안정적인 SHA-256 순서를 사용한다.
   설정값은 `SelectionConfig`에서 조정할 수 있다.

후보가 하나만 남으면 해당 후보를 반환한다. 모두 제외되면 `passage=None`, `scores=None`과
`no_eligible_passage`를 반환하고, 처음부터 후보가 없으면 `empty_catalog`를 반환한다.
동일 지문 ID에 내용이 다른 후보, 잘못된 후보 스킬이나 풀이 횟수, 범위를 벗어난 모델 확률에는 `ValueError`가 발생한다.

## 비교 실험

`python scripts/run_experiment.py`는 기존 문항 단위 Random·Adaptive 기준선과 확률 보정 평가를 실행한다.
`python scripts/run_passage_experiment.py`는 합성 지문 은행, 사용자, 풀이 시점, 응답 난수를 공유하는 별도의 비교다.
각 정책은 동일한 초기 Elo에서 시작해 자신이 노출한 문항으로 갱신한다.

- **Random**은 미노출 지문을 균등 추출한다.
- **Legacy Adaptive**는 기존 개별 문항 규칙을 지문 단위로 적용한다. 목표 `0.70`에 가장 가까운 개별 문항을 찾고 그 지문의 세 문항을 제공한다.
- **Prediction Core V1**은 세 문항의 목표 거리와 콜드스타트·취약 스킬·커버리지 보너스를 사용한다.

`target_mae`는 공통 기준 `0.70`으로부터의 문항별 평균 절대 거리다. 콜드스타트 구간도 같은 기준으로 집계한다.
`coverage_gap`은 사용자별 최다·최소 스킬의 응답 비율 차이를 평균한 값이다. 작을수록 균형에 가깝다.
`cold_accuracy`는 사용자별 첫 6문항의 정답률이다.

기본 시드 42에서 정책별로 사용자 200명에게 지문 100편 중 16편씩 배정했다. 조건별 응답 수는 9,600건이다.

| 정책 | AUC | Log loss | Brier | ECE | 정답률 | 첫 6문항 정답률 | 목표 거리 ↓ | 커버리지 격차 ↓ |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Random | 0.7524 | 0.5932 | 0.2033 | 0.0355 | 0.5127 | 0.5042 | 0.2622 | 0.0769 |
| Legacy Adaptive | 0.7320 | 0.5896 | 0.2019 | 0.0290 | 0.5678 | 0.5742 | 0.1875 | 0.0795 |
| Prediction Core V1 | 0.6605 | 0.6167 | 0.2136 | 0.0283 | 0.6303 | 0.7142 | 0.1296 | 0.0657 |

시드 7에서도 V1의 목표 거리 `0.1356`과 커버리지 격차 `0.0679`가 세 정책 중 가장 작았고,
첫 6문항 정답률 `0.6917`이 가장 높았다. 시드 42의 V1은 Legacy Adaptive보다 log loss와 Brier가 높았다.
정책마다 노출 문항과 응답 분포가 달라지므로 예측 지표는 각 정책의 노출 조건에서 해석한다.
높은 첫 정답률은 더 풀기 쉬운 문항을 배정한 결과일 수 있다.

## 한계

- 설정값은 합성 실험에서 비교하기 위한 초기값이다. 선택 점수는 학습 효과의 추정치가 아니며, 실사용자 로그의 보정과 전이·지연 평가가 필요하다.
- 합성 IRT는 지문 내 문항의 공통 맥락 효과나 4지선다 추측을 모델링하지 않는다. 학습량은 풀이마다 주어진 상수다.
- 후보 검색은 전달된 후보 수에 비례한다. 후보군 선별, 노출 예약, 영속 저장, 중복 제출 방지와 트랜잭션은 호출 측의 후속 연동 범위다.
