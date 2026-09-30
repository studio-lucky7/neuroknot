# 협업 가이드

뉴로넛은 세 명이 기능 단위(추천 · 해설 · 성장)로 나눠서 동시에 개발합니다. 서로의 작업을 덮어쓰지 않도록 아래 규칙을 지켜 주세요.

## 0. 처음 시작하기

### 레포 받기

처음이면 클론하고, 이미 있으면 최신으로 받은 뒤 `develop`으로 이동합니다.

```bash
# 처음
git clone https://github.com/studio-lucky7/neuroknot.git
cd neuroknot

# 이미 있으면
git fetch origin
git switch develop
git pull origin develop
```

> Next.js 시절 폴더가 남아 있다면 `frontend/node_modules`, `frontend/.next`, `frontend/next-env.d.ts`를 지우고 새로 설치하세요.

### 앱 실행 (Expo Go)

1. [expo.dev](https://expo.dev)에서 계정을 만듭니다. (GitHub로 가입 가능)
2. 노트북에서 로그인합니다. GitHub로 가입했다면 `--browser`를 붙이세요.
   ```bash
   cd frontend
   npm install
   npx expo login --browser
   npx expo whoami        # 내 계정 이름이 나오면 성공
   ```
3. 폰에 **Expo Go** 앱을 설치하고 **같은 계정**으로 로그인합니다.
   (GitHub로 가입해서 비밀번호가 없다면 expo.dev에서 "Forgot password?"로 비밀번호를 만드세요.)
4. `npx expo start` 후 QR 코드를 찍습니다. 아이폰은 기본 카메라 앱으로 찍으면 됩니다.

안 될 때:
- "signed in to Expo Go ... but not signed in to Expo CLI" → `npx expo start`를 껐다가 다시 켜세요. 로그인 전에 켠 서버는 로그인을 모릅니다.
- 연결이 안 됨 → 폰과 노트북이 같은 와이파이인지 확인하고, 안 되면 `npx expo start --tunnel`.
- 폰이 없으면 터미널에서 `w`를 눌러 브라우저로 볼 수 있습니다. 단, 앱과 조금 다르게 보일 수 있습니다.

## 1. 브랜치

| 브랜치 | 용도 | 규칙 |
| --- | --- | --- |
| `main` | 시연·배포 가능한 상태 | 직접 push 불가. 주차 마감 때 `develop`에서만 머지 |
| `develop` | 통합 브랜치 (기본 브랜치) | 직접 push 불가. 모든 작업은 PR로 |
| 작업 브랜치 | 기능 하나 | `develop`에서 따고, `develop`으로 PR |

작업 브랜치 이름은 `타입/슬라이스-설명` 형식입니다.

| 슬라이스 | 접두어 | 담당 |
| --- | --- | --- |
| 1 · 추천 (Retrieval) | `rec` | 함한솔 |
| 2 · 해설 (Generation) | `gen` | 정수민 |
| 3 · 성장 (Prediction) | `pred` | 류진 |
| 공통 기반 | `common` | 셋 다 |

예시: `feat/pred-attempt-logging`, `fix/gen-quiz-json-parse`, `chore/common-docker-compose`

## 2. GitHub가 막아 두는 것

`main`과 `develop`에는 규칙(Rulesets)이 걸려 있어서, 아래는 **실수로라도 할 수 없습니다.**

- 직접 push (`git push origin develop` → 거절됨)
- force push (`git push --force`)
- 브랜치 삭제
- 승인 없이 PR 머지 (다른 사람 1명 승인 필요, **본인 PR은 본인이 승인 불가**)

push가 거절되면 잘못한 게 아니라 규칙이 작동한 겁니다. 작업 브랜치로 옮겨서 PR을 올리세요.

```bash
# develop에서 실수로 커밋했다면: 그 커밋을 새 브랜치로 옮기기
git switch -c feat/pred-내작업     # 지금 상태 그대로 새 브랜치 생성
git push -u origin feat/pred-내작업
git switch develop
git reset --hard origin/develop    # 로컬 develop을 원래대로
```

## 3. 작업 흐름

```bash
# 1) 최신 develop에서 브랜치 만들기
git switch develop
git pull origin develop
git switch -c feat/pred-attempt-logging

# 2) 작업하고 커밋
git add .
git commit -m "feat: 답안 로깅 API 추가"

# 3) PR 올리기 전에 develop 최신 내용 반영
git fetch origin
git rebase origin/develop
git push -u origin feat/pred-attempt-logging

# 4) GitHub에서 develop 대상으로 PR 생성
```

PR이 머지되면 작업 브랜치는 삭제하고, 다음 작업은 다시 1)부터 시작합니다.

## 4. 커밋 메시지

`타입: 한 줄 요약` 형식으로, 요약은 한국어로 씁니다.

| 타입 | 언제 |
| --- | --- |
| `feat` | 기능 추가 |
| `fix` | 버그 수정 |
| `refactor` | 동작은 그대로, 구조 개선 |
| `docs` | 문서 |
| `test` | 테스트 |
| `chore` | 설정, 패키지, 빌드 |

## 5. PR 규칙

- 작업 PR의 대상은 항상 `develop`입니다.
- 리뷰어 1명 이상 승인 후 머지합니다. **PR이 올라오면 하루 안에 봐 주세요.** 리뷰가 늦으면 올린 사람의 작업이 막힙니다.
- PR은 작게 유지합니다. 하루 작업 분량 이상 쌓이면 나눠서 올려 주세요.
- 화면이 바뀌면 스크린샷을 첨부합니다.

### 머지 방식

| PR 방향 | 머지 방식 | 이유 |
| --- | --- | --- |
| 작업 브랜치 → `develop` | **Squash and merge** | 작업 브랜치는 머지 후 삭제하므로, 커밋을 하나로 합쳐 기록을 "기능 하나 = 커밋 하나"로 유지 |
| `develop` → `main` | **Create a merge commit** | 둘 다 계속 쓰는 브랜치라 원본 커밋을 공유해야 함. squash하면 다음 주 머지 때 충돌 |

GitHub에서 브랜치별로 허용된 방식만 버튼이 나오도록 설정해 두었으니, 보이는 버튼을 누르면 됩니다.

## 6. 공통 기반은 셋이 같이

아래는 모든 슬라이스가 기대는 부분이라, 바꿀 때는 PR 제목 앞에 `[공통]`을 붙이고 **나머지 두 명 모두** 승인을 받습니다.

- DB 스키마 (SQLAlchemy 모델)
- 슬라이스 간 API 계약 (요청·응답 형식)
- 카테고리 ID (`frontend/src/constants/categories.ts`)와 난이도 스케일 (1~5)
- docker-compose, FastAPI 기본 골격, 환경변수 목록

## 7. DB 마이그레이션

- Alembic 설정은 슬라이스 1이 관리합니다. 각자 자기 테이블의 마이그레이션은 직접 만들어도 됩니다.
- 마이그레이션이 들어간 PR은 머지 전에 `develop`으로 rebase하고 `alembic heads` 결과가 **1개**인지 확인합니다. 2개 이상이면 머지하지 말고 팀 채팅에 알려 주세요.

## 8. 비밀값

- `.env`는 절대 커밋하지 않습니다. 새 환경변수가 생기면 값 없이 `.env.example`에만 추가합니다.
- Claude API 키 등이 실수로 커밋되면, 커밋을 지우는 것보다 **키를 먼저 폐기하고 재발급**합니다. (한 번 올라간 키는 유출된 것으로 봅니다.)

## 9. 앱 식별자

iOS `bundleIdentifier`와 Android `package`는 `com.studiolucky7.neuroknot`로 고정입니다. 스토어에 한 번 올라가면 바꿀 수 없는 값이라 개인 이름으로 바꾸지 않습니다. 변경이 필요하면 팀장과 먼저 상의해 주세요.

## 10. 주차 마감

주차가 끝나면 팀장이 `develop` → `main` PR을 올리고, 셋이 시연 흐름(온보딩 → 추천 → 읽기 → 퀴즈 → 해설 → 리그)을 한 번 확인한 뒤 **Create a merge commit**으로 머지합니다. 머지 후 `v0.1`(1주차), `v0.2`(2주차)처럼 태그를 붙입니다.
