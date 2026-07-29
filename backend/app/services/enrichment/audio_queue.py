"""音频生成优先队列 —— **只回答"该生成哪些",不负责生成**。

自托管批量生成(VoxCPM2 等)消费这里的输出;tts-1 仍是按需兜底,长期保留。

## 为什么要分层,而不是"有文本就全生成"

按 prod 实测(2026-07-29):每件每语言 guide 372 字 ≈ 1.3 分钟,
全段(background+analysis+问答)≈ 3.4 分钟。真实候选宇宙 ≈ 5000 件 × 3 语言:
  只 guide  → 1.5 万文件 / 325 小时 / ~23 GB
  全段      → ~7 万文件 / 850 小时 / ~61 GB
两者都便宜,所以**约束不是成本,是延迟**:

- **guide 必须全预生成** —— 它是识别成功后**自动播**的。这里卡 5 秒,
  直接伤首体验与转化。长尾件一旦有了文本,下一轮就该补上 guide。
- **深度段/问答按件分层** —— 预热的热门件全段预生成(付费用户集中在那儿,
  点开不该等);长尾件只 guide,深度段按需(真有人点,现场生成一次即永久落库)。

规则跟着钱走,而且不需要预测"哪个段会被听"。

## 优先信号(不用 popularity 启发式)

popularity 在小馆会失真(橘园睡莲 pop=0,按热度排最后)。改用真实行为:
  1. 用户真正播放过的作品(付费用户的足迹 = 现场热点)
  2. 识别命中过的作品
  3. 兜底才用 popularity
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.content import ObjectContentSection, ObjectSuggestedQuestion
from app.models.museum import Museum
from app.models.museum_object import MuseumObject

# 自动播的那一段:必须全覆盖
HERO_SECTION = "guide"

# 不走音频的段落:facts 是列表展示(前端 factsExpanded 开关),不是叙述文本。
# 放进队列等于白烧 GPU。
NON_AUDIO_SECTIONS = {"facts"}


@dataclass(frozen=True)
class AudioJob:
    """一个待生成单元。`kind` 决定调用方走 section 还是 qa 的生成路径。"""

    qid: str
    language: str
    section: str  # section_code,或 qa_{sort}
    kind: str  # "section" | "qa"
    museum_slug: str | None
    reason: str  # 为什么排到它:hero_missing / head_full / engine_upgrade
    priority: int  # 越小越先做


def _played_qids(db: Session, limit: int = 5000) -> set[str]:
    """用户真播过的作品 —— 现场热点的最强信号(付费墙给的新数据)。

    ⚠️ 优先信号只是**排序增强**,不是硬依赖:取不到就退化成按 qid 排,
    绝不能让队列构建整个失败(同 log_event 的纪律)。
    """
    from app.models.app_event import AppEvent

    rows = (
        db.query(AppEvent.props)
        .filter(AppEvent.name.in_(["free_audio_played", "paywall_viewed_from_audio"]))
        .limit(limit)
    )
    out = set()
    try:
        for (props,) in rows:
            qid = (props or {}).get("qid")
            if qid:
                out.add(qid)
    except Exception:  # 表缺失/查询失败 → 无信号,不是错误
        return set()
    return out


def _recognized_qids(db: Session, limit: int = 5000) -> set[str]:
    from app.models.recognition_event import RecognitionEvent

    try:
        return {
            q
            for (q,) in db.query(RecognitionEvent.top_qid)
            .filter(RecognitionEvent.top_qid.isnot(None))
            .limit(limit)
            if q
        }
    except Exception:  # 同上:信号缺失不该让队列构建失败
        return set()


def build_queue(
    db: Session,
    *,
    languages: list[str],
    target_engine: str,
    head_size: int = 2000,
    museum_slug: str | None = None,
    include_upgrades: bool = True,
    limit: int = 5000,
) -> list[AudioJob]:
    """算出待生成清单,按优先级排好序。

    [target_engine] 目标引擎(如 "voxcpm2")。已经是该引擎的跳过;
    其它引擎生成的且 [include_upgrades] 为真时排进"音色统一"批次。

    ⚠️ **[languages] 由调用方按质量闸决定**。VoxCPM2 目前 CJK 达标、欧语待攻,
    先铺 zh;用没过闸的音色去覆盖量最大的 en/fr 是净损失。

    ⚠️ 迁移顺序应保证"一次参观内部音色一致" —— 调用方按 (馆, 语言) 整体推进,
    别零散替换:同一次参观里 A 件新音色、B 件旧音色,比全是旧音色更糟。
    """
    q = db.query(MuseumObject.id, MuseumObject.qid, Museum.slug).join(
        Museum, MuseumObject.museum_id == Museum.id
    )
    if museum_slug:
        q = q.filter(Museum.slug == museum_slug)
    objs = {oid: (qid, slug) for oid, qid, slug in q}
    if not objs:
        return []

    hot = _played_qids(db) | _recognized_qids(db)

    # 头部:热点优先,其次按已有内容量(有内容=被认真做过)
    ranked = sorted(
        objs.items(),
        key=lambda kv: (0 if kv[1][0] in hot else 1, kv[1][0]),
    )
    head_ids = {oid for oid, _ in ranked[:head_size]}

    jobs: list[AudioJob] = []

    rows = db.query(
        ObjectContentSection.object_id,
        ObjectContentSection.language,
        ObjectContentSection.section_code,
        ObjectContentSection.audio_key,
        ObjectContentSection.audio_engine,
    ).filter(
        ObjectContentSection.body.isnot(None),
        func.length(ObjectContentSection.body) > 0,
        ObjectContentSection.language.in_(languages),
    )
    for oid, lang, code, key, engine in rows:
        if oid not in objs or code in NON_AUDIO_SECTIONS:
            continue
        qid, slug = objs[oid]
        is_hero = code == HERO_SECTION
        in_head = oid in head_ids
        # 长尾件只做 hero;头部件全段
        if not is_hero and not in_head:
            continue
        if key and engine == target_engine:
            continue
        if key and not include_upgrades:
            continue

        if not key:
            reason = "hero_missing" if is_hero else "head_full"
            # hero 缺失最急:它是自动播的
            prio = 0 if is_hero else 20
        else:
            reason = "engine_upgrade"
            prio = 40 if is_hero else 60
        if qid in hot:
            prio -= 5
        jobs.append(AudioJob(qid, lang, code, "section", slug, reason, max(prio, 0)))

    # 问答只给头部件(每条 73 字 ≈ 18 秒,便宜;但长尾件几乎没人点)
    qa_rows = db.query(
        ObjectSuggestedQuestion.object_id,
        ObjectSuggestedQuestion.language,
        ObjectSuggestedQuestion.sort,
        ObjectSuggestedQuestion.audio_key,
        ObjectSuggestedQuestion.audio_engine,
    ).filter(ObjectSuggestedQuestion.language.in_(languages))
    for oid, lang, sort, key, engine in qa_rows:
        if oid not in head_ids or oid not in objs:
            continue
        if key and (engine == target_engine or not include_upgrades):
            continue
        qid, slug = objs[oid]
        jobs.append(
            AudioJob(
                qid,
                lang,
                f"qa_{sort}",
                "qa",
                slug,
                "head_full" if not key else "engine_upgrade",
                30 if not key else 70,
            )
        )

    jobs.sort(key=lambda j: (j.priority, j.museum_slug or "", j.language, j.qid))
    return jobs[:limit]


def coverage(db: Session, languages: list[str]) -> dict:
    """覆盖率报表:迁移进度不该靠猜。"""
    out: dict[str, dict] = {}
    rows = (
        db.query(
            ObjectContentSection.language,
            ObjectContentSection.audio_engine,
            func.count(),
        )
        .filter(
            ObjectContentSection.body.isnot(None),
            ObjectContentSection.language.in_(languages),
            ObjectContentSection.section_code == HERO_SECTION,
        )
        .group_by(ObjectContentSection.language, ObjectContentSection.audio_engine)
    )
    for lang, engine, n in rows:
        d = out.setdefault(lang, {})
        d[engine or "(无音频)"] = n
    return out
