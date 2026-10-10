"""一次性迁移:旧测试 fn(..., run_query=lambda s: ROWS) → 解析函数(ROWS[, langs])。
用法:python migrate_run_query_tests.py <file> <fn> [<fn>...]"""

import ast
import sys
from pathlib import Path

TARGET = {
    "fetch_wikidata_labels": ("_labels_from_rows", True),
    "fetch_artist_i18n_facts": ("_artist_i18n_from_rows", True),
    "resolve_creator_qid": ("_creator_from_rows", False),
    "fetch_artist_facts": ("_artist_facts_from_rows", False),
    "fetch_rich_facts": ("_rich_from_rows", False),
}


def offsets(src):
    starts, pos = [0], 0
    for line in src.splitlines(keepends=True):
        pos += len(line)
        starts.append(pos)
    return lambda ln, col: starts[ln - 1] + col


def main(path, fns):
    src = Path(path).read_text()
    off = offsets(src)
    tree = ast.parse(src)
    edits = []  # (start, end, text)
    # 只处理顶层测试函数(嵌套的 fake 函数里没有目标调用;ast.walk 嵌套会重复处理)
    for fdef in [n for n in tree.body if isinstance(n, ast.FunctionDef)]:
        replaced = []  # (call, new_name)
        for call in [n for n in ast.walk(fdef) if isinstance(n, ast.Call)]:
            name = getattr(call.func, "id", None)
            if name not in fns:
                continue
            kws = {k.arg: k.value for k in call.keywords}
            if "run_query" not in kws or "artist_qid" in kws:
                continue
            rq = kws["run_query"]
            if isinstance(rq, ast.Lambda):
                rows = ast.get_source_segment(src, rq.body)
            else:
                rows = f"{ast.get_source_segment(src, rq)}(None)"
            new, with_langs = TARGET[name]
            args = [rows]
            if with_langs:
                args.append(ast.get_source_segment(src, call.args[1]))
            edits.append(
                (
                    off(call.lineno, call.col_offset),
                    off(call.end_lineno, call.end_col_offset),
                    f"{new}({', '.join(args)})",
                )
            )
            replaced.append((call, new))
        if not replaced:
            continue
        skip = {id(c.func) for c, _ in replaced}
        for imp in [
            n
            for n in ast.walk(fdef)
            if isinstance(n, ast.ImportFrom)
            and (n.module or "").endswith(("material", "evidence"))
        ]:
            still = [
                a.name
                for a in imp.names
                if any(
                    isinstance(x, ast.Name) and x.id == a.name and id(x) not in skip
                    for x in ast.walk(fdef)
                )
            ]
            is_ev = imp.module.endswith("evidence")
            add = {nm for _, nm in replaced if (nm == "_rich_from_rows") == is_ev}
            final = sorted(set(still) | add)
            edits.append(
                (
                    off(imp.lineno, imp.col_offset),
                    off(imp.end_lineno, imp.end_col_offset),
                    f"from {imp.module} import {', '.join(final)}",
                )
            )
    for s, e, t in sorted(edits, reverse=True):
        src = src[:s] + t + src[e:]
    Path(path).write_text(src)
    print(f"{path}: {len(edits)} edits")


if __name__ == "__main__":
    main(sys.argv[1], set(sys.argv[2:]))
