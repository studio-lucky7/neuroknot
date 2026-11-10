# NeuroKnot FastAPI Backend

Python / FastAPI, SQLAlchemy 2, Alembic, MySQL 공통 기반이다. 기존 NestJS 시작 코드는
루트의 `Hello World!`와 테스트, 모델이 없는 Prisma 연결 설정을 제공했다. 이전 골격은
Git 이력의 `f7f46bb`와 전환 직전 develop `744f441`에서 확인할 수 있다.

## Windows PowerShell에서 실행

Python 3.12를 사용한다. 저장소 루트에서 실행한다.

```powershell
Set-Location backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

| 경로 | 용도 |
| --- | --- |
| `GET /health` | 프로세스 상태. DB 설정 없이 `{"status":"ok"}` 반환 |
| `GET /health/db` | DB 준비 상태. 연결을 열어 `SELECT 1` 실행 |
| `GET /docs`, `GET /openapi.json` | Swagger UI 및 OpenAPI 스키마 |

`app/main.py`가 앱과 수명 주기를 구성하고, `app/routers/`에 기능별 라우터를 둔다.
요청·응답은 Pydantic 모델로 선언한다. 공통 오류는 `code`, `message`, 검증 오류의
`issues`를 반환한다. 입력 검증이 있는 라우터는 OpenAPI의 422 응답 모델을
`ErrorResponse`로 선언한다. 업무 라우터는 팀이 계약을 합의한 뒤 추가한다.

## 환경변수와 MySQL

`Copy-Item .env.example .env`로 작업 트리의 로컬 설정 파일을 만들 수 있다.
프로세스 환경변수가 `backend/.env`보다 우선한다.

| 이름 | 동작 |
| --- | --- |
| `DATABASE_URL` | MySQL URL. `mysql+pymysql://user:password@localhost:3306/database` 형식. 기존 `mysql://`도 PyMySQL로 정규화한다. |
| `DATABASE_REQUIRED` | 기본값 `false`. `true`이면 URL 누락 시 앱 시작이 실패한다. |
| `MYSQL_TEST_DATABASE_URL` | 실제 MySQL 테스트용 별도 URL. 테스트를 실행하는 프로세스에 설정한다. |

URL이 없으면 `/health/db`는 `503 database_not_configured`를 반환한다.
연결이나 쿼리가 실패하면 `503 database_unavailable`를 반환한다.
URL에 들어가는 자격 증명의 특수문자는 퍼센트 인코딩한다. DB 설정은 `.env`나
프로세스 환경에 둔다.

엔진은 앱 수명 주기마다 생성·정리하며, 첫 DB 작업에서 연결한다. DB 작업을 하는
동기 라우터는 `DatabaseSession`으로 요청별 세션을 받는다. 쓰기 서비스가
커밋을 명시하고, 요청이 끝나면 세션이 닫히며 미완료 트랜잭션은 롤백된다.

## Alembic 및 테스트

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe -m alembic heads
```

기본 pytest는 MySQL 없이 실행한다. 실제 DB를 검사할 때는 테스트용
`MYSQL_TEST_DATABASE_URL`을 프로세스에 설정하고 아래 명령을 실행한다.
이 테스트는 준비 상태에서 `SELECT 1`을 확인한다.

```powershell
.\.venv\Scripts\python.exe -m pytest -m mysql
```

Alembic은 같은 DB 설정과 `Base.metadata`를 사용한다. `0001_foundation`은
업무 테이블을 추가하지 않는 초기 리비전이다. DB URL을 설정하면 아래 명령으로
연결 없이 MySQL SQL을 미리 볼 수 있다. 실제 `upgrade head`는 대상 DB가 확정된 뒤 실행한다.

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head --sql
```

## Generation·Prediction 연동 준비

`neuroknot_gen`과 `neuroknot_ml`은 원본 위치에서 독립적으로 유지한다.
같은 가상환경에서 개발용으로 import할 때는 기존 요구사항을 불러오고, 현재
PowerShell 세션의 모듈 경로에 두 슬라이스 디렉터리를 추가한다.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-slices.txt
$env:PYTHONPATH = @((Resolve-Path ../gen).Path, (Resolve-Path ../ml).Path) -join [IO.Path]::PathSeparator
```

서비스 통합 시 라우터가 Gen·ML 구현을 복사하는 대신 백엔드 어댑터에서 각 모듈을
호출한다. Generation의 생성·검증과 develop의 Elo 엔진은 현재 재사용 대상이다.
Core 지문 선택과 Learning Analytics는 PR #11 병합 후 별도 마일스톤에서 연결한다.
배포용 패키지화 시 슬라이스별 의존성 원본과 Generation 프롬프트·리소스의 포함 방식을 함께 정한다.

DB 테이블과 마이그레이션, 인증·CORS, 슬라이스 입출력 및 오류 계약, Elo 상태 저장과
트랜잭션 경계는 두 팀원의 공통 리뷰 대상이다.
