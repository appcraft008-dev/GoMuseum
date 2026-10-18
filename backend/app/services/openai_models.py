"""LLM 模型名走配置,按模型名前缀分发到 OpenAI / Anthropic(4o 系 2027-01-14 退役)。

代码里仍写档位名 gpt-4o-mini / gpt-4o / VISION,发请求前 resolve 成真实模型:
先看 LLM_CHANNEL_MODELS 里这条用量通路(generate/gate/qa/label…)有没有单独指定,
再落到档位(OPENAI_FAST/STRONG/VISION_MODEL)。按环境、按通路单独切换,出问题改 env 回切。
10-18 staging/prod 对照选型:看图 Claude Sonnet 5.5;写讲解/闸/问答/墙签 Claude Haiku 5.5;
翻译/判官/重译/识别兜底 gpt-6-luna。
"""

from app.core.config import settings

VISION = "vision"


def resolve(model: str, channel: str | None = None) -> str:
    if channel and channel in settings.LLM_CHANNEL_MODELS:
        return settings.LLM_CHANNEL_MODELS[channel]
    return {
        "gpt-4o-mini": settings.OPENAI_FAST_MODEL,
        "gpt-4o": settings.OPENAI_STRONG_MODEL,
        VISION: settings.OPENAI_VISION_MODEL,
    }.get(model, model)


def create_kwargs(model: str, channel: str | None = None, **kw) -> dict:
    """chat.completions.create 的参数。GPT-6 和 4o 有三处不同(10-18 staging 实测 400):
    拒收 max_tokens;temperature≠1 只在 reasoning_effort=none 时允许(闸靠 temperature=0);
    Sol 不支持 none,只能 low 并去掉 temperature。"""
    kw["model"] = real = resolve(model, channel)
    if real.startswith("gpt-6"):
        if "max_tokens" in kw:
            kw["max_completion_tokens"] = kw.pop("max_tokens")
        # ponytail: 按型号名判断是否支持 none,上新型号再补
        kw["reasoning_effort"] = "none" if "luna" in real else "low"
        if kw["reasoning_effort"] != "none":
            kw.pop("temperature", None)
    return kw


def chat(model: str, messages: list, channel: str | None = None, **kw):
    """一次对话调用(OpenAI chat 形状的 messages)。返回 (text, 真实模型, tokens_in, tokens_out)。"""
    real = resolve(model, channel)
    if real.startswith("claude"):
        return _claude(real, messages, **kw)

    import asyncio

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client 不可用")
    args = create_kwargs(model, channel, messages=messages, **kw)

    async def _run():
        return await client.chat.completions.create(**args)

    resp = asyncio.run(_run())
    u = getattr(resp, "usage", None)
    return (
        resp.choices[0].message.content or "",
        real,
        getattr(u, "prompt_tokens", 0),
        getattr(u, "completion_tokens", 0),
    )


_client = None


def _anthropic_client():
    global _client
    if _client is None:
        import anthropic

        # 同步客户端:调用方都在普通线程里;线程安全,可共用
        _client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    return _client


def _blocks(content):
    if isinstance(content, str):
        return content
    out = []
    for p in content:
        if p["type"] == "text":
            out.append({"type": "text", "text": p["text"]})
        elif p["type"] == "image_url":
            url = p["image_url"]["url"]
            if url.startswith("data:"):
                media, data = url[5:].split(";base64,", 1)
                src = {"type": "base64", "media_type": media, "data": data}
            else:
                src = {"type": "url", "url": url}
            out.append({"type": "image", "source": src})
    return out


def _claude(model: str, messages: list, **kw):
    """OpenAI 参数 → Anthropic Messages。Claude 5 系拒收 temperature(400),所以丢掉;
    关思考:Haiku 写 disabled,Sonnet 只认 between_tools(10-18 实测);返回里夹着
    thinking 块,只取 text。"""
    system = "\n\n".join(m["content"] for m in messages if m["role"] == "system")
    if (kw.get("response_format") or {}).get("type") == "json_object":
        system += "\n\nReturn ONLY a JSON object."
    args = {
        "model": model,
        "max_tokens": kw.get("max_tokens") or 4096,
        "messages": [
            {"role": m["role"], "content": _blocks(m["content"])}
            for m in messages
            if m["role"] != "system"
        ],
        "thinking": {"type": "disabled" if "haiku" in model else "between_tools"},
    }
    if system:
        args["system"] = system
    if kw.get("timeout"):
        args["timeout"] = kw["timeout"]
    r = _anthropic_client().messages.create(**args)
    text = "".join(b.text for b in r.content if b.type == "text")
    return text, model, r.usage.input_tokens, r.usage.output_tokens
