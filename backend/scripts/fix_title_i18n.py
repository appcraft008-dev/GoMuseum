"""存量修复:标题(与作者名)里的两类污染。

① 回贴的「Name:」标签:名字翻译 prompt 的 user 是 `Name:\\n{name}`,模型把标签也翻了
   (it「Nome:」663 / fr「Nom :」38 / es 19 …,prod 2026-09-30)。根因已在 strip_name 修。
② 维基消歧后缀:「昼食 (モネ)」「阿尔弗雷德·勒罗伊 (画作)」—— 括号里是**本作品作者**
   的名字或「画/tableau」这类泛称,且英文标题本身不带括号(带括号的多是正式副标题,
   如「ヴィシー(木立)」,一律不动)。

标题改了,正文/问答里原样出现的旧标题同步替换 ——**有音频的行跳过**(后缀会被念出来,
改字不改音就对不上;不重录)。作者卡是共享实体(纪律 37):只剥①的标签,单列报数。
改前原文备份到 --backup。

用法(容器内):
    python scripts/fix_title_i18n.py                                   # dry-run
    python scripts/fix_title_i18n.py --apply --backup /tmp/title_fix_backup.json
幂等。
"""

import argparse
import json
import re
import sys

sys.path.insert(0, "/app")

from sqlalchemy.orm.attributes import flag_modified  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402
from app.models.artist import Artist  # noqa: E402
from app.models.content import (  # noqa: E402
    ObjectContentSection,
    ObjectSuggestedQuestion,
)
from app.models.museum_object import MuseumObject  # noqa: E402
from app.services.enrichment.translator import _NAME_LABEL  # noqa: E402

_TAIL = re.compile(r"\s*[（(]([^()（）]{1,40})[)）]\s*$")
_GENERIC = {
    "画", "畫", "绘画", "繪畫", "画作", "畫作", "絵画", "絵", "그림", "회화",
    "painting", "tableau", "peinture", "gemälde", "dipinto", "pintura", "obraz",
}  # fmt: skip


def _artist_names(artist) -> set[str]:
    if artist is None:
        return set()
    names = {artist.name_en or "", *(artist.name_i18n or {}).values()}
    return {n for n in names if n}


def strip_label(name: str) -> str:
    """只剥「Name:」标签。⚠️ 不用 strip_name:它还剥两端引号,对库里的正式标题
    (「…dite "Vierge d'humilité"」)会剥坏一侧,#414 踩过。"""
    return _NAME_LABEL.sub("", name).strip()


def clean_title(title: str, en_title: str, artist_names: set[str]) -> str:
    t = strip_label(title)
    m = _TAIL.search(t)
    if m and not re.search(r"[（(]", en_title or ""):
        inner = m.group(1).strip()
        by_artist = len(inner) > 1 and any(
            inner == n or inner == n.split()[-1] or inner in n for n in artist_names
        )
        if by_artist or inner.lower() in _GENERIC:
            t = t[: m.start()].rstrip()
    return t


def plan(db) -> dict:
    artists = {a.qid: a for a in db.query(Artist).all()}
    objs, texts = [], []
    for o in db.query(MuseumObject).all():
        attrs = o.attributes or {}
        ti = attrs.get("title_i18n") or {}
        en = ti.get("en") or o.title_en or ""
        names = _artist_names(artists.get(attrs.get("artist_qid")))
        new_ti = {k: clean_title(v, en, names) if v else v for k, v in ti.items()}
        changed = {k: (ti[k], new_ti[k]) for k in ti if new_ti[k] != ti[k]}
        cols = {
            c: (getattr(o, c), clean_title(getattr(o, c), en, names))
            for c in ("title_en", "title_zh")
            if getattr(o, c) and clean_title(getattr(o, c), en, names) != getattr(o, c)
        }
        if not (changed or cols):
            continue
        objs.append((o, changed, cols))
        for lang, (old, new) in changed.items():
            for model, fields in (
                (ObjectContentSection, ("body",)),
                (ObjectSuggestedQuestion, ("question", "answer")),
            ):
                for row in db.query(model).filter_by(object_id=o.id, language=lang):
                    upd = {
                        f: getattr(row, f).replace(old, new)
                        for f in fields
                        if getattr(row, f) and old in getattr(row, f)
                    }
                    if upd:
                        texts.append((row, upd, bool(row.audio_key)))
    arts = []
    for a in artists.values():
        ni = a.name_i18n or {}
        new = {k: strip_label(v) if v else v for k, v in ni.items()}
        if new != ni:
            arts.append((a, {k: (ni[k], new[k]) for k in ni if new[k] != ni[k]}))
    return {"objects": objs, "texts": texts, "artists": arts}


def apply(db, p: dict, backup_path: str) -> None:
    backup = {
        "objects": [
            {
                "qid": o.qid,
                "title_i18n": {k: v[0] for k, v in ch.items()},
                **{c: v[0] for c, v in cols.items()},
            }
            for o, ch, cols in p["objects"]
        ],
        "texts": [
            {"table": r.__tablename__, "id": str(r.id), **{f: getattr(r, f) for f in u}}
            for r, u, audio in p["texts"]
            if not audio
        ],
        "artists": [
            {"qid": a.qid, "name_i18n": {k: v[0] for k, v in ch.items()}}
            for a, ch in p["artists"]
        ],
    }
    with open(backup_path, "w") as f:
        json.dump(backup, f, ensure_ascii=False)
    for o, ch, cols in p["objects"]:
        attrs = dict(o.attributes or {})
        attrs["title_i18n"] = {
            **attrs["title_i18n"],
            **{k: v[1] for k, v in ch.items()},
        }
        o.attributes = attrs
        flag_modified(o, "attributes")
        for c, (_, new) in cols.items():
            setattr(o, c, new)
    for row, upd, audio in p["texts"]:
        if audio:
            continue  # 后缀会被念出来:改字不改音就对不上,不动
        for f, v in upd.items():
            setattr(row, f, v)
    for a, ch in p["artists"]:
        a.name_i18n = {**a.name_i18n, **{k: v[1] for k, v in ch.items()}}
        flag_modified(a, "name_i18n")
    db.commit()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--backup")
    a = ap.parse_args()
    if a.apply and not a.backup:
        raise SystemExit("--apply 必须带 --backup")
    db = SessionLocal()
    p = plan(db)
    n_titles = sum(len(ch) + len(cols) for _, ch, cols in p["objects"])
    print(f"作品 {len(p['objects'])} 件,标题 {n_titles} 条要改。样例:")
    for o, ch, cols in p["objects"][:25]:
        for k, (old, new) in {**ch, **cols}.items():
            print(f"  {o.qid} {k}: {old!r} → {new!r}")
    skip = [t for t in p["texts"] if t[2]]
    print(
        f"正文/问答里引用旧标题:{len(p['texts'])} 行,其中有音频 {len(skip)} 行"
        f"(跳过不改,音频不作废)"
    )
    print(f"作者卡(共享实体,只剥标签):{len(p['artists'])} 位")
    for art, ch in p["artists"]:
        print(f"  {art.qid} {ch}")
    if a.apply:
        apply(db, p, a.backup)
        print(f"已写入;原文备份在 {a.backup}")
    else:
        print("dry-run(加 --apply --backup <路径> 生效)")
