# Prediction Service Workflow V1

`PredictionService`는 서버에서 채점한 학습 흐름을 기존 `LearningHistory`에 연결한다.
Elo, 순번, 지문 선택, 학습 이벤트와 성장 리포트는 기존 엔진에서 처리한다.
이 단계는 Python 애플리케이션 계층이며 실행 예제의 데이터는 합성 테스트 지문이다.

## 등록 및 공개 데이터

호출자는 Generation의 `GeneratedQuiz` 스키마와 `check_quiz()`로 검증한 JSON을
`register_quiz()`에 넘긴다. 함께 전달하는 `passage_body`는 같은 `passage_id`의 검수된 본문이다.
문항 ID는 지문 ID, 불변 출판 버전 `quiz_version`, 0부터 시작하는 문항 순서로 결정한다.
Generation의 `prompt_version`은 프롬프트 추적용이며 출판 버전은 호출자가 부여한다.
V1의 `item_version`은 해당 출판 버전과 같다. 본문·문항·선택지 순서·채점 키를 바꾸면
새 출판 버전을 등록한다. 신규 버전은 다음 추천에 사용하며 이전 노출의 채점 키는 보존한다.

`item_difficulties={0: 2}`처럼 서버가 정한 문항별 별점을 선택적으로 전달한다.
초기 prior는 Core의 문항별 별점, 지문 힌트, 중립값 순으로 적용된다.
동일 버전과 내용·유효 별점의 재등록은 같은 ID를 반환한다.
클라이언트에게는 지문 ID·버전·본문과 문항 ID·문제·선택지만 제공한다.
정답 인덱스, 해설, 근거 문장, 오답 설명은 공개 응답의 필드에 포함되지 않는다.

## Python 실행 흐름

1. `register_quiz()`로 검증된 퀴즈를 등록한다.
2. `recommend(user_id)`로 동일 Elo와 이력에 기반한 지문을 계산한다. 이 단계의 결과는
   `through_sequence`와 공개 퀴즈이며 후보가 소진되면 `quiz=null`이다.
3. 실제 제공이 확정되면 `confirm_exposure()`를 호출한다. 같은 노출 ID와 사용자·지문·버전이면
   원래 노출을 반환한다. 다른 ID로 같은 사용자에게 같은 지문을 재확정하면 충돌로 처리한다.
   비활성 버전에 대한 새 노출도 거부한다.
4. `submit_answer()`는 사용자·노출·문항·제출 ID와 선택지 인덱스를 받는다.
   서버의 정답 키로 채점하고, 이미 그 사용자의 유효 응답이 있는지 보고 재시도를 결정한다.
   최초 응답만 Elo를 갱신한다. 같은 제출 ID와 동일 선택값은 원래 결과를 반환한다.
   다른 오답 선택값으로 바꿔 재사용해도 충돌이다. 이미 승인된 재전송의 시각은 원래 기록을 보존한다.
5. `complete_learning()`은 그 노출의 세 문항에 유효 답안이 모두 있어야 완료한다.
   동일 노출 완료의 재전송은 원래 결과를 반환한다. 완료 뒤 새 제출은 거부한다.
6. `analyze()`는 지정한 `as_of`의 정답률·최초 풀이 수·재시도·주간 활동·스트릭·스킬별 θ를
   반환한다. `checkpoint()`와 `from_checkpoint()`는 기존 엔진의 복원 계약을 사용한다.

서비스 체크포인트에는 엔진 체크포인트, 퀴즈 등록 순서와 서버 채점 키, 제출별 선택값이 담긴다.
복원 시 버전별 문항과 채점 결과를 확인한다. **체크포인트는 서버 전용 데이터**다.
공개 응답이나 애플리케이션 로그에 넣지 않는다.

## FastAPI 연결을 위한 초안

아래 경로와 필드는 논의를 위한 예시다. 사용자 ID는 인증된 서버 문맥에서 얻고, 표에
생략한 `occurred_at`과 `applied_at`은 서버가 확정한다. 제출과 노출 ID의 발급 주체,
인증 방식, 공통 오류 형식과 DB 모델은 팀 리뷰에서 정한다.

| 동작 예시 | 요청 예시 | 응답 예시 | 실패 또는 빈 결과 |
| --- | --- | --- | --- |
| `GET /prediction/next` | 인증된 사용자 | `{"through_sequence":"0","quiz":{"passage_id":"p1","quiz_version":"v1","passage_body":"…","questions":[{"item_id":"q-…","stem":"…","options":["A","B","C","D"]}]}}` | 후보 소진 시 `quiz=null` |
| `POST /prediction/exposures` | `{"exposure_id":"x1","passage_id":"p1","quiz_version":"v1"}` | `{"exposure_id":"x1","sequence":"1","quiz":{…}}` | 비활성 버전, 지문 중복 노출, 노출 ID 충돌 |
| `POST /prediction/submissions` | `{"exposure_id":"x1","item_id":"q-…","submission_id":"s1","choice_index":0}` | `{"submission_id":"s1","is_correct":false,"is_retry":false,"sequence":"2"}` | 다른 사용자의 노출, 노출되지 않은 문항, 잘못된 선택지, 제출 ID 충돌, 완료된 노출의 새 답안 |
| `POST /prediction/exposures/x1/complete` | 인증된 사용자 및 노출 ID | `{"exposure_id":"x1","status":"completed","sequence":"5"}` | 노출 없음 또는 유효 답안 누락 |
| `GET /prediction/analytics?as_of=2026-01-04T15:00:00Z` | 기준 시각과 선택 시간대 | `{"summary":{…},"weekly":{…},"skills":{…},"through_sequence":"5"}` | 잘못된 시각·시간대, 기록 없는 사용자는 빈 통계 |

추천과 노출은 다른 시점에 일어난다. 한 서비스 인스턴스는 노출 확정 때 활성 버전과
사용자 노출 이력을 다시 검사하며, 동시 확정은 직렬화한다. 추천의 커서는 관측용이며
노출 예약 토큰으로 사용하지 않는다. 여러 프로세스에서는 저장소가 노출·제출의 고유성,
실제 제공과 이벤트의 경계, 전역 순번, 체크포인트와 후속 로그의 복구 경계를 보장해야 한다.
현재 경계는 단일 프로세스와 신뢰할 수 있는 서버 체크포인트이며, 기록 조회는 메모리
이력을 순회한다. 실제 서비스의 규모에 맞는 인덱스와 저장 방식은 후속 작업이다.

## 실행 및 검증

`ml/`에서 실행한다.

```text
python -m pytest
python scripts/run_service_workflow.py
python scripts/run_experiment.py
python scripts/run_passage_experiment.py
```

워크플로 테스트는 실제 Generation 스키마·검증 함수로 합성 지문을 확인한다.
스크립트는 두 사용자의 공유 문항 풀이, 오답과 재시도, 서울 자정 이후의 상태 복원과
다음 학습, 이전 제출 재전송을 재현한다. 중단 없이 실행한 경우와 복원 후의 체크포인트 및
리포트가 같아야 성공한다.

## PR #11·#12 병합 후

최신 `develop`에 원래 Core HEAD `cdf7e87`부터 통합 HEAD `fba9ddb`까지의
Analytics 차이와, `fba9ddb` 이후 이 브랜치의 워크플로 커밋을 옮긴다.
Core나 FastAPI 공통 기반의 원본 커밋을 중복 적용하지 않는다. 합의된 HTTP·영속화
어댑터를 붙이기 전 전체 Python 테스트와 기존 실험을 다시 실행한다.
