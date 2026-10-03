#!/usr/bin/env python
"""설정이 제대로 됐는지 확인한다. 문항을 만들기 전에 먼저 실행해 보면 좋다.

  python scripts/check_setup.py

확인하는 것
  1) .env 에서 GEMINI_API_KEY 를 읽어오는가
  2) 그 키로 실제 접속이 되는가
  3) 지금 계정에서 쓸 수 있는 모델 이름은 무엇인가
     (모델 이름은 계속 바뀌므로, 여기 나온 이름을 .env 의 GEMINI_MODEL 에 넣으면 된다)
  4) 샘플 지문이 제대로 읽히는가
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv  # noqa: E402

from neuroknot_gen.generate import make_client, model_name  # noqa: E402
from neuroknot_gen.loader import load_all_passages  # noqa: E402


def main() -> int:
    load_dotenv(ROOT / ".env", override=True)  # .env 를 항상 우선

    print("1) 샘플 지문")
    passages = load_all_passages()
    for p in passages:
        print(f"   {p.id}  {p.category:12s} {len(p.body):5d}자  {p.title[:34]}")
    if not passages:
        print("   없음 — gen/fixtures/ 를 확인하세요.")
        return 1

    print("\n2) API 키")
    try:
        client = make_client()
    except RuntimeError as e:
        print(f"   {e}")
        return 1
    print("   .env 에서 키를 읽었습니다.")

    print("\n3) 접속 확인 및 쓸 수 있는 모델")
    try:
        names = []
        for m in client.models.list():
            actions = getattr(m, "supported_actions", None) or []
            if not actions or "generateContent" in actions:
                names.append(m.name.replace("models/", ""))
    except Exception as e:  # 키가 틀렸거나 네트워크 문제
        print(f"   접속 실패: {type(e).__name__}: {e}")
        print("   키가 올바른지, 인터넷 연결이 되는지 확인하세요.")
        return 1

    for n in sorted(names)[:30]:
        print(f"   - {n}")
    if len(names) > 30:
        print(f"   ... 외 {len(names) - 30}개")

    current = model_name()
    print(f"\n4) 지금 쓰도록 설정된 모델: {current}")
    if current in names:
        print("   사용 가능합니다. 이제 문항을 만들 수 있습니다:")
        print("   python scripts/run_generate.py fx-001")
    else:
        print("   이 이름은 위 목록에 없습니다.")
        print("   위에서 하나 골라 .env 에 GEMINI_MODEL=<이름> 으로 넣으세요.")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
