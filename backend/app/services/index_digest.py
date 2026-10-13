"""进程内索引的「目录指纹」:只对索引真正用到的列算摘要。

为什么不用 (行数, max(updated_at)):懒生成只写看图描述/讲解状态,也会推进 updated_at,
于是每次有人看冷门件,下一轮到期就全量重建(搜索 ~20s 纯 Python 抢 GIL),prod 10-13
识别被拖到 13s。只摘要索引列,改这些列之外的东西就不重建。
"""

from __future__ import annotations

import hashlib

from sqlalchemy import text


def column_digest(db, *cols) -> str:
    """所选列全表的摘要(行序无关)。PG 在库里算(prod 2.7 万件 0.57s,不占 GIL);
    其它方言(测试用 SQLite)在 Python 里算同一件事。"""
    q = db.query(*cols)
    dialect = db.get_bind().dialect
    if dialect.name == "postgresql":
        sql = q.statement.compile(
            dialect=dialect, compile_kwargs={"literal_binds": True}
        )
        return (
            db.execute(
                text(
                    f"select md5(string_agg(t::text, E'\\n' order by t::text)) "
                    f"from ({sql}) t"
                )
            ).scalar()
            or ""
        )
    h = hashlib.md5()
    for line in sorted(repr(tuple(r)) for r in q):
        h.update(line.encode())
    return h.hexdigest()
