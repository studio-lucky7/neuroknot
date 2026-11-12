"""평가 도구가 숫자를 제대로 세는지 확인한다. (생성 품질 자체를 보는 테스트가 아니다)"""

import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from neuroknot_gen import evalkit  # noqa: E402
from neuroknot_gen.loader import load_passage  # noqa: E402
from neuroknot_gen.schemas import GeneratedQuiz  # noqa: E402

from test_validate import make_quiz  # noqa: E402


def generated(pid="fx-001", difficulty=3):
    quiz = make_quiz(load_passage("fx-001"))
    quiz.difficulty_hint = difficulty
    return GeneratedQuiz(passage_id=pid, prompt_version="t", model="t", quiz=quiz)


def test_자동_지표():
    m = evalkit.auto_metrics([generated(difficulty=2), generated(difficulty=4)])
    assert m["문항 수"] == 6
    assert m["스킬 분포"] == {"fact": 2, "inference": 2, "vocab": 0, "main_idea": 2}
    assert m["난이도 분포"]["2"] == 1 and m["난이도 분포"]["4"] == 1
    assert m["난이도 표준편차"] == 1.0
    assert m["정답 위치 분포"] == {"1": 0, "2": 6, "3": 0, "4": 0}
    assert sum(m["오답 유형 분포"].values()) == 18
    assert m["오답 유형이 겹치는 문항"] == 0


def test_오답_유형이_겹치는_문항을_센다():
    g = generated()
    first = g.quiz.questions[0]
    first.distractors[1].error_type = first.distractors[0].error_type
    assert evalkit.auto_metrics([g])["오답 유형이 겹치는 문항"] == 1


def test_정답이_가장_긴_선택지인_비율():
    g = generated()
    for q in g.quiz.questions:
        q.options[q.answer_index] = "아주 길게 늘여 쓴 정답 선택지입니다"
    assert evalkit.auto_metrics([g])["정답이 가장 긴 선택지인 비율"] == 1.0


def fill(path: Path, marks: dict[int, dict[str, str]]):
    """채점표의 n번째 줄(0부터)에 값을 적는다."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    for i, values in marks.items():
        rows[i].update(values)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=evalkit.sheet_header())
        w.writeheader()
        w.writerows(rows)


ALL_PASS = {c: "1" for c in evalkit.CRITERIA}


def test_채점표는_문항마다_한_줄이고_점수칸은_비어_있다(tmp_path):
    sheet = tmp_path / "sheet.csv"
    evalkit.write_sheet([generated("a"), generated("b")], sheet)
    with sheet.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 6
    assert rows[0]["answer"] == "2"  # 사람이 보는 번호는 1부터
    assert all(rows[0][c] == "" for c in evalkit.CRITERIA)


def test_빈_칸은_집계에서_뺀다(tmp_path):
    sheet = tmp_path / "sheet.csv"
    evalkit.write_sheet([generated("a")], sheet)
    fill(sheet, {0: ALL_PASS, 1: {**ALL_PASS, "정답_유일": "0"}})  # 3번째 문항은 안 매김
    s = evalkit.score_sheet(sheet)
    assert s["채점한 문항"] == 2
    assert s["항목별 통과율"]["정답_유일"] == 0.5
    assert s["항목별 통과율"]["해설_정확"] == 1.0
    assert s["전 항목 통과율"] == 0.5


def test_오답_유형_정확도와_난이도_상관(tmp_path):
    sheet = tmp_path / "sheet.csv"
    evalkit.write_sheet([generated("a", 1), generated("b", 3), generated("c", 5)], sheet)
    fill(sheet, {
        0: {evalkit.ERROR_TYPE_COLUMN: "3", evalkit.HUMAN_DIFFICULTY_COLUMN: "2"},
        3: {evalkit.ERROR_TYPE_COLUMN: "0", evalkit.HUMAN_DIFFICULTY_COLUMN: "3"},
        6: {evalkit.HUMAN_DIFFICULTY_COLUMN: "4"},
    })
    s = evalkit.score_sheet(sheet)
    assert s["오답 유형 라벨 정확도"] == 0.5  # (3 + 0) / 6
    assert s["난이도 일치(상관계수)"] == 1.0
    assert s["난이도 채점 지문 수"] == 3


def test_모델_난이도가_전부_같으면_상관을_내지_않는다(tmp_path):
    sheet = tmp_path / "sheet.csv"
    evalkit.write_sheet([generated(p, 2) for p in "abc"], sheet)
    fill(sheet, {0: {evalkit.HUMAN_DIFFICULTY_COLUMN: "1"}, 3: {evalkit.HUMAN_DIFFICULTY_COLUMN: "3"},
                 6: {evalkit.HUMAN_DIFFICULTY_COLUMN: "5"}})
    assert evalkit.score_sheet(sheet)["난이도 일치(상관계수)"] is None


def test_비교표에_실행_이름이_열로_나온다():
    table = evalkit.format_compare({
        "v2": {"채점한 문항": 60, "전 항목 통과율": 0.5, "항목별 통과율": {"정답_유일": 0.9}},
        "v3": {"채점한 문항": 60, "전 항목 통과율": 0.7, "항목별 통과율": {"정답_유일": 0.95}},
    })
    assert "| 항목 | v2 | v3 |" in table
    assert "| 정답_유일 | 0.9 | 0.95 |" in table
    assert "| 오답 유형 라벨 정확도 | - | - |" in table
