"""평가 세트: 프롬프트를 고쳤을 때 '정말 좋아졌는가'를 숫자로 보기 위한 도구.

두 종류의 점수를 본다.
- 자동 지표: 사람 없이 바로 계산. 쏠림(스킬·난이도·정답 길이)처럼 '모양'의 문제를 잡는다.
- 사람 채점: 채점표(sheet.csv)에 0/1을 적는다. '정답이 하나뿐인가'처럼 내용의 문제는
  사람이 봐야 안다. 채점 기준은 gen/eval/README.md.

같은 지문 10편(eval/passages.txt)으로 버전마다 돌리고, 두 실행(run)의 점수를 나란히 비교한다.
"""

import csv
import statistics
from pathlib import Path

from .schemas import GeneratedQuiz
from .skills import ErrorType, Skill

# 사람이 문항마다 0/1로 매기는 항목. 순서가 곧 채점표 열 순서다.
CRITERIA = {
    "정답_유일": "지문을 근거로 정답이 하나로 확정된다",
    "지문_필요": "지문을 읽지 않고 상식·배경지식만으로는 풀 수 없다",
    "근거_적절": "근거 문장(evidence)이 정답을 실제로 뒷받침한다",
    "오답_매력": "오답 3개가 모두 지문을 대충 읽으면 고를 만하다 (말이 안 되는 오답이 없다)",
    "해설_정확": "해설과 오답 설명에 사실 오류나 지문과 다른 내용이 없다",
    "스킬_일치": "붙어 있는 스킬 라벨이 이 문항이 실제로 재는 능력과 맞다",
}
# 오답 3개 중 오류 유형 라벨이 맞는 개수 (0~3).
ERROR_TYPE_COLUMN = "오답유형_맞은수"
# 지문당 한 번, 사람이 매긴 체감 난이도 (1~5). 모델의 difficulty_hint와 비교한다.
HUMAN_DIFFICULTY_COLUMN = "사람_난이도"


def load_run(run_dir: Path) -> list[GeneratedQuiz]:
    return [
        GeneratedQuiz.model_validate_json(p.read_text(encoding="utf-8"))
        for p in sorted((run_dir / "quiz").glob("*.json"))
    ]


# ── 자동 지표 ────────────────────────────────────────────────


def auto_metrics(quizzes: list[GeneratedQuiz]) -> dict:
    questions = [q for g in quizzes for q in g.quiz.questions]
    distractors = [d for q in questions for d in q.distractors]
    difficulties = [g.quiz.difficulty_hint for g in quizzes]

    # 정답이 선택지 중 '가장 긴 것'이면, 지문을 안 읽고도 길이만 보고 찍을 수 있다.
    # 무작위라면 약 25%가 기대값이다.
    longest = sum(
        1 for q in questions if len(q.options[q.answer_index]) == max(len(o) for o in q.options)
    )

    return {
        "지문 수": len(quizzes),
        "문항 수": len(questions),
        "스킬 분포": {s.value: sum(q.skill == s for q in questions) for s in Skill},
        "난이도 분포": {str(k): difficulties.count(k) for k in range(1, 6)},
        "난이도 표준편차": round(statistics.pstdev(difficulties), 2) if difficulties else 0.0,
        "정답 위치 분포": {str(k + 1): sum(q.answer_index == k for q in questions) for k in range(4)},
        "정답이 가장 긴 선택지인 비율": round(longest / len(questions), 2) if questions else 0.0,
        "오답 유형 분포": {e.value: sum(d.error_type == e for d in distractors) for e in ErrorType},
        # 한 문항의 오답 3개 중 같은 유형이 둘 이상인 문항 수. 0이어야 한다.
        "오답 유형이 겹치는 문항": sum(
            len({d.error_type for d in q.distractors}) < len(q.distractors) for q in questions
        ),
    }


def format_auto(metrics: dict) -> str:
    lines = ["| 지표 | 값 |", "| --- | --- |"]
    for key, value in metrics.items():
        if isinstance(value, dict):
            value = ", ".join(f"{k} {v}" for k, v in value.items())
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)


# ── 사람 채점표 ──────────────────────────────────────────────


def sheet_header() -> list[str]:
    return [
        "passage_id", "q", "skill", "difficulty_hint", "stem",
        "opt1", "opt2", "opt3", "opt4", "answer", "evidence", "explanation", "distractors",
        *CRITERIA, ERROR_TYPE_COLUMN, HUMAN_DIFFICULTY_COLUMN, "메모",
    ]


def sheet_rows(quizzes: list[GeneratedQuiz]) -> list[list[str]]:
    rows = []
    for g in quizzes:
        for i, q in enumerate(g.quiz.questions):
            distractors = " / ".join(
                f"{d.option_index + 1}번 [{d.error_type.value}] {d.why_wrong}" for d in q.distractors
            )
            rows.append([
                g.passage_id, str(i + 1), q.skill.value, str(g.quiz.difficulty_hint), q.stem,
                *q.options, str(q.answer_index + 1), q.evidence, q.explanation, distractors,
                *([""] * len(CRITERIA)),
                "",  # 오답유형_맞은수
                "",  # 사람_난이도: 지문마다 첫 문항(q=1) 줄에만 적는다
                "",  # 메모
            ])
    return rows


def write_sheet(quizzes: list[GeneratedQuiz], path: Path) -> None:
    # utf-8-sig: 엑셀·넘버스에서 열어도 한글이 깨지지 않게 BOM을 붙인다.
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f)
        w.writerow(sheet_header())
        w.writerows(sheet_rows(quizzes))


# ── 채점 집계 ────────────────────────────────────────────────


def _as_int(value: str) -> int | None:
    value = (value or "").strip()
    return int(value) if value.lstrip("-").isdigit() else None


def score_sheet(path: Path, quizzes: list[GeneratedQuiz] | None = None) -> dict:
    """채점이 끝난 sheet.csv를 읽어 항목별 통과율을 낸다. 빈 칸은 '아직 안 매김'으로 뺀다."""
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    result: dict = {"채점한 문항": 0, "항목별 통과율": {}, "스킬별 통과율": {}}

    for name in CRITERIA:
        values = [v for r in rows if (v := _as_int(r.get(name, ""))) is not None]
        result["항목별 통과율"][name] = round(sum(values) / len(values), 2) if values else None

    scored = [r for r in rows if all(_as_int(r.get(n, "")) is not None for n in CRITERIA)]
    result["채점한 문항"] = len(scored)
    # 여섯 항목을 모두 통과한 문항 = '그대로 앱에 내보내도 되는 문항'
    result["전 항목 통과율"] = (
        round(sum(all(_as_int(r[n]) == 1 for n in CRITERIA) for r in scored) / len(scored), 2)
        if scored else None
    )

    by_skill: dict[str, list[bool]] = {}
    for r in scored:
        by_skill.setdefault(r["skill"], []).append(all(_as_int(r[n]) == 1 for n in CRITERIA))
    result["스킬별 통과율"] = {k: round(sum(v) / len(v), 2) for k, v in sorted(by_skill.items())}

    et = [v for r in rows if (v := _as_int(r.get(ERROR_TYPE_COLUMN, ""))) is not None]
    result["오답 유형 라벨 정확도"] = round(sum(et) / (3 * len(et)), 2) if et else None

    # 모델 난이도와 사람 난이도가 얼마나 같이 움직이는가
    pairs = [
        (int(r["difficulty_hint"]), h)
        for r in rows
        if (h := _as_int(r.get(HUMAN_DIFFICULTY_COLUMN, ""))) is not None
    ]
    result["난이도 일치(상관계수)"] = _pearson(pairs)
    result["난이도 채점 지문 수"] = len(pairs)
    return result


def _pearson(pairs: list[tuple[int, int]]) -> float | None:
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    if len(set(xs)) == 1 or len(set(ys)) == 1:
        return None  # 한쪽이 전부 같은 값이면 상관을 정의할 수 없다 (= 난이도 구분 실패)
    return round(statistics.correlation(xs, ys), 2)


def format_compare(named_scores: dict[str, dict]) -> str:
    """여러 실행의 채점 결과를 표 하나로 나란히 놓는다."""
    names = list(named_scores)
    keys = ["채점한 문항", "전 항목 통과율", *[f"항목별 통과율.{c}" for c in CRITERIA],
            "오답 유형 라벨 정확도", "난이도 일치(상관계수)"]

    def get(score: dict, key: str):
        if "." in key:
            a, b = key.split(".", 1)
            return score.get(a, {}).get(b)
        return score.get(key)

    lines = ["| 항목 | " + " | ".join(names) + " |", "| --- |" + " --- |" * len(names)]
    for key in keys:
        label = key.split(".", 1)[-1]
        cells = ["-" if (v := get(named_scores[n], key)) is None else str(v) for n in names]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    return "\n".join(lines)
