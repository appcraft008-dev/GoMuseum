from __future__ import annotations

from collections import Counter

_FIELDS = ["image", "artist_zh", "year", "title_zh", "title_en"]


def _has(o: dict, field: str) -> bool:
    if field == "image":
        return bool(o.get("image"))
    return bool(o.get(field))


def build_report(slug: str, objects: list[dict], as_markdown: bool = False):
    total = len(objects) or 1
    coverage = {f: round(sum(_has(o, f) for o in objects) / total, 3) for f in _FIELDS}
    category_dist = dict(Counter(o.get("category", "?") for o in objects))
    anomalies = {
        "missing_image": [o["qid"] for o in objects if not o.get("image")][:20],
        "missing_zh_label": [o["qid"] for o in objects if not o.get("title_zh")][:20],
    }
    rep = {
        "slug": slug,
        "total": len(objects),
        "coverage": coverage,
        "category_dist": category_dist,
        "anomalies": anomalies,
    }
    if not as_markdown:
        return rep
    lines = [f"# 抽样报告: {slug}", "", f"- 对象数: {rep['total']}", "", "## 覆盖率"]
    lines += [f"- {f}: {coverage[f]*100:.0f}%" for f in _FIELDS]
    lines += ["", "## 类型分布"] + [f"- {k}: {v}" for k, v in category_dist.items()]
    lines += [
        "",
        "## 异常",
        f"- 缺主图: {len(anomalies['missing_image'])} 条 {anomalies['missing_image']}",
        f"- 缺中文标签: {len(anomalies['missing_zh_label'])} 条",
    ]
    return "\n".join(lines)
