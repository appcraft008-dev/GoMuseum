"""预热馆包讲解缓存

对馆包内热门馆藏批量调用 /content/explanation（命中缓存自动跳过，幂等），
让游客访问热门展品时讲解即时返回且不消耗 OpenAI 额度。

用法:
    python scripts/prewarm_explanations.py --museum orsay --limit 20 \
        [--base-url http://localhost:8000] [--language zh]
"""

import argparse
import json
import sys
import time
from pathlib import Path

import requests


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--museum", default="orsay")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--language", default="zh")
    parser.add_argument("--base-url", default="http://localhost:8000")
    args = parser.parse_args()

    pack_path = (
        Path(__file__).resolve().parent.parent / "museum_packs" / f"{args.museum}.json"
    )
    pack = json.loads(pack_path.read_text())
    artworks = pack["artworks"][: args.limit]

    lang_suffix = "zh" if args.language == "zh" else "en"
    ok = warmed = failed = 0
    for i, art in enumerate(artworks, 1):
        payload = {
            "artwork_name": art[f"title_{lang_suffix}"],
            "artist": art[f"artist_{lang_suffix}"],
            "period": art[f"period_{lang_suffix}"],
            "language": args.language,
        }
        t0 = time.time()
        try:
            resp = requests.post(
                f"{args.base_url}/api/v1/content/explanation",
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            data = resp.json()
            elapsed = time.time() - t0
            hit = elapsed < 0.5
            fallback = data.get("fallback", False)
            status = "缓存命中" if hit else ("⚠ fallback" if fallback else "已生成")
            if fallback:
                failed += 1
            elif hit:
                ok += 1
            else:
                warmed += 1
            print(
                f"[{i}/{len(artworks)}] {payload['artwork_name']}: {status} ({elapsed:.1f}s)"
            )
            if not hit:
                time.sleep(1)  # 限速，避免触发限流/预算告警
        except Exception as e:  # noqa: BLE001
            failed += 1
            print(f"[{i}/{len(artworks)}] {payload['artwork_name']}: 失败 {e}")

    print(f"\n完成：新生成 {warmed}，已有缓存 {ok}，失败/降级 {failed}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
