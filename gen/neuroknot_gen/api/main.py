"""슬라이스 2 API를 혼자 띄워 보기 위한 앱.

팀 공통 서버 골격(협업 가이드 6절, [공통])이 생기면 거기서
`app.include_router(router)` 한 줄로 이 라우터를 붙이고, 이 파일은 로컬 확인용으로만 쓴다.

실행 (gen 폴더에서):
    .venv/bin/uvicorn neuroknot_gen.api.main:app --reload
그다음 브라우저에서 http://127.0.0.1:8000/docs 를 열면 직접 눌러 볼 수 있다.
"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI

from .routes import router

# gen/.env 의 GEN_QUIZ_DIR 등을 읽는다. 이미 셸에 설정된 값이 있으면 그쪽이 우선.
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

app = FastAPI(title="NeuroKnots 슬라이스 2 — 문항·해설 API")
app.include_router(router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
