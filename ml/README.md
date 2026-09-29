# neuroknot_ml — 슬라이스 3 (성장 예측) 실험 패키지

## 목적

실제 유저 데이터가 없는 지금, **정답(진짜 실력 θ)을 아는 가상 데이터**를 만들어
예측 모델이 유저 실력을 제대로 추정하는지 검증한다.

1. IRT(1PL) 시뮬레이터로 유저·문제·풀이 기록을 만든다. 유저의 진짜 θ와 문제의 진짜 난이도 b를 알고 있다.
2. 모델(Elo, baseline)에 풀이 기록을 시간 순서대로 넣는다. 매 풀이마다 **예측 먼저 → 결과 보고 갱신**.
3. 두 가지를 본다.
   - 예측력: AUC, log loss, Brier score (전체 / 유저별 첫 10문제 콜드스타트 구간)
   - θ 복원력: 진짜 θ와 모델 추정치의 Spearman 상관

나중에 FastAPI 백엔드에서 import해서 쓸 수 있도록 웹 프레임워크/DB 의존 없이 순수 함수·클래스로만 작성했다.

## 구조

```
ml/
├── neuroknot_ml/
│   ├── skills.py     # 스킬 목록 (fact, inference, vocab, main_idea) — Day 0 확정 전 임시값
│   ├── simulate.py   # IRT(1PL) 시뮬레이터 → users / user_skills / items / attempts DataFrame
│   ├── elo.py        # 유저-스킬별 Elo + 문제 난이도 동시 갱신, 풀이 수에 따라 줄어드는 K
│   ├── baselines.py  # 전체 평균 정답률, 유저별 누적 정답률
│   └── evaluate.py   # 온라인 평가(run_online), 지표(score), θ 복원력(theta_recovery)
├── scripts/run_experiment.py
└── tests/
```

모든 모델은 같은 인터페이스를 따른다.

```python
model.predict(user_id, item_id) -> float      # 정답 확률
model.update(user_id, item_id, is_correct)    # 결과 반영 (갱신 전 예측 확률 반환)
```

`EloModel`은 문제의 스킬을 알아야 하므로 먼저 `register_item(item_id, skill, difficulty)`로 등록하고,
유저는 `register_user(user_id, onboarding_level)`로 등록하면 온보딩 레벨 prior에서 시작한다.

## 임시값 (Day 0에 확정/재추정 필요)

| 항목 | 위치 | 값 |
| --- | --- | --- |
| 스킬 목록 | `skills.py` | fact, inference, vocab, main_idea |
| 온보딩 레벨 prior | `elo.DEFAULT_LEVEL_PRIOR` | warming_up -1.0, cruising -0.3, high_speed 0.3, autonomous 1.0 |
| 별 개수 → 난이도 prior | `elo.DEFAULT_STAR_PRIOR` | 1★ -1.6, 2★ -0.8, 3★ 0.0, 4★ 0.8, 5★ 1.6 |
| K 스케줄 | `elo.DEFAULT_USER_K`, `DEFAULT_ITEM_K` | 유저 0.8/(1+0.1n), 최소 0.1 · 문제 0.4/(1+0.1n), 최소 0.05 |

## 실행 방법

```bash
cd ml
python -m venv .venv
.venv/Scripts/activate        # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

pytest                                    # 테스트
python scripts/run_experiment.py          # 유저 200명, 문제 300개로 모델 비교
python scripts/run_experiment.py --seed 7 --learning-rate 0   # 시드 변경, 학습 효과 끄기
```

Windows 콘솔에서 한글이 깨지면 `PYTHONIOENCODING=utf-8`을 설정한다.
