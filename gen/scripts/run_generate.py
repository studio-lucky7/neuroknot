#!/usr/bin/env python
"""지문에서 문항·해설을 만들어 gen/out/ 에 저장한다.

  python scripts/run_generate.py fx-001            한 편만
  python scripts/run_generate.py --all             전부
  python scripts/run_generate.py fx-001 --dry-run  호출 없이 프롬프트만 확인
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from neuroknot_gen.generate import (  # noqa: E402
    DEFAULT_PROMPT_VERSION,
    build_user_content,
    generate_quiz,
    load_prompt,
)
from neuroknot_gen.loader import load_all_passages, load_passage  # noqa: E402
from neuroknot_gen.schemas import Passage  # noqa: E402
from neuroknot_gen.validate import check_quiz  # noqa: E402

OUT_DIR = ROOT / "out"


def show(generated, passage: Passage) -> None:
    """사람이 읽기 좋게 출력. 생성 직후 눈으로 확인하는 용도."""
    quiz = generated.quiz
    print(f"\n{'=' * 72}")
    print(f"{passage.id}  {passage.title}")
    print(f"지문 난이도 {quiz.difficulty_hint}/5   프롬프트 {generated.prompt_version}")
    print("=" * 72)

    for i, q in enumerate(quiz.questions, 1):
        print(f"\n[문항 {i}] ({q.skill.value})")
        print(f"  {q.stem}")
        for j, opt in enumerate(q.options):
            mark = "✔" if j == q.answer_index else " "
            print(f"   {mark} {j + 1}. {opt}")
        print(f"  근거: {q.evidence}")
        print(f"  해설: {q.explanation}")
        for d in q.distractors:
            print(f"   - {d.option_index + 1}번 ({d.error_type.value}): {d.why_wrong}")


def run_one(passage: Passage, *, dry_run: bool, prompt_version: str) -> bool:
    if dry_run:
        print(f"\n{'=' * 72}\n[system]\n{'=' * 72}")
        print(load_prompt(prompt_version))
        print(f"\n{'=' * 72}\n[user]\n{'=' * 72}")
        print(build_user_content(passage))
        return True

    generated = generate_quiz(passage, prompt_version=prompt_version)
    problems = check_quiz(generated.quiz, passage)

    if problems:
        print(f"\n{passage.id}: 검사에서 걸러졌습니다. 같은 지문으로 한 번만 다시 만듭니다.")
        for p in problems:
            print(f"  - {p}")
        generated = generate_quiz(passage, prompt_version=prompt_version, retry_notes=problems)
        problems = check_quiz(generated.quiz, passage)

    show(generated, passage)

    if problems:
        print(f"\n{passage.id}: 재시도 후에도 문제가 남아 저장하지 않습니다.")
        for p in problems:
            print(f"  - {p}")
        return False

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / f"{passage.id}.json"
    out.write_text(
        json.dumps(generated.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\n{passage.id}: 검사 통과 → {out.relative_to(ROOT)}")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="지문에서 문항·해설 생성")
    parser.add_argument("passage_ids", nargs="*", help="예: fx-001")
    parser.add_argument("--all", action="store_true", help="fixtures 전체")
    parser.add_argument("--dry-run", action="store_true", help="API 호출 없이 프롬프트만 출력")
    parser.add_argument("--prompt", default=DEFAULT_PROMPT_VERSION, help="프롬프트 버전")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=True)  # .env 를 항상 우선

    if args.all:
        passages = load_all_passages()
    elif args.passage_ids:
        passages = [load_passage(pid) for pid in args.passage_ids]
    else:
        parser.error("지문 ID를 지정하거나 --all 을 쓰세요.")

    ok = 0
    for p in passages:
        try:
            if run_one(p, dry_run=args.dry_run, prompt_version=args.prompt):
                ok += 1
        except RuntimeError as e:  # 키 없음, 모델 거절 등 사용자가 조치할 수 있는 오류
            print(f"\n{p.id}: {e}")
            return 1

    if not args.dry_run:
        print(f"\n완료: {ok}/{len(passages)} 편 저장")
    return 0 if ok == len(passages) else 1


if __name__ == "__main__":
    raise SystemExit(main())
