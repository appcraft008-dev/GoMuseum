"""存量修:繁体位里漏出的简体字(2026-09-07)。

新加的简繁闸只管**新内容**;prod 已发布的这批是闸装上之前进来的:
  标题 435/27132 · 作者名 106/4183 · 正文 82/2659 · 问答 31/1123 · 作者简介 17/191

做的是**定点正字**,不是改写:只把简体专有字换成繁体形(「全景图」→「全景圖」),
繁体里本来就合法的字(里/台/后/秘/群/床)一个不动。读音不变,所以**已生成的音频
仍然念得对,不需要失效重跑** —— 这跟"改正文事实"那类改动不是一回事(纪律 28 补充②
管的是后者)。

⚠️ dry-run 另报一个「归一化救不了」的计数,别把它当脏值:抽查下来那 63 条
标题基本都**合法** —— 卢浮宫埃及/近东部的藏品标题天然带馆藏编号与音译名
(「Orthostat碎片-AO 10886」「鱷魚 Shebek Ra-E 16358」「Nakhti的內棺」),
被既有的"拉丁占比 >40%"规则判成非中文。这是那条规则在短标题上的误报,
与简繁无关,也不影响显示 —— 标题走归一化不走判否,不会被挡下来。

默认 dry-run。`--apply` 才写。幂等可重跑。
"""

import sys

sys.path.insert(0, ".")

LANG = "zh-hant"


def _fix(s):
    from app.services.enrichment.lang_detect import to_traditional

    return to_traditional(s) if s else s


def scan(db, apply=False):
    from app.models.artist import Artist
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
    from app.models.museum_object import MuseumObject
    from app.services.enrichment.lang_detect import text_in_language

    stats = {}
    samples = []
    latin_left = 0

    def note(label, n, changed):
        stats[label] = {"扫描": n, "改动": changed}

    # ① 段落正文 / ② 问答
    rows = db.query(ObjectContentSection).filter_by(language=LANG).all()
    changed = 0
    for r in rows:
        new = _fix(r.body)
        if new != r.body:
            changed += 1
            if len(samples) < 8:
                samples.append(("正文", (r.body or "")[:40], (new or "")[:40]))
            if apply:
                r.body = new
    note("段落正文", len(rows), changed)

    rows = db.query(ObjectSuggestedQuestion).filter_by(language=LANG).all()
    changed = 0
    for r in rows:
        q, a = _fix(r.question), _fix(r.answer)
        if (q, a) != (r.question, r.answer):
            changed += 1
            if apply:
                r.question, r.answer = q, a
    note("问答", len(rows), changed)

    # ③ 标题(JSON 字段,须整体重赋值 SQLAlchemy 才认脏)
    rows = db.query(MuseumObject).all()
    changed = 0
    for o in rows:
        ti = (o.attributes or {}).get("title_i18n") or {}
        cur = ti.get(LANG)
        if not cur:
            continue
        new = _fix(cur)
        if new != cur:
            changed += 1
            if len(samples) < 16:
                samples.append(("标题", cur, new))
            if apply:
                o.attributes = {**o.attributes, "title_i18n": {**ti, LANG: new}}
        elif not text_in_language(cur, LANG):
            latin_left += 1  # 归一化救不了的(多为带馆藏编号的合法标题,见模块 docstring)
    note("标题", len(rows), changed)

    # ④ 作者名 / ⑤ 作者简介
    rows = db.query(Artist).all()
    changed = bio_changed = 0
    for a in rows:
        ni = a.name_i18n or {}
        cur = ni.get(LANG)
        if cur:
            new = _fix(cur)
            if new != cur:
                changed += 1
                if apply:
                    a.name_i18n = {**ni, LANG: new}
            elif not text_in_language(cur, LANG):
                latin_left += 1
        bio = a.bio or {}
        cur = bio.get(LANG)
        if cur:
            new = _fix(cur)
            if new != cur:
                bio_changed += 1
                if apply:
                    a.bio = {**bio, LANG: new}
    note("作者名", len(rows), changed)
    note("作者简介", len(rows), bio_changed)

    if apply:
        db.commit()
    return stats, samples, latin_left


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="不加就是 dry-run")
    ns = ap.parse_args()

    db = SessionLocal()
    stats, samples, latin_left = scan(db, apply=ns.apply)
    print("=== 繁体位简体字正字", "(已写入)" if ns.apply else "(dry-run,未写)", "===")
    for k, v in stats.items():
        print(f"  {k}: 扫描 {v['扫描']} → 改动 {v['改动']}")
    print(f"\n  归一化救不了的(多为带馆藏编号的合法标题,非缺陷): {latin_left}")
    print("\n抽样:")
    for kind, a, b in samples:
        print(f"  [{kind}] {a}\n       → {b}")
