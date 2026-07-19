"""LLM 成本报告(成本工程①):llm_usage 表按 channel×model 聚合 + 粗估 $。
用法(容器内): python scripts/llm_cost_report.py [--days 30]"""

import sys

sys.path.insert(0, ".")

# 粗估单价($/1M tokens;tts=$/1M 字符)。价目会变,改这里即可——报告以 tokens 为准,$ 仅参考。
PRICES = {
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "tts-1": (15.0, 0.0),  # $15/1M chars
}


def report(db, days: int) -> str:
    from datetime import date, timedelta

    from sqlalchemy import func

    from app.models.llm_usage import LLMUsage

    since = date.today() - timedelta(days=days)
    rows = (
        db.query(
            LLMUsage.channel,
            LLMUsage.model,
            func.sum(LLMUsage.calls),
            func.sum(LLMUsage.tokens_in),
            func.sum(LLMUsage.tokens_out),
        )
        .filter(LLMUsage.day >= since)
        .group_by(LLMUsage.channel, LLMUsage.model)
        .all()
    )
    lines = [f"LLM 用量 最近{days}天(截至 {date.today()})"]
    lines.append(
        f"{'channel':10} {'model':18} {'calls':>8} {'in':>12} {'out':>10} {'~$':>8}"
    )
    total = 0.0
    for ch, model, calls, tin, tout in sorted(rows, key=lambda r: r[0]):
        tin, tout = int(tin or 0), int(tout or 0)  # PG SUM 返回 Decimal,统一成 int
        pin, pout = PRICES.get(model, (0.0, 0.0))
        usd = tin / 1e6 * pin + tout / 1e6 * pout
        total += usd
        lines.append(
            f"{ch:10} {model:18} {calls or 0:>8} {tin:>12} {tout:>10} {usd:>8.2f}"
        )
    lines.append(f"{'合计':>50} ~${total:.2f}(粗估,价目见 PRICES)")
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ns = ap.parse_args()
    print(report(SessionLocal(), ns.days))
