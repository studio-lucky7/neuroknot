#!/usr/bin/env python
"""rec/raw/ 의 기사에 카테고리를 붙여 rec/passages/ 에 저장한다. (2단계: 분류)

  python scripts/run_classify.py                 카테고리당 12편까지
  python scripts/run_classify.py --limit 10      10편만 시험 삼아
  python scripts/run_classify.py --target 20     카테고리당 20편까지

이미 passages/ 에 있는 기사는 건너뛴다. 중간에 멈췄다 다시 돌려도 된다.
후보가 **모두 목표를 채운** 기사는 모델을 부르지 않고 건너뛴다. 호출을 아끼기 위해서다.
"""

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from neuroknot_rec.categories import CATEGORY_LABELS  # noqa: E402
from neuroknot_rec.classify import classify  # noqa: E402
from neuroknot_rec.criteria import check_passage  # noqa: E402
from neuroknot_rec.ministries import candidates_for  # noqa: E402
from neuroknot_rec.schemas import Passage  # noqa: E402
from neuroknot_rec.sources.base import RawArticle  # noqa: E402

RAW_DIR = ROOT / "raw"
PASSAGE_DIR = ROOT / "passages"


def current_counts() -> Counter[str]:
    """이미 모아 둔 지문을 카테고리별로 센다."""
    counts: Counter[str] = Counter()
    for path in PASSAGE_DIR.glob("*.json"):
        counts[json.loads(path.read_text(encoding="utf-8"))["category"]] += 1
    return counts


def report(counts: Counter[str], target: int) -> None:
    for cid, label in CATEGORY_LABELS.items():
        mark = "✓" if counts[cid] >= target else " "
        print(f"  {mark} {label:10} {counts[cid]:>2} / {target}")


def main() -> int:
    parser = argparse.ArgumentParser(description="지문 카테고리 분류 (2단계)")
    parser.add_argument("--target", type=int, default=12, help="카테고리당 목표 편수")
    parser.add_argument("--limit", type=int, default=0, help="처리할 기사 수 (0이면 제한 없음)")
    parser.add_argument("--delay", type=float, default=4.0, help="모델 호출 간격(초)")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env", override=True)
    PASSAGE_DIR.mkdir(exist_ok=True)

    counts = current_counts()
    print("시작 시점")
    report(counts, args.target)
    print()

    skipped: Counter[str] = Counter()
    added = 0
    processed = 0

    for path in sorted(RAW_DIR.glob("*.json")):
        if all(counts[cid] >= args.target for cid in CATEGORY_LABELS):
            print("\n모든 카테고리가 목표를 채웠습니다.")
            break
        if args.limit and processed >= args.limit:
            break

        article = RawArticle.model_validate_json(path.read_text(encoding="utf-8"))
        out = PASSAGE_DIR / f"kr-{article.source_id}.json"
        if out.exists():
            continue

        cands = candidates_for(article.publisher)
        if not cands:
            skipped["표에 없는 기관"] += 1
            continue
        if all(counts[cid] >= args.target for cid in cands):
            skipped["후보 카테고리가 이미 다 참"] += 1
            continue

        processed += 1
        if len(cands) > 1:
            time.sleep(args.delay)  # 모델을 부르기 직전에만 쉰다

        result = classify(article)
        if result.category is None:
            skipped["분류 못 함"] += 1
            print(f"  - {article.source_id} {result.reason[:70]}")
            continue

        passage = Passage(
            id=f"kr-{article.source_id}",
            title=article.title,
            category=result.category,
            source=article.source,
            source_url=article.source_url,
            license=article.license,
            body=article.body,
        )
        problems = check_passage(passage)
        if problems:
            skipped["최종 검사 탈락"] += 1
            print(f"  - {article.source_id} {problems[0]}")
            continue

        out.write_text(passage.model_dump_json(indent=2) + "\n", encoding="utf-8")
        counts[result.category] += 1
        added += 1
        print(f"  + {passage.id} [{CATEGORY_LABELS[result.category]}] {passage.title[:30]}")

    print(f"\n처리 {processed}편 → 새로 저장 {added}편")
    print("\n[카테고리별 현황]")
    report(counts, args.target)
    print("\n[건너뛴 이유]")
    for reason, count in skipped.most_common():
        print(f"  {count:>4}편  {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())