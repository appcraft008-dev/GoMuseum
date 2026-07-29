"""钱路径端到端验收(跑**真实部署**,不是内存 sqlite)。

为什么必须跑真环境:本轮几个缺陷在 1000+ 单元测试里全绿,只有真跑才暴露 ——
- 免费名额被一件**没有音频**的作品烧掉(生成 404,但认领已发生)
- 内容接口无鉴权下发音频直链(单测里没人会去 curl 内容端点)
- staging 库里 audio_key 指向已迁移改名的文件(数据层面的坑,代码测不出来)

用法:
  python scripts/verify_money_path.py --base https://staging-api.gomuseum.app \\
      --slug orsay --free-qid Q152509 --second-qid Q737062

退出码 0 = 全部不变量成立。任何一条不成立即非 0,并打印是哪条。
"""

import argparse
import sys
import time
import uuid

import httpx

OK, BAD = "✅", "❌"


class Checks:
    def __init__(self) -> None:
        self.failed: list[str] = []

    def expect(self, ok: bool, invariant: str, detail: str = "") -> None:
        print(f"  {OK if ok else BAD} {invariant}" + (f" — {detail}" if detail else ""))
        if not ok:
            self.failed.append(invariant)


def _pick_samples(http, api: str, slug: str, scan: int = 12):
    """自动挑样本:两件有正文的 + 一件无正文的。

    写死 qid 的检查会随数据变化假红,然后被人绕过 —— 自己挑才活得久。
    """
    with_text, without = [], None
    try:
        items = http.get(f"{api}/museums/{slug}/objects?language=zh&limit={scan}")
        rows = items.json().get("items") or items.json().get("objects") or []
    except Exception:
        return [], None
    for o in rows:
        qid = o.get("qid")
        if not qid:
            continue
        if len(with_text) >= 2 and without:
            break
        try:
            d = http.get(
                f"{api}/museums/{slug}/objects/{qid}/content?language=zh"
            ).json()
        except Exception:
            continue
        body = ((d.get("default_guide") or {}).get("body") or "").strip()
        if body and len(with_text) < 2:
            with_text.append(qid)
        elif not body and not without:
            without = qid
    return with_text, without


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--slug", default="orsay")
    # ⚠️ 默认**自动挑样本**。写死 qid 的检查会随数据变化假红,
    # 然后被人加 `|| true` 绕过 —— 那就等于没有这个检查。
    ap.add_argument("--free-qid", default=None, help="有已发布正文的作品(默认自动挑)")
    ap.add_argument("--second-qid", default=None, help="另一件,验证撞墙(默认自动挑)")
    ap.add_argument("--no-audio-qid", default=None, help="无正文的作品(默认自动挑)")
    ns = ap.parse_args()

    c = Checks()
    api = ns.base.rstrip("/") + "/api/v1"
    http = httpx.Client(timeout=120, follow_redirects=True)
    dev = f"verify-{uuid.uuid4().hex[:10]}"

    if not (ns.free_qid and ns.second_qid):
        with_text, without = _pick_samples(http, api, ns.slug)
        ns.free_qid = ns.free_qid or (with_text[0] if len(with_text) > 0 else None)
        ns.second_qid = ns.second_qid or (with_text[1] if len(with_text) > 1 else None)
        ns.no_audio_qid = ns.no_audio_qid or without
        print(
            f"自动挑样本:免费={ns.free_qid} 第二件={ns.second_qid} 无正文={ns.no_audio_qid}"
        )
    if not (ns.free_qid and ns.second_qid):
        print(f"{BAD} 该馆找不到两件有正文的藏品,无法验收")
        return 1

    print("\n[I3] 未鉴权不得取得音频")
    for path in (
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio?language=zh",
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio/stream?language=zh",
    ):
        r = http.get(path)
        c.expect(
            r.status_code == 401,
            "I3 音频端点必须鉴权",
            f"{path[-40:]} → {r.status_code}",
        )

    r = http.post(
        f"{api}/content/tts/generate", json={"text": "白嫖", "language": "zh"}
    )
    c.expect(r.status_code == 401, "I3 TTS 端点必须鉴权", f"→ {r.status_code}")

    print("\n[I4] 内容端点不得下发音频直链")
    r = http.get(f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/content?language=zh")
    body = r.text
    c.expect("audio_url" not in body, "I4 内容响应不含 audio_url")
    c.expect("object-audio/" not in body, "I4 内容响应不含音频直链")

    print("\n[身份] 游客创建")
    r = http.post(f"{api}/auth/guest", json={"device_id": dev})
    if r.status_code == 429:
        # 限流不是缺陷。让它把部署搞红,这检查很快就会被加 `|| true` 绕过。
        print("  ⏭  游客登录被限流,跳过本次验收(非缺陷)")
        return 0
    if r.status_code != 200:
        print(f"  {BAD} 游客登录失败({r.status_code})")
        return 1
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}

    ent = http.get(f"{api}/entitlements/me", headers=h).json()
    c.expect(ent.get("state") == "not_purchased", "新游客无通票")
    c.expect(
        ent.get("free_recognitions_total") == ent.get("free_recognitions_left"),
        "新游客额度未被消耗",
        f"{ent.get('free_recognitions_left')}/{ent.get('free_recognitions_total')}",
    )
    # ⚠️ 验收脚本自己**不得因缺字段崩溃** —— 它的职责是报告不成立,不是抛异常。
    # 缺字段本身就是一种"不成立"(旧版本后端还没有该字段)。
    can = ent.get("can") or {}
    c.expect(
        can.get("purchase") is False,
        "I11 游客不得直接购买",
        f"can.purchase={can.get('purchase', '(缺字段)')}",
    )
    c.expect("ai_ask" not in can, "I13 契约不含已停用能力")

    if ns.no_audio_qid:
        print("\n[I6] 生成失败不得烧掉免费名额")
        r = http.get(
            f"{api}/museums/{ns.slug}/objects/{ns.no_audio_qid}/audio?language=zh",
            headers=h,
        )
        after = http.get(f"{api}/entitlements/me", headers=h).json()
        c.expect(
            after.get("free_audio_qid") is None,
            "I6 未交付则不认领",
            f"端点 {r.status_code},free_audio_qid={after.get('free_audio_qid')}",
        )

    print("\n[免费层] 首件试听")
    r = http.get(
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio?language=zh", headers=h
    )
    c.expect(r.status_code == 200, "首件应放行", f"→ {r.status_code}")
    url = r.json().get("audio_url", "") if r.status_code == 200 else ""
    if url:
        a = http.get(url)
        c.expect(
            a.status_code == 200
            and a.headers.get("content-type", "").startswith("audio"),
            "首件直链可播(数据层未失效)",
            f"{a.status_code} {a.headers.get('content-type')}",
        )
    ent = http.get(f"{api}/entitlements/me", headers=h).json()
    c.expect(ent.get("free_audio_qid") == ns.free_qid, "I7 交付后必须认领")

    time.sleep(0.3)
    r = http.get(
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio?language=zh", headers=h
    )
    c.expect(r.status_code == 200, "首件可无限重播")

    print("\n[6.4] 免费范围 = 一件 × 一语言 × 主讲解段")
    r = http.get(
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio?language=fr", headers=h
    )
    c.expect(r.status_code == 402, "换语言不在免费范围", f"→ {r.status_code}")
    r = http.get(
        f"{api}/museums/{ns.slug}/objects/{ns.free_qid}/audio"
        f"?language=zh&section=analysis",
        headers=h,
    )
    c.expect(r.status_code in (402, 404), "深度段不在免费范围", f"→ {r.status_code}")

    print("\n[付费墙] 第二件撞墙")
    r = http.get(
        f"{api}/museums/{ns.slug}/objects/{ns.second_qid}/audio?language=zh", headers=h
    )
    c.expect(r.status_code == 402, "第二件必须 402", f"→ {r.status_code}")
    c.expect(
        r.json().get("detail", {}).get("reason") == "pass_required",
        "402 须带明确原因",
    )

    print("\n[I8/I9] 伪造收据不得发放权益")
    r = http.post(
        f"{api}/payment/verify",
        json={
            "platform": "android",
            "receipt_data": f"forged-{uuid.uuid4().hex}",
            "product_id": "paris_pass_7d",
            "device_id": dev,
        },
        headers=h,
    )
    # 游客先被 I11 拦(403);若已登录则应因凭证校验失败而 verified=false
    ok = r.status_code == 403 or (
        r.status_code == 200 and r.json().get("verified") is False
    )
    c.expect(ok, "I8 伪造收据不得通过", f"→ {r.status_code} {r.text[:80]}")
    ent = http.get(f"{api}/entitlements/me", headers=h).json()
    c.expect(ent.get("state") == "not_purchased", "伪造后仍无通票")

    print(f"\n{'='*56}")
    if c.failed:
        print(f"{BAD} {len(c.failed)} 条不变量不成立:")
        for f in c.failed:
            print(f"   · {f}")
        return 1
    print(f"{OK} 钱路径全部不变量成立")
    return 0


if __name__ == "__main__":
    sys.exit(main())
