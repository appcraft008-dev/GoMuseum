"""staging 轻量化护栏(spec 2026-07-17):staging 永不为数据规模付 LLM 费。
机制验证=小样本;规模数据用 sync_staging_from_prod.py 从 prod 搬运,别重算。"""

STAGING_SAMPLE_LIMIT = 50
_HINT = "(全量请 --allow-full;规模数据用 sync_staging_from_prod.py 搬运,别重算)"


def staging_limit(target, limit, allow_full):
    """带 LLM 的批命令:staging 默认收紧到小样本;prod/显式 allow_full 原样返回。"""
    if target != "staging" or allow_full:
        return limit
    if limit is None or limit > STAGING_SAMPLE_LIMIT:
        print(f"⚠️ staging 护栏:limit → {STAGING_SAMPLE_LIMIT} {_HINT}")
        return STAGING_SAMPLE_LIMIT
    return limit


def staging_require_allow_full(target, allow_full):
    """无 limit 概念的全库 LLM 脚本(rescan 系):staging 必须显式确认。"""
    if target == "staging" and not allow_full:
        raise SystemExit(f"❌ staging 护栏:全库 LLM 操作需显式 --allow-full {_HINT}")
