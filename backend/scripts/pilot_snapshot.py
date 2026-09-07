"""按 qid 快照/回滚一批藏品的全部生成内容。

用于内容管线改动的 pilot：跑之前 snapshot，效果不好 restore 原样退回。

⚠️ 爆炸半径不止段落。`onboard generate --force` 会动四张表：
  - object_content_sections   正文/状态/**audio_key**
  - object_suggested_questions 问答
  - museum_objects            content_status / evidence_pack / title_zh / attributes
  - artists                   bio 等（**按作者 qid 全馆共享**，同作者的其他作品跟着变）

⚠️ audio_key 必须备。`_upsert_section` 在 body 变化时把它置空，但 **R2 里的 mp3 不删**
   —— 所以 restore 写回 audio_key，音频立刻复活，不用重灌。

⚠️ restore 会删除快照里没有的行（重生成可能新建段/问答），否则回滚不干净。

用法:
  python scripts/pilot_snapshot.py snapshot --qids Q1,Q2 --out /tmp/a.json
  python scripts/pilot_snapshot.py restore  --in /tmp/a.json
  python scripts/pilot_snapshot.py verify   --in /tmp/a.json   # 比对当前库与快照
"""

import argparse
import json
import sys
import uuid
from datetime import datetime

sys.path.insert(0, "/app")

from sqlalchemy import text as sql  # noqa: E402

from app.core.database import SessionLocal  # noqa: E402

SEC_COLS = [
    "language",
    "section_code",
    "body",
    "audio_key",
    "status",
    "model",
    "source",
    "generated_at",
    "audio_engine",
    "grounding_ratio",
]
QA_COLS = [
    "language",
    "sort",
    "question",
    "answer",
    "status",
    "model",
    "generated_at",
    "audio_key",
    "audio_engine",
]
OBJ_COLS = ["content_status", "evidence_pack", "title_zh", "title_en", "attributes"]
ART_COLS = [
    "name_zh",
    "name_en",
    "birth",
    "death",
    "nationality",
    "notable_works",
    "bio",
    "name_i18n",
    "nationality_i18n",
    "notable_works_i18n",
    "bio_audio",
    "bio_audio_engine",
]


def _j(v):
    return v.isoformat() if isinstance(v, datetime) else v


def _pg(v):
    """写回时给 psycopg2 用:dict/list 一律转 JSON 文本。

    ⚠️ 别维护"哪些列是 JSONB"的清单 —— 漏一列(实测漏了 artists.bio_audio)
    就是 `can't adapt type 'dict'`,而且只在真回滚那一刻才炸。按值类型判就不会漏。
    """
    return json.dumps(v, ensure_ascii=False) if isinstance(v, (dict, list)) else v


def _rows(db, table, cols, where, **kw):
    q = f"SELECT {','.join(cols)} FROM {table} WHERE {where}"
    return [
        {c: _j(v) for c, v in zip(cols, r)} for r in db.execute(sql(q), kw).fetchall()
    ]


def snapshot(qids: list[str], out: str) -> dict:
    db = SessionLocal()
    data = {"created_at": datetime.utcnow().isoformat(), "objects": {}, "artists": {}}
    for qid in qids:
        row = db.execute(
            sql("SELECT id, attributes FROM museum_objects WHERE qid=:q"), {"q": qid}
        ).fetchone()
        if not row:
            print(f"  ⚠ {qid} 不存在，跳过")
            continue
        oid, attrs = row
        data["objects"][qid] = {
            "object": _rows(db, "museum_objects", OBJ_COLS, "qid=:q", q=qid)[0],
            "sections": _rows(
                db, "object_content_sections", SEC_COLS, "object_id=:o", o=oid
            ),
            "qa": _rows(
                db, "object_suggested_questions", QA_COLS, "object_id=:o", o=oid
            ),
        }
        aqid = (attrs or {}).get("artist_qid")
        if aqid and aqid not in data["artists"]:
            got = _rows(db, "artists", ART_COLS, "qid=:q", q=aqid)
            if got:
                data["artists"][aqid] = got[0]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    ns = sum(len(v["sections"]) for v in data["objects"].values())
    nq = sum(len(v["qa"]) for v in data["objects"].values())
    print(
        f"✅ 快照 {len(data['objects'])} 件 / {ns} 段 / {nq} 问答 / "
        f"{len(data['artists'])} 作者 → {out}"
    )
    return data


def restore(path: str) -> None:
    db = SessionLocal()
    data = json.load(open(path, encoding="utf-8"))
    n_sec = n_qa = n_del = 0
    for qid, blob in data["objects"].items():
        row = db.execute(
            sql("SELECT id FROM museum_objects WHERE qid=:q"), {"q": qid}
        ).fetchone()
        if not row:
            print(f"  ⚠ {qid} 已不存在，跳过")
            continue
        oid = row[0]
        db.execute(
            sql(
                "UPDATE museum_objects SET "
                + ",".join(f"{c}=:{c}" for c in OBJ_COLS)
                + " WHERE qid=:q"
            ),
            {**{c: _pg(blob["object"][c]) for c in OBJ_COLS}, "q": qid},
        )
        # 先删净该件所有行，再原样插回 —— 比逐行 upsert + 找多余行简单可靠
        n_del += db.execute(
            sql("DELETE FROM object_content_sections WHERE object_id=:o"), {"o": oid}
        ).rowcount
        n_del += db.execute(
            sql("DELETE FROM object_suggested_questions WHERE object_id=:o"), {"o": oid}
        ).rowcount
        # ⚠️ id 必须自己生成:该列**没有库侧默认值**(模型里是 Python 侧 uuid.uuid4),
        # 裸 INSERT 不带 id 会 NotNullViolation —— 而这只会在真回滚那一刻才炸。
        for s in blob["sections"]:
            db.execute(
                sql(
                    "INSERT INTO object_content_sections (id,object_id,"
                    + ",".join(SEC_COLS)
                    + ") VALUES (:_id,:oid,"
                    + ",".join(f":{c}" for c in SEC_COLS)
                    + ")"
                ),
                {
                    **{k: _pg(v) for k, v in s.items()},
                    "oid": oid,
                    "_id": str(uuid.uuid4()),
                },
            )
            n_sec += 1
        for a in blob["qa"]:
            db.execute(
                sql(
                    "INSERT INTO object_suggested_questions (id,object_id,"
                    + ",".join(QA_COLS)
                    + ") VALUES (:_id,:oid,"
                    + ",".join(f":{c}" for c in QA_COLS)
                    + ")"
                ),
                {
                    **{k: _pg(v) for k, v in a.items()},
                    "oid": oid,
                    "_id": str(uuid.uuid4()),
                },
            )
            n_qa += 1
    for aqid, art in data.get("artists", {}).items():
        db.execute(
            sql(
                "UPDATE artists SET "
                + ",".join(f"{c}=:{c}" for c in ART_COLS)
                + " WHERE qid=:q"
            ),
            {**{c: _pg(art[c]) for c in ART_COLS}, "q": aqid},
        )
    db.commit()
    print(
        f"✅ 回滚：删 {n_del} 行 → 写回 {n_sec} 段 / {n_qa} 问答 / "
        f"{len(data.get('artists', {}))} 作者"
    )


def verify(path: str) -> int:
    """比对当前库与快照，返回不一致数（回滚后应为 0）。"""
    db = SessionLocal()
    data = json.load(open(path, encoding="utf-8"))
    bad = 0
    for qid, blob in data["objects"].items():
        row = db.execute(
            sql("SELECT id FROM museum_objects WHERE qid=:q"), {"q": qid}
        ).fetchone()
        if not row:
            print(f"  ✗ {qid} 不存在")
            bad += 1
            continue
        now = {
            (s["language"], s["section_code"]): s
            for s in _rows(
                db, "object_content_sections", SEC_COLS, "object_id=:o", o=row[0]
            )
        }
        snap = {(s["language"], s["section_code"]): s for s in blob["sections"]}
        if set(now) != set(snap):
            print(f"  ✗ {qid} 段集合不一致 (库{len(now)} vs 快照{len(snap)})")
            bad += 1
            continue
        for k, s in snap.items():
            for col in SEC_COLS:
                if now[k][col] != s[col]:
                    print(f"  ✗ {qid} {k} 的 {col} 不一致")
                    bad += 1
        # 问答 —— 漏了它,「回滚成功」的判据就是不完整的
        nq = {
            (a["language"], a["sort"]): a
            for a in _rows(
                db, "object_suggested_questions", QA_COLS, "object_id=:o", o=row[0]
            )
        }
        sq = {(a["language"], a["sort"]): a for a in blob["qa"]}
        if set(nq) != set(sq):
            print(f"  ✗ {qid} 问答集合不一致 (库{len(nq)} vs 快照{len(sq)})")
            bad += 1
        else:
            for k, a in sq.items():
                for col in QA_COLS:
                    if nq[k][col] != a[col]:
                        print(f"  ✗ {qid} 问答{k} 的 {col} 不一致")
                        bad += 1
        # museum_objects 上被 --force 动过的字段
        cur = _rows(db, "museum_objects", OBJ_COLS, "qid=:q", q=qid)[0]
        for col in OBJ_COLS:
            if cur[col] != blob["object"][col]:
                print(f"  ✗ {qid} museum_objects.{col} 不一致")
                bad += 1
    # 作者(全馆共享实体,--force 会重写 bio)
    for aqid, art in data.get("artists", {}).items():
        got = _rows(db, "artists", ART_COLS, "qid=:q", q=aqid)
        if not got:
            print(f"  ✗ 作者 {aqid} 不存在")
            bad += 1
            continue
        for col in ART_COLS:
            if got[0][col] != art[col]:
                print(f"  ✗ 作者 {aqid} 的 {col} 不一致")
                bad += 1
    print("✅ 与快照完全一致" if not bad else f"⚠ {bad} 处不一致")
    return bad


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("snapshot")
    s.add_argument("--qids", required=True)
    s.add_argument("--out", required=True)
    r = sub.add_parser("restore")
    r.add_argument("--in", dest="inp", required=True)
    v = sub.add_parser("verify")
    v.add_argument("--in", dest="inp", required=True)
    a = p.parse_args()
    if a.cmd == "snapshot":
        snapshot([x.strip() for x in a.qids.split(",") if x.strip()], a.out)
    elif a.cmd == "restore":
        restore(a.inp)
    else:
        sys.exit(1 if verify(a.inp) else 0)


if __name__ == "__main__":
    main()
