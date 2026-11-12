"""Render the research report entirely from committed artifacts + reviewed findings."""
from pathlib import Path
import json
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
A = ROOT/'research_v2/artifacts'
NAMES = ['v1','random','target_only','no_weakness','no_coverage','no_bonuses','no_cold']


def table(headers, rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |',
        *['| '+' | '.join(map(str,row))+' |' for row in rows]])+'\n'


def main():
    summaries = {phase:pd.read_csv(A/f'{phase}_summary.csv').set_index(['variant','metric'])
                 for phase in ['tune','validate','learning','replay']}
    paired = pd.read_csv(A/'validate_paired.csv').set_index(['variant','metric'])
    frozen = json.loads((A/'frozen_candidates.json').read_text())
    names = list(dict.fromkeys(NAMES+frozen['candidates']))
    def fmt(name,metric,phase='validate',ci=False):
        row = summaries[phase].loc[(name,metric)]
        if ci:
            return f'{row["mean"]:.5f} [{row.ci_low:.5f}, {row.ci_high:.5f}]'
        return f'{row["mean"]:.5f} ± {row.sd:.5f}'
    def delta(name,metric):
        row = paired.loc[(name,metric)]
        return f'{row["mean"]:+.5f} [{row.ci_low:+.5f}, {row.ci_high:+.5f}]'
    sections = []
    sections.append('''# Prediction Model Research V2 — 1단계

이 연구는 V2 모델의 우월성을 주장하지 않는다. 기존 Elo 수식·정책의 운영 기본값·PredictionService 공개 계약은 그대로 두고, 평가 방법과 정책 구성요소, 설정 민감도를 연구했다. 모든 추가 코드는 `ml/` 안에 있다.

기준 커밋은 `origin/fix/pred-review-hardening`의 `d17ac32`, 연구 브랜치는 `research/pred-model-evaluation-v2`다. 아래 숫자는 저장된 합성 실험 결과이며 실제 사용자 성능이 아니다. 표의 ±는 **시드 간 표본 SD**, 대괄호는 **시드 단위 Student-t 95% 신뢰구간**이다. 같은 응답을 독립 표본처럼 세어 CI를 축소하지 않았다.

## 1. V1 재현과 문제 정의

출처: [기존 지문 실험 원문](research_v2/artifacts/baseline_passage.txt), [문항 실험 원문](research_v2/artifacts/baseline_item.txt). 재현: `cd ml; python scripts/run_passage_experiment.py`, `python scripts/run_experiment.py`.

기본 조건(시드 42, 사용자 200명, 지문 100개, 16라운드, 학습률 0.01)의 정책별 9,600응답 결과는 기존 `PREDICTION_CORE_V1.md`와 소수점 네 자리까지 일치했다.

| 정책 | AUC | Log loss | Brier | ECE | 정답률 | 첫 6개 정답률 | 예측 목표 거리 | 커버리지 격차 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Random | .7524 | .5932 | .2033 | .0355 | .5127 | .5042 | .2622 | .0769 |
| Legacy Adaptive | .7320 | .5896 | .2019 | .0290 | .5678 | .5742 | .1875 | .0795 |
| V1 | .6605 | .6167 | .2136 | .0283 | .6303 | .7142 | .1296 | .0657 |

시드 7 재현도 [별도 원문](research_v2/artifacts/baseline_passage_seed7.txt)에 보존했다 (`python scripts/run_passage_experiment.py --seed 7`). V1이 더 목표에 가까운 문항을 선택하지만 관측 AUC/Brier가 불리한 사실은, 서로 다른 문항의 응답 분포를 평가하므로 모델의 열등함을 입증하지 않는다. Brier는 불가약 응답 분산에도 영향을 받으며 AUC는 노출 범위가 좁아질 때 낮아질 수 있다.

## 2. 실제 구현 조사

| 코드 | 현재 동작 | 평가에서 주의할 점 |
|---|---|---|
| `neuroknot_ml/elo.py` | sigmoid(θ−b), 잔차로 θ/b를 반대 방향 갱신. 사용자·문항별 누적 횟수 K. 생성자에서 prior/K 주입 가능 | 새 주입 인터페이스나 운영 변경 불필요. θ와 b의 공통 이동은 확률에서 식별되지 않음 |
| `neuroknot_ml/selection.py` | 세 문항의 목표 절대 거리 + 취약 스킬 + 커버리지. 첫 6응답 목표 .8, 이후 .7. 사용자·지문 SHA-256 동점 처리 | 콜드 구간에는 취약 가산점 비활성. 커버리지는 계속 적용. 목표 적합도만/두 가산점 제거는 cold 유지 여부로 구분 |
| `neuroknot_ml/simulate.py` | 1PL 합성 θ/b, noisy onboarding, 실제 b를 구간화한 별점. 스킬당 응답 시 고정 학습량 | 모델과 생성기 수식 일치. 별점은 실제 서비스보다 좋은 신호일 수 있음. 학습 증가량 자체는 정책·정오답·난이도와 무관 |
| `neuroknot_ml/evaluate.py` | 온라인 예측 후 갱신, AUC/log loss/Brier/ECE, θ Spearman | θ 절대 오차와 b 오차, 공통 평가가 없었음. ECE는 10개 등간격 bin이며 표본/범위에 민감 |
| `neuroknot_ml/passage_experiment.py` | 정책별 별도 Elo, 동일 사용자/지문/시각/응답 uniform. 관측 응답만 집계 | target_mae는 실제 확률 아닌 예측값과 .7의 거리. cold_accuracy는 6개 기준. 정책별 노출 차이는 남음 |

기존 문항 평가의 콜드 기준은 10개, 지문 정책은 6개다. 연구에서는 6개로 고정했다. 기존 코드/문서는 변경하지 않았다.

## 3. 평가 설계와 누출 방지

출처: [사전 계획](research_v2/PLAN.md), [설정·환경 manifest](research_v2/artifacts/tune_manifest.json), [연구 코드](research_v2/experiment.py), [검증 manifest](research_v2/artifacts/validate_manifest.json). 재현: `python -m research_v2.run --phase tune`, 이후 `--phase validate`.

- 시드당 사용자 60명, 훈련 지문 60개/문항 180개, 16라운드/사용자 48응답. 기존 전체 크기 재현과 별도로 탐색 계산량을 제한했다.
- 탐색 시드 11/29/47, 검증 시드 101/211/307/401/503. 사용자·은행·풀이 시각·각 시각의 세 응답 uniform을 정책 간 공유한다. 문항별 잠재 응답이 동일하다는 뜻은 아니다.
- 주 분석 학습률은 0: 모든 정책에서 같은 실제 θ로 공통 평가가 가능하다. 0.01은 별도 강건성 분석으로만 사용한다.
- 독립 RNG의 공통 미학습 문항 40개(각 스킬 10개)를 등록하되 후보군에는 넣지 않는다. 사용자 0/6/48응답 시점에 상태를 읽고 평가할 뿐 업데이트하지 않는다. 같은 시드/사용자/시점/문항은 같은 평가 uniform을 사용한다.
- 같은 사용자 이력 길이의 실제 시각에 평가한다. 마지막 공통 평가는 각 사용자의 마지막 응답 직후이지 전체 사용자 학습 종료 후의 일괄 평가가 아니다. 전체 이벤트 순서/시각은 정책 간 같다.
- 훈련 갱신에는 선택된 현재 문항의 정오답만 전달한다. 등록에는 ID/스킬/별점/온보딩만 전달한다. 잠재 θ/b, 미학습 평가 응답, 미사용 source 응답은 모델/정책에 전달하지 않는다.
- 공통 Brier/AUC/log loss/ECE는 같은 평가 문항과 라벨을 사용한다. 추가로 `probability_mse=mean((p−p_true)^2)`와 `expected_brier=probability_mse+mean(p_true(1−p_true))`를 evaluator에서만 계산한다. 확률 MSE는 기대 Brier의 oracle 대비 초과분이다.
- 미학습 문항 b는 prior로 고정된다. 따라서 공통 평가는 **미학습 문항 일반화**이고, 학습된 문항 b의 개선을 직접 평가하지 않는다. 별도로 훈련 문항 전체/노출 문항/미학습 문항의 b RMSE를 저장한다.
- θ RMSE는 사용자×스킬, 사용자 스킬평균, 스킬별로 저장한다. raw logit 오차이며 gauge 정렬을 하지 않는다. 확률 MSE를 함께 봐야 한다.
- 정책 품질은 예측/실제 확률과 고정 .7 사이 평균 절대 거리, 실제 정답률, 첫 6개 정답률, cold 실제 확률과 .8 거리, 적용 설정 목표 거리, 사용자별 커버리지 격차 `(max count−min count)/total`로 평가한다. 목표 후보를 자기 목표만으로 유리하게 평가하지 않는다.
- 초기 관측 구간은 n_prior<6, 후기 구간은 n_prior≥30이다. 최대 48응답은 수렴이나 장기 학습 완료를 보장하지 않는다.

## 4. 정책 Ablation: 예측과 추천 성능을 분리

`no_bonuses`는 cold 목표 전환을 유지한다. `target_only`는 두 가산점과 cold 전환을 모두 제거한다. `no_cold`는 두 가산점을 유지하며 cold 전환/취약 보너스 억제를 제거한다. 나머지 값은 V1과 같다.

출처: [독립 검증 시드별 수치](research_v2/artifacts/validate_seeds.csv), [평균·분산·CI](research_v2/artifacts/validate_summary.csv). 재현: `python -m research_v2.run --phase validate`.

### 정책별 관측 예측 지표 — 노출 집합이 다름
''')
    sections.append(table(['정책','AUC','Log loss','Brier','ECE'],[[n,*[fmt(n,m) for m in ['observed_auc','observed_log_loss','observed_brier','observed_ece']]] for n in NAMES]))
    sections.append('### 공통 미학습 평가 — 같은 문항/라벨, 48응답 직후\n')
    sections.append(table(['정책','AUC','Log loss','Brier','ECE','확률 MSE'],[[n,*[fmt(n,'common_48_'+m) for m in ['auc','log_loss','brier','ece','probability_mse']]] for n in NAMES]))
    sections.append('### 추천 정책 지표\n')
    sections.append(table(['정책','예측→.7 거리','실제확률→.7 거리','정답률','첫 6개 정답률','커버리지 격차'],[[n,*[fmt(n,m) for m in ['target_pred_mae','target_true_mae','accuracy','cold_accuracy','coverage_gap']]] for n in NAMES]))
    sections.append('### 동일 시드 V1 대비 차이와 95% CI\n\n음수는 해당 오차/격차 감소다. 시드가 적고 다중 비교 보정을 하지 않았으므로 탐색적 증거로 해석한다. 출처: [paired 결과](research_v2/artifacts/validate_paired.csv), 재현 명령은 위와 같다.\n')
    sections.append(table(['구성','공통 Brier Δ','실제 목표거리 Δ','커버리지 Δ'],[[n,*[delta(n,m) for m in ['common_48_brier','target_true_mae','coverage_gap']]] for n in NAMES if n!='v1']))
    sections.append('''## 5. 하이퍼파라미터 민감도

출처: [탐색 시드 원자료](research_v2/artifacts/tune_seeds.csv), [탐색 통계](research_v2/artifacts/tune_summary.csv), [정확한 후보 설정](research_v2/artifacts/tune_manifest.json). 재현: `python -m research_v2.run --phase tune`.

총 31설정×3시드의 제한적 단변량 비교다. 기본 일반/초기 목표 .7/.8, cold 횟수 6, 취약/커버리지 가중치 .2/.15를 중심으로 탐색했다. 사용자 K는 max(.1,.8/(1+.1n)), 문항 K는 max(.05,.4/(1+.1n)). `scale`은 k0와 k_min을 함께 곱하고 decay를 고정한다. `decay`는 분모의 감소율만 바꾼다. `level_scale`/`star_scale`은 기존 각 prior를 곱하며 0은 prior 제거다. `target_080`에서는 cold 목표와 일반 목표가 같아지는 특성이 있다. 상세 숫자는 manifest가 기준이다.

아래 결과는 **튜닝 데이터**이며 독립 검증 결과와 섞지 않는다.
''')
    tuning = pd.read_csv(A/'tune_seeds.csv').variant.drop_duplicates().tolist()
    sections.append(table(['설정','공통 확률 MSE','θ RMSE','훈련 b RMSE','커버리지 격차'],[[n,*[fmt(n,m,'tune') for m in ['common_48_probability_mse','theta_48_rmse','b_train_rmse','coverage_gap']]] for n in tuning]))
    sections.append('''비-Ablation 후보 중 공통 확률 MSE 상위 두 개, 커버리지 격차 최저 한 개를 사전 규칙으로 선택했다. [고정 후보와 튜닝 CSV hash](research_v2/artifacts/frozen_candidates.json)는 검증을 시작하기 전에 커밋했다. 후보는 '''+', '.join(frozen['candidates'])+'''다. 검증 시드 결과로 재튜닝하거나 추가 조합을 만들지 않았다.

### 고정 후보의 독립 검증

출처: `validate_summary.csv`, `validate_paired.csv`; 재현: `python -m research_v2.run --phase validate`.
''')
    sections.append(table(['후보','공통 확률 MSE','공통 Brier Δ [CI]','θ RMSE','커버리지 Δ [CI]'],[[n,fmt(n,'common_48_probability_mse'),delta(n,'common_48_brier'),fmt(n,'theta_48_rmse'),delta(n,'coverage_gap')] for n in frozen['candidates']]))
    sections.append('''### 같은 V1 로그를 학습하는 추정기 전용 비교

정책 설정 후보가 다른 데이터를 모으는 효과와 모델 설정 효과를 구분하기 위해, 각 검증 시드의 V1 로그를 그대로 재학습했다. 후보 모델은 추천에 관여하지 않고 현재 관측 라벨로만 갱신한다. 이 추가 진단은 후보 고정 후 수행했으며 후보 재선정에 쓰지 않았다. 커버리지 후보는 Elo 설정이 같으므로 동일 로그에서는 V1과 정확히 같아야 한다.

출처: [replay 원자료](research_v2/artifacts/replay_seeds.csv), [paired CI](research_v2/artifacts/replay_paired.csv), [설정](research_v2/artifacts/replay_manifest.json). 재현: `python -m research_v2.replay`.
''')
    sections.append(table(['모델 설정','공통 확률 MSE','공통 Brier','θ RMSE','훈련 b RMSE'],[[n,*[fmt(n,m,'replay') for m in ['common_48_probability_mse','common_48_brier','theta_rmse','b_train_rmse']]] for n in ['v1',*frozen['candidates']]]))
    sections.append('''## 6. 초기/후기, θ/b 오차와 사용자 분포

출처: `validate_summary.csv`, [사용자별 원자료](research_v2/artifacts/validate_users.csv), [사용자·스킬 추정치](research_v2/artifacts/validate_theta.csv), [문항별 추정치](research_v2/artifacts/validate_items.csv). 재현: `python -m research_v2.run --phase validate`.

### 공통 평가 시점별 변화
''')
    sections.append(table(['정책','응답 수','AUC','Log loss','Brier','ECE','θ RMSE'],[[n,str(k),*[fmt(n,f'common_{k}_{m}') for m in ['auc','log_loss','brier','ece']],fmt(n,f'theta_{k}_rmse')] for n in ['v1','random',*frozen['candidates']] for k in [0,6,48]]))
    sections.append('### 관측 초기/후기 성능\n\n노출 문항/시점/다른 사용자에 의한 문항 학습량도 달라지므로 전후 차이를 학습의 인과 효과로 해석하지 않는다.\n')
    sections.append(table(['정책','초기 AUC','후기 AUC','초기 Log loss','후기 Log loss','초기 Brier','후기 Brier','초기 ECE','후기 ECE'],[[n,*[fmt(n,m) for m in ['early_auc','late_auc','early_log_loss','late_log_loss','early_brier','late_brier','early_ece','late_ece']]] for n in NAMES]))
    sections.append('### 최종 θ/b 복원 오차\n')
    sections.append(table(['정책','사용자 평균 θ RMSE','fact θ','inference θ','vocab θ','main_idea θ','훈련 b','미학습 b'],[[n,*[fmt(n,m) for m in ['theta_48_user_mean_rmse','theta_48_fact_rmse','theta_48_inference_rmse','theta_48_vocab_rmse','theta_48_main_idea_rmse','b_train_rmse','b_heldout_rmse']]] for n in names]))
    sections.append('### 시드별 공통 확률 MSE 분포\n\n출처: `validate_seeds.csv`; 재현: `python -m research_v2.run --phase validate`. 평균만으로 가려지는 시드 변동을 그대로 표시한다.\n')
    raw = pd.read_csv(A/'validate_seeds.csv')
    seeds = sorted(raw.seed.unique())
    sections.append(table(['정책',*[str(seed) for seed in seeds]], [[n,*[f'{raw[(raw.variant==n)&(raw.seed==seed)].iloc[0].common_48_probability_mse:.6f}' for seed in seeds]] for n in names]))
    sections.append('### 사용자 분포\n\n각 시드의 사용자 분위수(p10/p50/p90)를 먼저 계산한 뒤 시드 평균·SD로 표시한다. 모든 사용자를 합친 분위수와 다르며 사용자별 평균의 뒤에 숨는 차이를 보는 기술통계다. 개별 값은 `validate_users.csv`에 있다.\n')
    sections.append(table(['정책','정답률 p10','정답률 p50','정답률 p90','공통 Brier p10','공통 Brier p50','공통 Brier p90'],[[n,*[fmt(n,m) for m in ['user_accuracy_p10','user_accuracy_p50','user_accuracy_p90','user_common_brier_p10','user_common_brier_p50','user_common_brier_p90']]] for n in names]))
    sections.append('''## 7. 학습 효과 가정에 대한 강건성 확인

출처: [학습률 .01 원자료](research_v2/artifacts/learning_seeds.csv), [통계](research_v2/artifacts/learning_summary.csv), [manifest](research_v2/artifacts/learning_manifest.json). 재현: `python -m research_v2.run --phase learning`.

검증과 같은 다섯 시드/고정 후보로 기존 스킬당 +.01 가정을 적용했다. 응답별 증가량은 정책과 독립적이나 어떤 스킬을 노출했는지에 따라 스킬별 최종 θ는 달라진다. 따라서 이 조건의 공통 문항 ID/uniform은 같아도 정답 라벨과 true probability는 정책별로 다를 수 있다. 주 분석처럼 엄밀히 동일한 잠재 θ의 비교가 아니며, 정책별 학습 효과 향상의 증거가 아니다. 사용자당 총 θ 증가량은 동일하다.
''')
    sections.append(table(['정책','공통 Brier','공통 확률 MSE','실제 목표거리','정답률','커버리지 격차'],[[n,*[fmt(n,m,'learning') for m in ['common_48_brier','common_48_probability_mse','target_true_mae','accuracy','coverage_gap']]] for n in names]))
    sections.append((ROOT/'research_v2/FINDINGS.md').read_text(encoding='utf-8-sig'))
    sections.append('''## 10. 재현 절차와 산출물

아래 명령은 저장소 루트에서 시작한다. Python 환경은 [requirements-lock.txt](research_v2/requirements-lock.txt)에 고정했다. 플랫폼 차이로 마지막 부동소수 자리는 달라질 수 있다. 실험은 외부 API/실사용자 데이터를 사용하지 않는다.

```powershell
cd ml
python -m venv .venv
.venv/Scripts/Activate.ps1
python -m pip install -r research_v2/requirements-lock.txt
$env:PYTHONIOENCODING='utf-8'
python scripts/run_experiment.py
python scripts/run_passage_experiment.py
python scripts/run_passage_experiment.py --seed 7
python -m pytest -q --ignore=tests/test_research_v2.py --basetemp=research_v2/tmp-baseline
python -m research_v2.run --phase tune
# frozen_candidates.json 생성 완료 후만 검증 실행
python -m research_v2.run --phase validate
python -m research_v2.run --phase learning
python -m research_v2.replay
python -m research_v2.check_artifacts
python -m research_v2.report
python -m pytest -q --basetemp=research_v2/tmp-final
python -m pytest -c ../gen/pytest.ini ../gen/tests --basetemp=research_v2/tmp-gen -q
python scripts/run_learning_analytics.py
python scripts/run_service_workflow.py
python scripts/diagnose_difficulty.py
```

- `*_seeds.csv`: 모든 시드·설정별 집계값. 표에 생략한 적용 목표 거리, cold 실제 거리, 기대 Brier, b 노출 문항 오차 등도 포함한다.
- `*_summary.csv`: 모든 지표의 평균·표본분산·SD·95% CI. `*_paired.csv`: 같은 시드 V1 대비 차이와 CI. 시드가 유일한 통계 반복 단위다.
- `*_users.csv`: 사용자별 정답률, 커버리지, 목표 거리, 공통 예측 성능, θ RMSE.
- `*_theta.csv`: 사용자·스킬·시점별 추정/실제 θ와 오차. `*_items.csv`: 문항별 추정/실제 b, split/노출 여부.
- `*_manifest.json`: 정확한 설정, 시드, Python/라이브러리 버전, 실행 시 연구 코드 SHA-256(검증 시 Git checkout의 줄바꿈 변환만 허용). 튜닝 이후 추가된 replay/report 파일은 튜닝 manifest의 소스 목록에 없으며 튜닝 수치에는 관여하지 않는다.
- seed/설정/응답 생성 규칙으로 원시 온라인 로그를 다시 생성할 수 있다. `run(..., return_logs=True)`의 다섯 번째/여섯 번째 반환값이 관측/공통 로그다. 기존 `ml/results/`와 기존 기준 문서는 덮어쓰지 않았다(분리된 worktree의 기존 스크립트 기본 출력만 생성).

## 11. 검증과 변경 경계

[기존 ML 테스트](research_v2/artifacts/baseline_tests.txt) 189개, [추가 연구 테스트 포함](research_v2/artifacts/final_tests.txt) 194개, [Generation 테스트](research_v2/artifacts/generation_tests.txt) 19개가 통과했다. 재현 명령은 위에 있다. 기본 환경에 누락된 의존성은 별도 worktree 가상환경에 설치했고, pytest 임시 디렉터리 접근 문제는 허용된 연구 디렉터리의 `--basetemp`로 해결했다.

연구 테스트는 기존 V1/Random과 문항 선택·응답·예측의 동일성, 미학습 은행 분리, probe 무변경, 잠재값의 등록 경계, 정책 간 공통 라벨 pairing, Brier 분해, 시드 단위 paired 통계, 동일 로그 재학습의 동등성을 확인한다.

[결과 파일 검증](research_v2/artifacts/artifact_checks.txt)은 탐색 93회, 독립 검증 50회, 학습률 강건성 50회, 동일 로그 재학습 20회의 누락·중복 여부, 모든 요약/paired 통계 재계산, 소스 hash와 튜닝 고정 hash를 확인했다 (`python -m research_v2.check_artifacts`).

기존 [분석 데모](research_v2/artifacts/learning_analytics.json), [서비스 워크플로](research_v2/artifacts/service_workflow.json), [난이도 진단](research_v2/artifacts/difficulty_diagnostic.json)도 위 명령으로 성공했다. Backend/Frontend의 별도 JS 테스트는 이번 ML 연구의 검증 범위에 포함하지 않았다. 기존 ML/Generation 소스·테스트, FastAPI/DB/Generation/Retrieval/Frontend, 공개 계약, 운영 기본값은 수정하지 않았다.

`git diff --name-status d17ac32 HEAD`로 `ml/` 내부 추가 파일만 있는지 확인한다. 기존 작업 브랜치와 PR #11/#12는 수정하지 않고 연구 브랜치만 Push한다. PR은 생성하지 않는다.
''')
    (ROOT/'PREDICTION_MODEL_RESEARCH_V2.md').write_text('\n'.join(sections),encoding='utf-8')

if __name__ == '__main__':
    main()
