"""质量闸 QualityGate：逐句蕴含校验删不支持句 + 叙事/硬事实对账 + 质量分 → status。
LLM 判定经注入式 complete，单测离线。spec §8A-1/§8A-2。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.services.enrichment.prompts import build_entailment_prompt

# 存活率阈值：三类闸下 keep 含引导句/解读句（仅无据事实主张被删），
# 低存活率意味着大量事实性主张无材料支持（料薄/脑补），需人工复审。
GROUNDING_THRESHOLD = 0.6

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# 缩写里的点不是句末。切错了会把半截短语单独送去过闸,而碎片("1, is a painting…")
# 多半判无据被删 → 正文被截断。prod 实测损害 2 条(Q687182《惠斯勒的母亲》的
# significance,en/es):「Arrangement in Grey and Black No.」后面的编号整个没了。
# 绝大多数切点无害(两半都过闸,再用空格拼回去与原文逐字相同),所以这是低频缺陷,
# 但修它是一行的事。宁可少切一刀:误合只是让判定单元长一点,误切会吃掉内容。
_ABBR = (
    r"(?:No|Nos|St|Ste|Mr|Mrs|Ms|Dr|Prof|Jr|Sr|vs|ca|cf|approx"
    r"|Inv|Ave|Mt|Fig|vol|op|ed|c)"
)
_ENDS_ABBR = re.compile(r"(?:^|\s)" + _ABBR + r"\.$")


def _split_sentences(text: str | None) -> list[str]:
    """把正文切成句子列表（按 . ! ? 后接空白）。空/None → []。

    在已知缩写（Dr. / St. / No. …）之后不断句——`re` 的后顾断言要求定长，
    没法写进正则，所以切完再把跟在缩写后面的那截拼回去。
    """
    if not text or not text.strip():
        return []
    out: list[str] = []
    for part in _SENTENCE_SPLIT.split(text.strip()):
        part = part.strip()
        if not part:
            continue
        if out and _ENDS_ABBR.search(out[-1]):
            out[-1] = f"{out[-1]} {part}"
        else:
            out.append(part)
    return out


def _split_paragraphs(text: str | None) -> list[str]:
    """按空行(\\n\\n+)切段;无空行则整体一段。空/None → []。"""
    if not text or not text.strip():
        return []
    return [p.strip() for p in re.split(r"\n\s*\n", text.strip()) if p.strip()]


# 段落在 App 里是**独立展示**的(标题/作者在段外),所以正文第一句里的指人代词
# 一定没有先行词。接地闸逐句删,删掉开头那句之后剩下的就这样发出去了:
#   「His profile reveals a thoughtful demeanor…」   —— His 是谁?
#   「Their flowing garments and tender expressions…」—— Their 指谁?
#   「Sentier de la Mi-côte' is that it was painted on-site.」—— 引号腰斩,语法不通。
# 这是 #555 去套话的副作用:以前开头是「Take a moment to really look…」,
# **套话不陈述事实所以永远过闸**、首句删不掉;换成实质句后,过不了闸就被删。
#
# ⚠️ 判据只看**剩余首句长什么样**,不看「首句是不是被删了」(契约纪律 32)——
# 2026-09-13 (#557) 上线的就是后者,prod 47 件重跑实测:
#   首句被删 → 拦 23 段,其中 **17 段完全自洽**(「The artist's brushwork is
#   meticulous…」这类技法描述段根本不需要总起),真断裂只有 6 段。
#   换成这里的词表:拦 3 段真断裂,误杀 0 段。
# 漏掉的断法(代词在句中、This+抽象名词)是已知代价,比误杀 17 段好内容划算。
# 🔑 教训:我当时拿「剩余首句看着悬空」的统计(3 段)去论证「首句被删」这个
# 判据(23 段),两者差一个数量级 —— **代理指标测的不是你要实施的那件事**。
#
# ⚠️ 别把 It/Its/This 加进来:「It was commissioned for the coronation…」
# 「Its significance lies in…」指的是**作品本身**,段落就展示在作品页上,
# 指代成立 —— prod 全库 46 段是这种,加进来就是又一轮误杀。
# ⚠️ 已知漏掉的两种(**故意不补**):This + 抽象名词(「This choice allowed
# Courbet…」)、句中引号被切开(「Sentier de la Mi-côte' is that…」)。
# 每补一种都要加分支,而每个分支都带着误杀好开头的风险 ——
# 上一版正是因为想「一网打尽」才误杀了 17 段。
_ORPHANED_OPENING = re.compile(
    r"^(?:He|His|Him|She|Her|Hers|They|Them|Their)\b"  # 指人的代词,无先行词
    r"|^[a-z]"  # 小写开头 = 句子被腰斩
)

# 「代词在句中」原先也在故意不补之列,2026-09-27 小皇宫 TOP21-30 用户读出两篇 guide:
#   曼特尼亚「To his left, another child…」(首句,代词不在句首)
#   博纳尔《沃拉尔与猫》「The warm browns … of the room … To his left, …」(第二句;
#   引出沃拉尔的首句被闸删了,全文再没出现过沃拉尔)
# 判据:**第一个带性别的单数代词之前**,既没出现专名,也没出现指人/动物的名词 → 悬空。
# 只看 he/his/him/she/her/hers:they/their 常指物(「tall trees … their foliage」),
# 带进来就是误杀。宁可放过(句首的非虚词大写词一律当专名),不可误杀。
# 实测:prod 全部已发布英文段 2829 段命中 48 段,逐条读过**全是真悬空**
# (「He painted each of the four figures…」「This work showcases his…」),误杀 0;
# 已知漏网:代词前刚出现过别的专名(热尔韦「…of Venus … His brushwork」)。
_GENDERED_PRONOUN = re.compile(r"\b(?:he|his|him|she|her|hers)\b", re.I)
_ANTECEDENT_NOUN = re.compile(
    r"\b(?:man|men|woman|women|girl|boy|child|children|infant|baby|mother|father|"
    r"son|daughter|sister|brother|wife|husband|figure|sitter|subject|artist|"
    r"painter|sculptor|model|lady|gentleman|king|queen|saint|goddess|god|youth|"
    r"soldier|rider|horseman|horsemen|knight|shepherd|peasant|dancer|bather|nude|"
    r"person|people|couple|cat|dog|horse|lion|bird)s?\b",
    re.I,
)
# 句首大写词若是虚词就不算专名;不在表里的句首大写词一律当专名(偏向放行)
_SENTENCE_FUNCTION_WORDS = {
    "The", "A", "An", "This", "These", "That", "Those", "In", "On", "At", "To",
    "With", "By", "From", "For", "As", "Its", "It", "Of", "And", "But", "While",
    "Beneath", "Behind", "Above", "Below", "Around", "Against", "Here", "There",
}  # fmt: skip
_CAPITALIZED = re.compile(r"(?:^|(?<=[\s(\"'“‘]))([A-Z][\w’'-]*)")


def _pronoun_lacks_antecedent(body: str) -> bool:
    m = _GENDERED_PRONOUN.search(body)
    if not m:
        return False
    before = body[: m.start()]
    if _ANTECEDENT_NOUN.search(before):
        return False
    for cm in _CAPITALIZED.finditer(before):
        prev = before[: cm.start()].rstrip()
        at_sentence_start = not prev or prev[-1] in ".!?\n"
        if not at_sentence_start or cm.group(1) not in _SENTENCE_FUNCTION_WORDS:
            return False  # 出现过专名 → 可能就是先行词,放行
    return True


def _opening_is_orphaned(body: str | None) -> bool:
    """正文是不是悬空的(开头语法残缺,或指人代词找不到先行词)。"""
    if not body:
        return False
    body = body.strip()
    return bool(_ORPHANED_OPENING.match(body)) or _pronoun_lacks_antecedent(body)


@dataclass
class SectionQuality:
    body: str | None
    status: str
    grounding_ratio: float
    conflicts: list[str] = field(default_factory=list)
    score: float = 0.0
    # 因正文悬空而挂起(而非存活率不够):guide 据此重写一次,见 pipeline
    orphaned: bool = False


def _parse():
    # 复用 Phase 2a 的容错解析，避免重复实现
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class QualityGate:
    def __init__(self, complete):
        self._complete = complete  # complete(system, user) -> str

    def check_section(self, material: str, facts: str, body: str) -> SectionQuality:
        """接地闸（三类判定）：逐句送蕴含模型，按 verdicts 保留/删除各句，
        计算存活率(survival rate) = kept/total，≥ GROUNDING_THRESHOLD → published。

        三类判定语义（接地闸返回 true=keep）：
          - 事实硬接地：材料直接支持的事实句 → keep=True
          - 引导句/观察句：引导观众感知、无具体可证伪事实 → keep=True（不占"无据名额"）
          - 解读句：主观/情感诠释 → keep=True（同上）
          - 无据事实主张：涉具体事实但材料不支持 → keep=False（被删）

        因此低存活率 = 大量事实性主张无材料支持（料薄/脑补） → needs_review；
        新语义下引导/解读句天然留存，存活率比纯事实模式更高，阈值语义不变。

        不再做阻塞性 fact-consistency 对账——它对 Joconde 富材料里的事件年(展出/收购)
        高频误报、误杀已接地内容(2026-06-21 prod 金丝雀诊断：grounding=1.0 的段被年份
        误判杀掉)，且其目标(错年份/错作者)已被蕴含覆盖(材料不支持→会被删)。
        `facts` 入参保留以兼容调用方签名。fact-consistency prompt 仍在 prompts.py 备用。
        """
        parse = _parse()
        # 段落感知:按 \n\n 拆段,段内逐句;过闸后段内保留句用空格连、段间用 \n\n 连,
        # 保住多段结构(馆介绍分段/未来多段正文)。单段输入 → 行为与旧版逐字相同。
        paragraphs = _split_paragraphs(body)
        para_sentences = [_split_sentences(p) for p in paragraphs]
        sentences = [s for ps in para_sentences for s in ps]  # 扁平送闸(判定顺序不变)
        if not sentences:
            return SectionQuality(body=None, status="needs_review", grounding_ratio=0.0)

        e_sys, e_user = build_entailment_prompt(material, sentences)
        verdicts = parse(self._complete(e_sys, e_user)).get("verdicts") or []
        keep = [
            i < len(verdicts) and verdicts[i] is True for i in range(len(sentences))
        ]

        idx, kept_total, kept_paras = 0, 0, []
        for ps in para_sentences:
            kept_here = []
            for s in ps:
                if keep[idx]:
                    kept_here.append(s)
                idx += 1
            if kept_here:
                kept_paras.append(" ".join(kept_here))
                kept_total += len(kept_here)
        grounding_ratio = kept_total / len(sentences)
        kept_body = "\n\n".join(kept_paras) if kept_paras else None

        published = kept_body is not None and grounding_ratio >= GROUNDING_THRESHOLD
        orphaned = published and _opening_is_orphaned(kept_body)
        if orphaned:
            published = False
        if published:
            from app.services.enrichment.lang_detect import text_in_language

            # en 轴心须英文:接地过但语言不是英文(镜像法语源)→needs_review
            if not text_in_language(kept_body, "en"):
                published = False
        return SectionQuality(
            body=kept_body,
            status="published" if published else "needs_review",
            grounding_ratio=grounding_ratio,
            conflicts=[],
            score=grounding_ratio,
            orphaned=orphaned,
        )

    def gate(self, material: str, facts: str, sections: dict) -> dict:
        """逐段过闸。sections 里 body 为 None/空的段视为 absent，跳过不进结果。
        返回 {section_code: SectionQuality}。"""
        results = {}
        for code, body in sections.items():
            if not body:
                continue
            results[code] = self.check_section(material, facts, body)
        return results
