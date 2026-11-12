#!/usr/bin/env python
"""평가 세트 실행과 채점 집계.

  python scripts/run_eval.py generate v2-base              평가 지문 전체로 생성 → 자동 지표 + 채점표
  python scripts/run_eval.py generate v3-try --prompt quiz_v3
  python scripts/run_eval.py score v2-base                 채점이 끝난 채점표 집계
  python scripts/run_eval.py score v2-base v3-try          두 실행 나란히 비교

결과는 gen/eval/runs/<실행 이름>/ 에 쌓인다. 이 폴더는 커밋한다.
(프롬프트를 바꾸기 전과 후를 나중에도 비교할 수 있어야 하므로)
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from neuroknot_gen import evalkit  # noqa: E402
from neuroknot_gen.generate import DEFAULT_PROMPT_VERSION, generate_quiz, model_name  # noqa: E402
from neuroknot_gen.loader import load_passage  # noqa: E402
from neuroknot_gen.validate import check_quiz  # noqa: E402

EVAL_DIR = ROOT / "eval"
RUNS_DIR = EVAL_DIR / "runs"


def eval_ids() -> list[str]:
    lines = (EVAL_DIR / "passages.txt").read_text(encoding="utf-8").splitlines()
    return [s.strip() for s in lines if s.strip() and not s.startswith("#")]


def cmd_generate(args) -> int:
    load_dotenv(ROOT / ".env", override=True)
    run_dir = RUNS_DIR / args.run
    quiz_dir = run_dir / "quiz"
    quiz_dir.mkdir(parents=True, exist_ok=True)

    meta_path = run_dir / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {
        "run": args.run,
        "prompt_version": args.prompt,
        "model": model_name(),
        "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "first_try_pass": [],
        "retried": [],
        "failed": {},
    }
    if meta["prompt_version"] != args.prompt:
        print(f"이 실행은 {meta['prompt_version']}로 시작했습니다. 다른 프롬프트는 새 실행 이름을 쓰세요.")
        return 1

    for pid in eval_ids():
        out = quiz_dir / f"{pid}.json"
        if out.exists():  # 중간에 끊겼을 때 이어서 돌리기
            continue
        passage = load_passage(pid)
        print(f"{pid} 생성 중…", flush=True)
        try:
            generated = generate_quiz(passage, prompt_version=args.prompt)
            problems = check_quiz(generated.quiz, passage)
            if problems:
                generated = generate_quiz(passage, prompt_version=args.prompt, retry_notes=problems)
                problems = check_quiz(generated.quiz, passage)
                meta["retried"].append(pid)
            else:
                meta["first_try_pass"].append(pid)
        except RuntimeError as e:
            print(f"  {e}")
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            return 1

        if problems:
            meta["failed"][pid] = problems
            print(f"  재시도 후에도 검사 실패: {problems}")
        else:
            meta["failed"].pop(pid, None)
            out.write_text(
                json.dumps(generated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    quizzes = evalkit.load_run(run_dir)
    total = len(eval_ids())
    metrics = {
        "자동 검사 첫 시도 통과": f"{len(meta['first_try_pass'])}/{total}",
        "재시도 후 실패": f"{len(meta['failed'])}/{total}",
        **evalkit.auto_metrics(quizzes),
    }
    (run_dir / "auto.md").write_text(
        f"# {args.run} 자동 지표\n\n프롬프트 `{meta['prompt_version']}` · 모델 `{meta['model']}`\n\n"
        + evalkit.format_auto(metrics) + "\n",
        encoding="utf-8",
    )
    sheet = run_dir / "sheet.csv"
    if sheet.exists() and not args.overwrite_sheet:
        print(f"\n채점표가 이미 있어 덮어쓰지 않았습니다: {sheet.relative_to(ROOT)}")
    else:
        evalkit.write_sheet(quizzes, sheet)

    print("\n" + evalkit.format_auto(metrics))
    print(f"\n다음: {sheet.relative_to(ROOT)} 를 열어 채점 기준(eval/README.md)대로 0/1을 적으세요.")
    return 0 if not meta["failed"] else 1


def cmd_score(args) -> int:
    scores = {}
    for run in args.runs:
        sheet = RUNS_DIR / run / "sheet.csv"
        if not sheet.exists():
            print(f"채점표가 없습니다: {sheet}")
            return 1
        scores[run] = evalkit.score_sheet(sheet)
        (RUNS_DIR / run / "score.json").write_text(
            json.dumps(scores[run], ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(evalkit.format_compare(scores))
    for run, s in scores.items():
        if s["스킬별 통과율"]:
            print(f"\n{run} 스킬별 전 항목 통과율: {s['스킬별 통과율']}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="평가 세트 실행·채점")
    sub = parser.add_subparsers(dest="cmd", required=True)

    g = sub.add_parser("generate", help="평가 지문 전체로 생성")
    g.add_argument("run", help="실행 이름. 예: v2-base")
    g.add_argument("--prompt", default=DEFAULT_PROMPT_VERSION)
    g.add_argument("--overwrite-sheet", action="store_true", help="이미 있는 채점표를 새로 만든다 (적어 둔 점수가 지워짐)")
    g.set_defaults(func=cmd_generate)

    s = sub.add_parser("score", help="채점표 집계·비교")
    s.add_argument("runs", nargs="+")
    s.set_defaults(func=cmd_score)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
