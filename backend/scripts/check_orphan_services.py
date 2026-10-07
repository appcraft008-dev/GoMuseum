"""零调用方检测(不变量 I16)。

**本项目最常见的缺陷不是设计错,是"写完了没接上"** —— 已经踩过四次:
`log_event`、`/entitlements/activate`、`revoke_for_purchase`、真实收据校验,
全都建好了、从没有人调。这类问题在代码评审和设计文档里都看不见,只能机械检测。

用法:
  python scripts/check_orphan_services.py            # 列出零调用方
  python scripts/check_orphan_services.py --strict   # 有孤儿则退出码 1(CI 用)

允许清单:确实只作为对外 API/入口存在的函数写进 ALLOW,并注明理由。
"""

import argparse
import ast
import pathlib
import re
import sys

SCAN_DIRS = ("app/services",)
USE_DIRS = ("app", "scripts", "tests")

# 有意的"无内部调用方":理由必须写清楚,否则不许进这张表
ALLOW = {
    "add_referral_bonus": "推荐奖励功能待接入 UI;保留服务能力",
    "fetch_museum_building_photo": "上新馆 CLI 按需调用(动态派发)",
    "run_lazy_images": "运维脚本入口",
    "to_simplified": "繁简转换工具,按需使用",
}

# 已知死代码:整模块无人引用。**不删**(非本次改动造成,按项目规矩只报不删),
# 但登记在此,避免每次检测都当成新问题。要清理时单独提 PR。
KNOWN_DEAD = {
    "get_content_cache": "app/services/content_cache.py 整模块零引用(约 157 行)",
}


def _public_defs() -> dict[str, str]:
    out: dict[str, str] = {}
    for d in SCAN_DIRS:
        for p in pathlib.Path(d).rglob("*.py"):
            try:
                tree = ast.parse(p.read_text())
            except SyntaxError:
                continue
            for n in ast.walk(tree):
                if isinstance(
                    n, (ast.FunctionDef, ast.AsyncFunctionDef)
                ) and not n.name.startswith("_"):
                    out.setdefault(n.name, str(p))
    return out


def _corpus() -> str:
    """全仓文本。**必须排除本文件** —— 否则 ALLOW/KNOWN_DEAD 里的函数名
    作为字符串出现,会被当成"有人引用",检测器自己把自己骗过去(实测踩到)。"""
    me = pathlib.Path(__file__).resolve()
    parts = []
    for d in USE_DIRS:
        for p in pathlib.Path(d).rglob("*.py"):
            if p.resolve() == me:
                continue
            parts.append(p.read_text())
    return "\n".join(parts)


def find_orphans() -> list[tuple[str, str]]:
    defs = _public_defs()
    corpus = _corpus()
    orphans = []
    for name, path in defs.items():
        # 定义处会出现 `def name`;其余任何出现都算被引用 ——
        # 必须算**裸引用**而不只是 `name(`:Depends(get_tts_service) 这类
        # 只传函数不调用的写法同样是"接上了"。
        total = len(re.findall(r"\b" + re.escape(name) + r"\b", corpus))
        as_def = len(re.findall(r"def\s+" + re.escape(name) + r"\b", corpus))
        if total - as_def == 0:
            orphans.append((name, path))
    return sorted(orphans)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ns = ap.parse_args()

    orphans = find_orphans()
    unexpected = [(n, p) for n, p in orphans if n not in ALLOW and n not in KNOWN_DEAD]

    print(f"零调用方 {len(orphans)} 个(其中 {len(unexpected)} 个未在允许清单):")
    for n, p in orphans:
        note = ALLOW.get(n)
        dead = KNOWN_DEAD.get(n)
        mark = "  " if note else ("💀" if dead else "⚠️")
        tail = note or dead or ""
        print(f"{mark} {n:38s} {p}" + (f"  — {tail}" if tail else ""))

    if unexpected:
        print(
            "\n未接线的服务层函数 = 功能没做完。要么接上," "要么写进 ALLOW 并注明理由。"
        )
    if ns.strict and unexpected:
        sys.exit(1)


if __name__ == "__main__":
    main()
