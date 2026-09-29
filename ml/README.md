# neuroknot_ml — 슬라이스 3 (성장 예측) 실험 패키지

## 목적

실제 유저 데이터가 없는 지금, **정답(진짜 실력 θ)을 아는 가상 데이터**를 만들어
예측 모델이 유저 실력을 제대로 추정하는지 검증한다.

1. IRT(1PL) 시뮬레이터로 유저·문제·풀이 기록을 만든다. 유저의 진짜 θ와 문제의 진짜 난이도 b를 알고 있다.
2. 모델(Elo, baseline, oracle)에 풀이 기록을 시간 순서대로 넣는다. 매 풀이마다 **예측 먼저 → 결과 보고 갱신**.
3. 세 가지를 본다.
   - 예측력: AUC, log loss, Brier score (전체 / 유저별 첫 10문제 콜드스타트 구간)
   - 보정도(calibration): 예측 확률 70%인 문제를 실제로 70% 맞히는지
     - ECE (Expected Calibration Error): 예측 확률을 10개 구간으로 나눠, 구간별 |예측 평균 - 실제 정답률|을 개수로 가중 평균. 0에 가까울수록 좋다
     - 신뢰도 표 (`reliability_table`): 구간별 예측 평균, 실제 정답률, 개수
     - 전체 평균 예측 vs 실제 정답률 (`calibration_in_the_large`)
     - 신뢰도 그래프: `run_experiment.py`가 `ml/results/reliability_{random,adaptive}.png`로 저장 (git에는 안 올림)
   - θ 복원력: 진짜 θ와 모델 추정치의 Spearman 상관

ECE만으로는 부족하다. 모두에게 전체 평균을 예측하는 `global_mean`도 ECE는 낮다.
보정도는 "예측이 믿을 만한가", log loss와 θ 복원력은 "예측이 쓸모 있는가"를 본다고 생각하고 함께 읽는다.

`oracle`은 시뮬레이터의 진짜 확률 P = sigmoid(θ - b)로 예측하는 상한선이다. 어떤 모델도 이 값을
기대값 기준으로 넘을 수 없으므로, 다른 모델의 지표는 oracle 대비 어디쯤인지로 읽는다.

### 문제 배정 방식 (`SimulationConfig.selection`)

- `random`: 유저마다 안 푼 문제를 무작위 순서로 푼다.
- `adaptive`: 매 풀이마다 그 시점 Elo 추정치로 예상 정답률이 `target_p`(0.7)에 가장 가까운 문제를 고른다.
  실서비스의 적응형 추천을 흉내 낸 것으로, 배정 → 풀이 → Elo 갱신이 모든 유저에 걸쳐 시각 순으로 번갈아 일어난다.

같은 seed면 두 모드의 유저/문제/풀이 시각/정답 노이즈가 같고 배정만 다르다.

**적응형(adaptive)에서는 AUC 대신 보정도와 θ 복원력을 본다.** 문제를 골라 준 Elo와 평가하는 Elo가
같은 모델이라, 평가 대상 Elo의 예측이 거의 항상 0.7 근처에 모인다. 그래서 AUC는 구조적으로 낮게 나온다
(oracle의 AUC 상한도 함께 낮아진다). 적응형 배정에서 중요한 건 "70%라고 보고 고른 문제를 실제로 70% 맞히는가"이므로
ECE와 신뢰도 표(특히 0.6~0.8 구간)로 보정도를 확인하고, θ 복원력으로 실력 추정이 맞는지를 확인한다.

나중에 FastAPI 백엔드에서 import해서 쓸 수 있도록 웹 프레임워크/DB 의존 없이 순수 함수·클래스로만 작성했다.

## 구조

```
ml/
├── neuroknot_ml/
│   ├── skills.py     # 스킬 목록 (fact, inference, vocab, main_idea) — Day 0 확정 전 임시값
│   ├── simulate.py   # IRT(1PL) 시뮬레이터 (random / adaptive 배정) → users / user_skills / items / attempts
│   ├── elo.py        # 유저-스킬별 Elo + 문제 난이도 동시 갱신, 풀이 수에 따라 줄어드는 K
│   ├── baselines.py  # 전체 평균 정답률, 유저별 누적 정답률, oracle(진짜 확률) 상한선
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
python scripts/run_experiment.py          # 유저 200명, 문제 300개로 random/adaptive 두 조건 모델 비교
python scripts/run_experiment.py --seed 7 --learning-rate 0   # 시드 변경, 학습 효과 끄기
```

Windows 콘솔에서 한글이 깨지면 `PYTHONIOENCODING=utf-8`을 설정한다.
