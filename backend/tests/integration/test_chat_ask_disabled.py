"""未接地的自由问答已停用(2026-07-27)。

它只喂一段 context 字符串、不查馆藏内容、不带证据包 → 会脑补,违反项目最核心的
AI 原则(接地、可溯源、宁缺毋滥)。讲解侧建了整套接地闸,问答侧不能双标——
尤其付费墙将建在音频/问答上,脑补=差评+退款。
接地版见 backlog;已生成的 743 条接地预设问答走 content 端点,不受影响。
"""

from app.api.v1.endpoints import chat


def test_ask_endpoint_is_disabled():
    import asyncio

    import pytest
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        asyncio.run(
            chat.ask_question(
                chat.ChatRequest(question="谁画的?", context="随便"), ai_service=None
            )
        )
    assert e.value.status_code == 503
    assert "ungrounded" in str(e.value.detail)
