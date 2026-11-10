# Learning Analytics V1

## 범위와 현재 구조

`EloModel`의 공개 등록·조회·예측·갱신 메서드를 사용한다. `evaluate.run_online()`의 예측 후 갱신 순서를
서비스 이벤트에 적용한다. `simulate`는 합성 검증에 사용하고 기존 스킬 네 종류를 그대로 사용한다.
Prediction Core V1의 스냅샷, 보정도, 선택기는 별도 연동 범위다.

Expo 읽기 화면은 임시 정답을 로컬에서 판정하고 완료 표시를 저장한다. 홈은 이 표시로 연속 학습과 주간 상태를,
프로필은 고정 데이터로 주간 차트를 그린다. Generation 결과는 지문 ID와 프롬프트 버전, 문항 스킬을 제공한다.
Prisma에는 MySQL 연결이 선언돼 있으며, 학습 이벤트 테이블과 영속 처리 계약은 후속 작업이다.

## 처리 원칙

1. 초기 카탈로그에서 문항 ID·버전·스킬·별점을, 온보딩에서 사용자 prior를 준비한다. 문항 ID는 버전별로 고유하며
   여러 사용자가 같은 문항 버전을 풀면 같은 Elo 난이도를 공유한다.
2. 실제로 제공한 지문과 문항 목록만 노출로 기록한다. 서버가 채점을 확정하면 그 결과를 답안 이벤트로 전달한다.
   한 사용자와 문항 버전의 첫 유효 응답만 Elo를 갱신한다. 재노출 이후의 후속 응답도 재시도로 분류한다.
3. 노출의 모든 문항에 유효 응답이 있으면 완료 이벤트를 수락한다. 오답도 유효 응답이다.
   중단은 별도의 종료 상태이며 주간 완료와 연속 학습 집계에서 제외된다.
4. 단일 엔진이 전 사용자의 이벤트를 처리한다. 신규 이벤트의 UTC 시간이 이전 신규 이벤트보다 이르면 거부한다.
   재생은 UTC 시간으로 안정 정렬하며, 같은 시각의 인과 순서는 입력 배열이 정한다.
   수락된 이벤트만 기록한다. 정확한 재전송은 같은 결과를 반환하고, ID 충돌은 오류로 처리한다.
5. 사용자 리포트는 지정된 기준 시각까지의 이벤트만 읽는다. 기본 표시는 서울 시간, 주간은 월요일부터 일요일이다.
   완료일이 오늘 또는 어제인 연속 구간을 현재 스트릭으로 계산한다. 기록이 없는 날은 0건으로 표시한다.
   스킬별 변화량은 해당 주 시작 직전 추정치와 기준 시각의 추정치 차이다. 표본 기준은 참고용으로만 사용한다.

## V1 입력 스키마

모든 이벤트는 `version=1`, `type`, `event_id`, `user_id`, `exposure_id`, `occurred_at`을
포함한다. ID는 공백으로 시작하거나 끝나지 않는 비어 있지 않은 문자열이다. 시각은 초 단위까지 표현한
ISO 8601 문자열이며 `Z` 또는 `±HH:MM` 오프셋이 필요하다. 소수 초는 최대 6자리다.
출력의 시각은 UTC로 정규화한다. 알 수 없는 필드, 누락 필드, 지원하지 않는 버전은 거부한다.

| 유형 | 추가 필드 |
| --- | --- |
| `exposure` | `passage_id`, `quiz_version`, 중복 없는 비어 있지 않은 `item_ids`, 선택 사항 `policy_version` |
| `submission` | `submission_id`, `passage_id`, `item_id`, `item_version`, `skill`, 서버 확정 불리언 `is_correct`, `is_retry`, 선택 사항 `hint_used` |
| `completion` | `status`에 `completed` 또는 `abandoned`를 사용한다. 두 상태 모두 해당 노출을 종료한다. |

```json
[
  {"version":1,"type":"exposure","event_id":"e1","user_id":"u1","exposure_id":"x1","occurred_at":"2026-01-05T10:00:00+09:00","passage_id":"p1","quiz_version":"quiz-v1","item_ids":["q1-v1"],"policy_version":"reading-v1"},
  {"version":1,"type":"submission","event_id":"e2","user_id":"u1","exposure_id":"x1","occurred_at":"2026-01-05T10:01:00+09:00","submission_id":"s1","passage_id":"p1","item_id":"q1-v1","item_version":"v1","skill":"fact","is_correct":true,"is_retry":false,"hint_used":false},
  {"version":1,"type":"completion","event_id":"e3","user_id":"u1","exposure_id":"x1","occurred_at":"2026-01-05T10:02:00+09:00","status":"completed"}
]
```

## 처리 및 재생 인터페이스

```python
from neuroknot_ml.learning_analytics import analyze_user
from neuroknot_ml.learning_history import CatalogItem, LearningHistory

items = [CatalogItem("q1-v1", "v1", "fact", difficulty=3)]
history = LearningHistory(items)
for event in events:  # 위 JSON을 파싱한 이벤트 목록
    record = history.apply(event)
    print(record.to_dict())  # 답안이면 예측 확률, 갱신 전후 θ·b, Elo 갱신 여부 포함

replayed = LearningHistory.replay(items, history.event_log())
report = analyze_user(replayed, "u1", as_of="2026-01-05T02:00:00Z")
```

- 같은 `event_id`와 정규화된 내용이 다시 도착하면 기존 결과를 반환한다. 같은 제출 ID의 동일한 내용은
  새 이벤트 ID로 도착해도 같은 결과를 반환하고, 그 ID도 재생 로그에 보존한다. 노출 ID와 노출의 종료 이벤트에도 같은 원칙을 적용한다.
  내용이 달라지면 `EventConflictError`가 발생한다.
- 다른 제출 ID의 재시도는 이력에 남긴다. `is_retry`와 기록된 첫 응답 여부가 다르면 거부한다.
  유효한 재시도에는 당시 Elo 예측을 기록하고, 전후 θ와 b는 같다. 힌트 사용 여부는 기록하며 첫 유효 응답의 Elo 반영 기준은 같다.
- 등록되지 않은 문항, 노출과 맞지 않는 사용자·지문·문항, 카탈로그와 다른 버전·스킬, 종료 후 신규 답안,
  선행 이벤트가 없는 답안·종료는 `EventValidationError`로 거부한다.
- `records`는 집계 대상인 논리적 이벤트를 한 번씩 제공한다. `event_log()`는 정규화된 JSON 재생 입력이며
  수락한 별칭 ID까지 제공한다. 재생은 같은 초기 카탈로그·온보딩과 전체 사용자 로그를 사용한다.
  카탈로그는 생성 시 고정되며, 하나의 문항 ID에는 한 버전만 연결된다.

## 리포트 및 화면 매핑

`analyze_user()`는 명시한 `as_of`까지 읽는다. 예시의 답안 1건으로 생성한 응답 일부는 다음과 같다.

```json
{
  "version": 1,
  "user_id": "u1",
  "timezone": "Asia/Seoul",
  "data_status": "available",
  "summary": {"first_attempts": 1, "correct_first_attempts": 1, "observed_accuracy": 1.0, "retries": 0, "exposures": 1, "exposed_passages": 1, "completed_sessions": 1},
  "weekly": {"week_start": "2026-01-05", "first_attempts": 1, "completed_sessions": 1, "streak_days": 1},
  "skills": {"fact": {"attempts": 1, "theta": 0.4, "previous_theta": 0.0, "theta_change": 0.4, "status": "insufficient_data"}}
}
```

- Expo 프로필의 고정 학습량 차트는 `weekly.days[].first_attempts`를 사용한다. 각 항목에 현지 날짜와
  완료 수가 있고, 이번 주 월요일부터 일요일까지 7개 항목을 반환한다. 홈의 요일별 완료 표시에는
  `completed_sessions > 0`, 홈·프로필의 연속 학습에는 `weekly.streak_days`를 사용한다.
- 관측 정답률은 최초 유효 응답 중 정답 비율이며, 분모가 0이면 `null`이다. 재시도, 중단, 단순 노출은
  완료일로 집계하지 않는다. 노출 수와 서로 다른 지문 수를 따로 제공한다.
- `skills`에는 네 스킬이 항상 들어 있다. `theta_history`는 최초 응답별 추정값을 담는다.
  해당 주 첫 응답의 갱신 전 θ를 주 시작 기준으로 삼고, 해당 주 응답이 없으면 기존 추정치의 변화량은 0이다.
  관측이 전혀 없는 스킬의 θ와 변화량은 `null`이다. 기본 5회는 이력 충분 여부를 표시하는 규칙이다.
  `observed` 상태와 θ 변화량은 신뢰구간, 유의성 또는 실제 학습 효과를 뜻하지 않는다.

## NestJS·Prisma 연동 경계

서버가 사용자 ID와 문항 버전을 확인하고, 정답 여부·최초 또는 재시도 분류·확정 시각을 기록한다.
이벤트에는 정답 인덱스, 선택지, 해설을 저장하지 않는다. Prisma 연동 시 ID 고유 제약과
이벤트·Elo 상태의 원자적 쓰기, 같은 문항 상태의 동시 갱신 제어, 전역 순서 보존이 필요하다.
현재 엔진은 한 프로세스에서 같은 카탈로그와 온보딩 설정으로 처리·재생하는 구조다.

NestJS는 실제 노출을 확정한 후 이벤트를 생성하고, 서버가 확정한 채점 결과와 완료 상태를 전달한다.
DB에서는 이벤트 및 업무 ID의 중복 처리와 동시각 이벤트의 순번을 보존해야 한다.
늦게 도착한 새 이벤트는 현재 처리기에서 거부하며, 과거 기록 반영은 전역 로그를 재구성한 뒤 재생해야 한다.
실서비스에서는 리포트 조회 시 전체 이력을 스캔하는 비용과 장기 θ 시계열 보관 정책도 검토해야 한다.

## 재현성 검증

`python -m pytest`는 합성 시드 0, 7, 42에서 JSON 로그 재생과 순차 처리 결과를 비교한다.
전 사용자 공용 문항 난이도, 각 최초 응답의 예측과 갱신 전후 상태, 리포트, 미래 응답 추가 전후의 기존 기록을 검증한다.
`python scripts/run_experiment.py`는 기존 Elo·IRT 실험을 실행한다.
`python scripts/run_learning_analytics.py --seed 42`는 독립 JSON 예제를 출력한다.
