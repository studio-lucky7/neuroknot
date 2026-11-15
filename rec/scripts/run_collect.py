#!/usr/bin/env python
"""정책브리핑에서 기사를 모아 rec/raw/ 에 저장한다. (1단계: 수집)

  python scripts/run_collect.py --limit 30          30편까지 시도 (처음엔 이걸로)
  python scripts/run_collect.py --limit 400         본 수집
  python scripts/run_collect.py --limit 5 --delay 1 아주 짧게 시험

카테고리는 여기서 정하지 않는다. 2단계(run_classify.py)의 몫이다.
이미 받아 둔 기사는 건너뛰므로 중간에 멈췄다가 다시 돌려도 된다.
"""

import argparse
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from neuroknot_rec.criteria import check_text  # noqa: E402
from neuroknot_rec.sources.korea_kr import KoreaKrSource  # noqa: E402

RAW_DIR = ROOT / "raw"


def main() -> int:
    parser = argparse.ArgumentParser(description="지문 후보 수집 (1단계)")
    parser.add_argument("--limit", type=int, default=30, help="시도할 기사 수")
    parser.add_argument("--delay", type=float, default=2.0, help="요청 간격(초)")
    args = parser.parse_args()

    RAW_DIR.mkdir(exist_ok=True)
    source = KoreaKrSource()
    kept: Counter[str] = Counter()
    dropped: Counter[str] = Counter()
    tried = 0

    print("사이트맵에서 주소를 받는 중...")
    urls = list(source.iter_article_urls())
    print(f"기사 주소 {len(urls)}개. 최대 {args.limit}편 시도합니다.\n")

    for url in urls:
        if tried >= args.limit:
            break

        article_id = url.rsplit("=", 1)[-1]
        out = RAW_DIR / f"korea_kr-{article_id}.json"
        if out.exists():
            continue  # 이미 받아 둔 기사

        tried += 1
        time.sleep(args.delay)  # 상대 서버를 배려한다

        try:
            article = source.fetch(url)
        except Exception as error:  # 네트워크 오류는 건너뛰고 계속한다
            dropped["가져오기 실패"] += 1
            print(f"  ! {article_id} {type(error).__name__}")
            continue

        if article is None:
            dropped["공공누리 표시 없음 / 본문 없음"] += 1
            continue

        problems = check_text(article.title, article.body, article.license)
        if problems:
            # 이유별로 몇 편이 걸렸는지 세기 위해 숫자 부분은 떼어 낸다
            dropped[problems[0].split("→")[0].strip()] += 1
            continue

        out.write_text(article.model_dump_json(indent=2) + "\n", encoding="utf-8")
        kept[article.publisher] += 1
        print(f"  + {article_id} {len(article.body):>5}자 {article.publisher} {article.title[:28]}")

    print(f"\n시도 {tried}편 → 저장 {sum(kept.values())}편")

    print("\n[저장된 기사의 기관]")
    for name, count in kept.most_common():
        print(f"  {count:>3}편  {name}")

    print("\n[버린 이유]")
    for reason, count in dropped.most_common():
        print(f"  {count:>3}편  {reason}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())