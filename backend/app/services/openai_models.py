"""OpenAI 模型名走配置(4o 系 2027-01-14 退役,迁 GPT-6)。

代码里仍写档位名 gpt-4o-mini / gpt-4o / VISION,发请求前 resolve 成 settings 里的真实模型,
按环境、按档位单独切换,出问题改 env 回切。选型依据见 docs(10-18 staging 对照):
Luna 做生成/闸/翻译/识别/墙签不差于现状;看图描述 Luna 错得多,用 Sol。
"""

from app.core.config import settings

VISION = "vision"


def resolve(model: str) -> str:
    return {
        "gpt-4o-mini": settings.OPENAI_FAST_MODEL,
        "gpt-4o": settings.OPENAI_STRONG_MODEL,
        VISION: settings.OPENAI_VISION_MODEL,
    }.get(model, model)


def create_kwargs(model: str, **kw) -> dict:
    """chat.completions.create 的参数。GPT-6 和 4o 有三处不同(10-18 staging 实测 400):
    拒收 max_tokens;temperature≠1 只在 reasoning_effort=none 时允许(闸靠 temperature=0);
    Sol 不支持 none,只能 low 并去掉 temperature。"""
    kw["model"] = real = resolve(model)
    if real.startswith("gpt-6"):
        if "max_tokens" in kw:
            kw["max_completion_tokens"] = kw.pop("max_tokens")
        # ponytail: 按型号名判断是否支持 none,上新型号再补
        kw["reasoning_effort"] = "none" if "luna" in real else "low"
        if kw["reasoning_effort"] != "none":
            kw.pop("temperature", None)
    return kw
