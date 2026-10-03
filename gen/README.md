# neuroknot_gen — 슬라이스 2 (문항·해설 생성)

지문 한 편을 받아 **문항 3개와 선택지별 해설**을 만들고, 사람이 보기 전에
기계가 먼저 품질을 검사한다.

## 왜 미리 만들어 두는가

사용자가 답을 고를 때마다 모델을 부르면 ① 몇 초씩 기다려야 하고 ② 사용자가 늘수록
비용이 비례해 커지며 ③ 이상한 해설이 나와도 이미 사용자가 본 뒤다.

4지선다는 한 문항에 나올 수 있는 해설이 최대 4개뿐이므로, **문항을 만들 때
선택지별 해설까지 한꺼번에 만들어 둔다.** 그러면 앱에서는 조회만 하면 되고,
품질 검사를 사용자 노출 이전에 끝낼 수 있다.

```
[지문] → 프롬프트 조립 → Claude 호출 → 자동 검사 → (실패 시 1회 재생성) → out/ 저장
                                                                    ↓
                                       앱: 문항 조회 / 채점 후 해당 선택지의 해설 표시
```

## 설치와 실행

사용하는 모델은 **Google Gemini**다. (`generate.py` 한 파일만 바꾸면 다른 회사
모델로 교체할 수 있다.)

```bash
cd gen
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt

cp .env.example .env      # 그리고 .env 에 GEMINI_API_KEY 값을 채운다
```

키는 [Google AI Studio](https://aistudio.google.com/apikey)에서 발급한다.

```bash
./.venv/bin/python scripts/check_setup.py                    # 키·모델·지문 점검
./.venv/bin/python scripts/run_generate.py fx-001            # 한 편
./.venv/bin/python scripts/run_generate.py --all             # 전체
./.venv/bin/python scripts/run_generate.py fx-001 --dry-run  # 호출 없이 프롬프트만 확인
./.venv/bin/python -m pytest                                 # 검사기 테스트
```

`--dry-run`과 `pytest`는 API 키가 없어도 동작한다. 프롬프트를 고친 뒤 **모델에
실제로 무엇이 전달되는지 먼저 눈으로 확인**하는 용도다.

모델 이름은 수시로 바뀌므로 코드에 고정하지 않았다. `check_setup.py`가 계정에서
쓸 수 있는 이름을 출력하니, 거기서 골라 `.env`의 `GEMINI_MODEL`에 넣으면 된다.

## 구조

```
gen/
├── fixtures/                샘플 지문 (출처·이용 조건은 fixtures/README.md)
├── neuroknot_gen/
│   ├── skills.py            스킬 4종 + 오답 유형 5종
│   ├── schemas.py           문항·해설 데이터 형식 (Pydantic)
│   ├── prompts/quiz_v1.md   출제 지침 — 앞으로 계속 고쳐 나갈 파일
│   ├── loader.py            지문 읽기 (나중에 DB 조회로 교체)
│   ├── generate.py          Gemini 호출 — 모델을 바꾸려면 이 파일만 고친다
│   └── validate.py          자동 검사
├── scripts/
│   ├── check_setup.py       키·모델·지문 점검
│   └── run_generate.py      실행 진입점
├── out/                     생성 결과 (커밋하지 않음)
└── tests/
```

## 스킬과 오답 유형은 다른 개념이다

| | 스킬 (skill) | 오답 유형 (error_type) |
| --- | --- | --- |
| 붙는 곳 | 문항마다 하나 | 틀린 선택지마다 하나 |
| 뜻 | 이 문항이 무엇을 측정하는가 | 이걸 고른 사람이 어떤 실수를 했는가 |
| 쓰는 곳 | 슬라이스 3이 스킬별로 실력 추정 | 취약점 분석, 다음 지문 추천 |

틀린 선택지를 만들 때 "이런 식으로 잘못 읽은 사람이 고를 법한" 선택지를 의도적으로
설계하고 유형을 미리 붙여 둔다. 그러면 사용자가 그 선택지를 고르는 순간,
**추가 호출 없이 오답 원인이 확정된다.**

> 스킬 목록은 `ml/neuroknot_ml/skills.py`(슬라이스 3)와 같아야 한다.
> 바꿀 때는 협업 가이드 6절에 따라 팀 합의가 필요하다.

## 자동 검사가 보는 것

선택지 개수나 번호 범위처럼 형식으로 정해지는 것은 Pydantic이 막는다.
`validate.py`는 **지문과 대조해야만 알 수 있는 것**을 본다.

- **근거 문장이 지문에 실제로 있는가** (공백 차이는 무시) — 환각을 잡는 핵심 검사
- 문제 문장에 정답 표현이 그대로 노출되지 않았는가
- 오답 설명이 정답을 제외한 세 선택지를 정확히 한 번씩 가리키는가
- 선택지가 중복되지 않는가, 해설이 지나치게 짧지 않은가
- 문항 3개가 서로 다른 스킬을 측정하는가

검사에 걸리면 문제 목록을 프롬프트에 덧붙여 **한 번만** 다시 만들고,
그래도 걸리면 저장하지 않는다.

## 아직 하지 않은 것

- 평가 세트 (고정 지문 20편 + 채점표). 프롬프트를 고쳤을 때 좋아졌는지를
  숫자로 확인하려면 필요하다.
- DB 저장과 API. FastAPI 골격이 생긴 뒤 `loader.py`와 저장 부분만 바꾼다.
- 개인화 해설 (학습자의 과거 오답 이력 반영). v1은 지문만 근거로 한다.
