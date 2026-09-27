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
import re

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
    if _QUOTED.search(text):  # 绝大多数描述没有转写,不查作者、不调模型
        text = strip_signatures(text, _artist_names(db, obj))
    from sqlalchemy.orm.attributes import flag_modified

    obj.attributes = {**attrs, KEY: text, VIA_KEY: f"{MODEL}/{DETAIL}"}
    flag_modified(obj, "attributes")
    db.flush()
    return True


# ---- 签名过滤(看图之后,纯文本) ----------------------------------------------
# 看图 prompt 里已经写了「不许转写签名」,但模型认不出**不像签名的签名**:
#   齐马《圣母子》画中字条上的「IOANNES B」(= Ioannes Baptista,作者本名拉丁化)
#   被当成「inscription」转写,下游 guide 写成「铭文暗示了艺术家的身份」。
# 在 prompt 里加细则反而更糟(2026-09-27 A/B,各 2 次):新写法点名了
# 「名字+年份」,库尔贝自画像从 0/2 → 2/2 转写出「Gustave Courbet 1842」,
# 齐马照旧 2/2 —— **禁令里点名的东西就是种子**(同 guide 的教训)。
# 所以不再指望看图模型自我克制,而是看完之后单独判:这条转写是不是这位作者的签名。
# 这一步**可以**给作者名(看图那步不许给,见下方 _SYSTEM 注释),因为它只做分类、
# 不产出描述。prod 全部 6 条带转写的描述实测:签名 2/2 判中,ECCE AGNUS DEI /
# GLORIA / 梅尔松铭文 3/3 保留;单独的年份(克莱兰「1876」)模型判不是 → 用代码判。
_QUOTED = re.compile(r'"([^"]+)"|“([^”]+)”')
_YEAR_ONLY = re.compile(r"^\W*\d{4}\W*$")
# 引号里的句号(「…"GLORIA." The setting…」)后面也要断开,否则删签名句会连带删下一句
_SENTENCE = re.compile(r"(?<=[.!?])\s+|(?<=[.!?][\"”])\s+")
_SIGNATURE_SYSTEM = (
    "You check text transcribed from a photograph of an artwork. For each quoted text, "
    "answer whether it is (part of) the ARTIST'S SIGNATURE or signing date — i.e. the "
    "artist's own name in any language, Latinized, abbreviated or partial form, "
    "optionally with a year or words like pinxit/fecit/f./opus. Text that names "
    "someone else, or is a title, motto, dedication, scripture or label, is NOT a "
    'signature. Reply JSON {"signature":[true|false,...]} in the same order.'
)


def _artist_names(db, obj) -> list[str]:
    from app.models.artist import Artist

    names = {obj.artist_en}
    aq = (obj.attributes or {}).get("artist_qid")
    art = db.query(Artist).filter_by(qid=aq).one_or_none() if aq else None
    if art:
        names |= set((art.name_i18n or {}).values()) | {art.name_en}
    return sorted(n for n in names if n and re.search(r"[A-Za-z]", n))


def _classify_signatures(names: list[str], quoted: list[str]) -> list[bool]:
    import asyncio
    import json

    from app.services.content_generation_service import _get_openai_client

    client = _get_openai_client()
    if client is None:
        raise RuntimeError("OpenAI client 不可用")

    async def _run():
        return await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _SIGNATURE_SYSTEM},
                {
                    "role": "user",
                    "content": json.dumps(
                        {"artist": names, "quoted_texts": quoted}, ensure_ascii=False
                    ),
                },
            ],
        )

    resp = asyncio.run(_run())
    from app.services.llm_usage import record_llm_usage

    usage = getattr(resp, "usage", None)
    record_llm_usage(
        "vision",
        "gpt-4o-mini",
        getattr(usage, "prompt_tokens", 0),
        getattr(usage, "completion_tokens", 0),
    )
    flags = json.loads(resp.choices[0].message.content).get("signature") or []
    return [bool(f) for f in flags]


def strip_signatures(text: str, names: list[str], classify=None) -> str:
    """删掉描述里转写了作者签名/落款年份的**整句**。没有引号转写就原样返回(不调模型)。

    判不出来(调用失败/返回条数不对)→ 原样返回:签名漏网是老行为,
    而因为这一步失败把整段视觉描述丢掉,那一件就回到脑补状态,更糟。
    """
    # 引号内部不断句:签名常带首字母缩写(「h. Daumier」「G. Courbet」),
    # 在那个点上切开会让引号两半各落一句,一条转写都认不出来,签名原样漏过
    spans = [m.span() for m in _QUOTED.finditer(text)]
    cuts = [
        m
        for m in _SENTENCE.finditer(text)
        if not any(a < m.start() < b for a, b in spans)
    ]
    starts = [0] + [m.end() for m in cuts]
    ends = [m.start() for m in cuts] + [len(text)]
    sentences = [text[a:b] for a, b in zip(starts, ends)]
    quoted = [
        (i, a or b) for i, s in enumerate(sentences) for a, b in _QUOTED.findall(s)
    ]
    if not quoted:
        return text
    drop = {i for i, q in quoted if _YEAR_ONLY.match(q)}
    rest = [(i, q) for i, q in quoted if i not in drop]
    if rest and names:
        try:
            flags = (classify or _classify_signatures)(names, [q for _, q in rest])
        except Exception:
            logger.exception("signature check failed; keeping description as is")
            flags = []
        if len(flags) == len(rest):
            drop |= {i for (i, _), f in zip(rest, flags) if f}
    return " ".join(s for i, s in enumerate(sentences) if i not in drop)


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
    # ⚠️ 「读不清就说读不清」必须长在转写这一句上,不能只留在末尾当通则(那条还在,
    # 见下面的 "If something is unclear")。2026-09-13 实测(Q104444757 梅尔松草图,
    # 四条铭文):末尾通则版把 4 条里的 3 条编了出来 —— LES SOCIÉTÉS DE TIR /
    # DE NATATION / EXERCICES PHYSIQUES,真实是 LA DISTRIBUTION DES PRIX /
    # LES EXCURSIONNISTES / LES BAINS DE MER。编出来的全是「体育协会」这类
    # 合情合理的词,下游当硬事实用,最难发现。
    # 同图 A/B(各 2 次):旧 3 条/3 条 → 新 1 条/0 条,并主动写出 partially legible。
    # 这是 #555「禁令要长在它约束的那一拍上」的第二例。
    #
    # ⚠️ **签名与日期明确排除在外**(2026-09-14 实测逼出来的;契约纪律 34)。
    # 上面那条「读不清就说读不清」对铭文有效,对签名**无效** —— 模型自认读清了:
    #   Daumier《下棋者》签的是「h. Daumier」,读成「L. Beaumier」;
    #   Sérusier《织粉袜的少女》签名下是两位数,模型扩写成「1890.」,
    #   而编目年代是 1920 —— 它把推断当成了转写。
    # 关键在于:签名唯一能提供的就是**作者和年代**,而这两样编目里已经有了
    # (Wikidata/Joconde,比从图上读可靠得多)。读对了是冗余,读错了是往材料里
    # 注入假事实,还带着「画上亲笔签着」这种极具说服力的口吻。**净损失,去掉。**
    "Transcribe VERBATIM, in quotes, any text that is part of the artwork itself "
    "(an inscription, a banner, a book, a scroll). Transcribe ONLY letters you "
    "can actually read; where lettering is small, faded, reversed or otherwise not "
    "clearly legible, write that an inscription is present but illegible INSTEAD OF "
    "reconstructing what it probably says. "
    "Do NOT transcribe or mention the artist's signature or the date they signed — "
    "the catalogue already records who made this and when, and a misread signature "
    "would contradict it. "
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
