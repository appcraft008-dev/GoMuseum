"""看藏品照片写外观描述,作为生成讲解的**视觉材料**。

## 为什么需要这一层

2026-09-13 实证:材料里没有任何视觉信息时,模型会凭训练记忆(或凭空)
编出外观描写,而**接地闸抓不到** —— 它把「muted background」「earthy palette」
这类句子归成 IMPRESSION 放行(闸的规则见 prompts._ENTAILMENT_SYSTEM)。

库尔贝《驴》实例:材料只有标题/尺寸/材质,生成出「耳朵竖起、眼睛闪着好奇」
(原画是低头吃食、耳朵垂着)。《萨拉·伯恩哈特像》更典型:编出「粉色沙发」
(实为红色)、「紫天鹅绒威尼斯镜」(无),而**漏掉了画面里的狗、折扇、金靠枕**。

把照片描述喂进材料 → 这些句子要么有据可依,要么被闸正确删掉。

## 选型实证(2026-09-13,三张图对照)

- **gpt-4o-mini 不能用**:把库尔贝的驴认成马,而且图像 token 是 4o 的 **29 倍**
  (36988 vs 1258) —— 又贵又错。
- **detail="low" 不能用**:省 80% token,但把签名年份 1876 读成 1878。
  凡图上有文字(签名/年份/铭牌)就会编。
- **gpt-4o + detail="high"**:《萨拉·伯恩哈特像》10 项全对零编造
  (红沙发/白裙毛边/折扇/金靠枕/长毛猎犬/左侧绿植/暗背景/签名 1876…)。
  单张约 $0.004。

⚠️ 与 `app/services/recognition/vision.py` **不是重复**:那个吃用户现拍的
base64、任务是**认出这是哪件**(候选名 + 墙签 OCR),用 mini 足够且要快;
这个吃馆藏图 URL、任务是**描述它长什么样**,要准不要快。两者 prompt 目标相反
(那边要它猜名字,这边明确禁止猜名字)。
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

MODEL = "gpt-4o"
DETAIL = "high"

# 描述写进哪个键。前缀 `visual_description_` 会被 build_material 收进
# [VISIBLE IN THE ARTWORK] 块 —— 所以来源标记**不能**用同前缀,否则
# 「gpt-4o/high」会被当成材料喂给模型(tests 里有用例钉住,且键名从这里取)。
KEY = "visual_description_en"
VIA_KEY = "visual_via"


def primary_image_url(db, obj) -> str | None:
    """取这件的主图公网 URL(large 档)。没有本地图返回 None。

    按 sort 取第一张而不是挑 role=='primary':实测存量有 role 为 view 的
    单图件,挑 primary 会把它们整批判成"无图"。
    """
    from app.models.museum_object import ObjectImage
    from app.services.storage import get_object_storage

    img = (
        db.query(ObjectImage)
        .filter(ObjectImage.object_id == obj.id, ObjectImage.image_key.isnot(None))
        .order_by(ObjectImage.sort.asc().nullslast())
        .first()
    )
    if not img:
        return None
    return get_object_storage().public_url(f"{img.image_key}_large.jpg")


def ensure_description(db, obj) -> bool:
    """这件还没有外观描述且有图 → 看一次图并落库。返回是否新写了描述。

    **一次性**:描述落库后永久复用,重生成(--force)不会再看第二次图。
    所以按件计的 $0.0044 只付一次,而正文会被重生成很多次。

    ⚠️ 失败**不阻断生成**:视觉调用挂了就退回"没有视觉材料"的老行为,
    用户照样能看到讲解。不写任何标记 —— 键仍然缺失,所以下次批跑/重生成
    会自然重试,不会静默永久跳过。代价是这一版正文的外观描写可能是编的,
    这比让用户对着空白页强。ERROR 级日志可 grep:VISION_FAILED。
    """
    attrs = obj.attributes or {}
    if attrs.get(KEY):
        return False
    url = primary_image_url(db, obj)
    if not url:
        return False
    try:
        text = describe_image(url)
    except Exception:
        logger.exception("VISION_FAILED qid=%s url=%s", obj.qid, url)
        return False
    from sqlalchemy.orm.attributes import flag_modified

    obj.attributes = {**attrs, KEY: text, VIA_KEY: f"{MODEL}/{DETAIL}"}
    flag_modified(obj, "attributes")
    db.flush()
    return True


# ⚠️ 这段 prompt 里**不出现作品标题、作者、年代** —— 调用方也不许传。
# 理由:模型拿到标题就能顺着标题编("Danaé" → 金雨/宙斯/神话解读),
# 那样产出的就不是观察而是联想,和我们要修的病一模一样。
# 不给标题 = 它只能描述真正看到的东西。见 tests 里钉这一条的用例。
_SYSTEM = (
    "You describe a museum artwork from its photograph, to be used as SOURCE MATERIAL "
    "for writing a guide. Describe ONLY what is visibly present in the artwork itself. "
    "Cover: what is depicted (subject, pose, setting), the palette, the handling of the "
    "medium (brushwork, surface, carving) if visible, and the composition. "
    # ① 作品**上**的文字要逐字转写。实测漏它会连带看错东西:《Credo》主体举着
    # 一条写着 CREDO 的横幅,不转写文字时被读成「一把大弯刀,双手横持」。
    # 注意与下一条不冲突:转写的是画/雕塑本身的铭文,不是墙签。
    "Transcribe VERBATIM, in quotes, any text that is part of the artwork itself "
    "(an inscription, a banner, a book, a signature). "
    # ② 中景/远景要交代。实测只写显眼元素会漏掉主体:河景里停泊的一排驳船
    # 在中景,第一版描述只写了树和房子,船一条没提 —— 而船正是这幅画的主题。
    "Account for the foreground, the middle distance and the background separately; "
    "include small or distant figures, animals, boats and buildings, not only the "
    "dominant elements. "
    "Do NOT identify people, places or events by name unless a name is legibly written "
    "in the image. "
    "Do NOT interpret meaning, symbolism, mood, quality or art-historical significance. "
    "Do NOT describe the frame, mount, wall, label or plaque. "
    "If something is unclear, say it is unclear rather than guessing what it is. "
    "Write 80-140 words of plain prose, no preamble."
)


def build_vision_messages(image_url: str, detail: str = DETAIL) -> list:
    """构造视觉调用的 messages。抽出来是为了让单测能断言"没夹带元数据"。"""
    return [
        {"role": "system", "content": _SYSTEM},
        {
            "role": "user",
            "content": [
                {
                    "type": "image_url",
                    "image_url": {"url": image_url, "detail": detail},
                }
            ],
        },
    ]


def describe_image(
    image_url: str,
    *,
    model: str = MODEL,
    detail: str = DETAIL,
    channel: str = "vision",
    attempts: int = 3,
) -> str:
    """看图出描述。失败抛异常 —— **不要**吞掉换成空串。

    空描述和"这张图没什么可说的"在下游长得一模一样,而真实后果是
    那一件又回到脑补状态。宁可整批停下来。

    attempts:OpenAI 侧取图偶发超时(实测 `invalid_image_url:
    Unable to download content ... before the timeout`),CDN 抖动而已,重试即可。
    """
    import asyncio

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client 不可用")

    async def _run():
        resp = await client.chat.completions.create(
            model=model,
            messages=build_vision_messages(image_url, detail),
            temperature=0,
        )
        return resp.choices[0].message.content, getattr(resp, "usage", None)

    last = None
    for i in range(attempts):
        try:
            text, usage = asyncio.run(_run())
            break
        except Exception as e:  # noqa: BLE001 — 重试后仍失败会原样抛出
            last = e
            if "invalid_image_url" not in str(e) or i == attempts - 1:
                raise
            logger.warning("vision 取图失败,重试 %s/%s: %s", i + 1, attempts, e)
    else:  # pragma: no cover - 循环必然 break 或 raise
        raise last

    from app.services.llm_usage import record_llm_usage

    record_llm_usage(
        channel,
        model,
        getattr(usage, "prompt_tokens", 0),
        getattr(usage, "completion_tokens", 0),
    )
    text = (text or "").strip()
    if not text:
        raise RuntimeError(f"视觉描述为空: {image_url}")
    return text
