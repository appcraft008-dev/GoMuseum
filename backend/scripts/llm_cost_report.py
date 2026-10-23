"""LLM 成本报告(成本工程①):llm_usage 表按 channel×model 聚合 + 粗估 $。
用法(容器内): python scripts/llm_cost_report.py [--days 30]"""

import sys

sys.path.insert(0, ".")


def report(db, days: int) -> str:
    from datetime import date, timedelta

    from sqlalchemy import func

    from app.models.llm_usage import LLMUsage
    from app.services.llm_usage import cost_usd

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
        f"{'channel':14} {'model':18} {'calls':>8} {'in':>12} {'out':>10} {'~$':>8}"
    )
    total = 0.0
    for ch, model, calls, tin, tout in sorted(rows, key=lambda r: r[0]):
        tin, tout = int(tin or 0), int(tout or 0)  # PG SUM 返回 Decimal,统一成 int
        usd, known = cost_usd(model, tin, tout)
        total += usd
        lines.append(
            f"{ch:14} {model:18} {calls or 0:>8} {tin:>12} {tout:>10} {usd:>8.2f}"
            + ("" if known else " ?")
        )
    lines.append(
        f"{'合计':>54} ~${total:.2f}(粗估,价目见 llm_usage.DEFAULT_LLM_PRICES + .env LLM_PRICES;? = 不在价目里,按最贵价计)"
    )
    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    from app.core.database import SessionLocal

    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=30)
    ns = ap.parse_args()
    print(report(SessionLocal(), ns.days))
