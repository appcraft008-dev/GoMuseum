"""音频损失闸(契约纪律 37 第①②层):任何写入让**已有音频**失效,都先被这里看见。

## 为什么是这里

2026-09-14 与 09-26,`generate --force` 两次顺带清掉跨馆作者的简介音频,第一次 12 天
没人发现。会让音频失效的写入点当时就有 4 处(正文段改写 / 问答改写 / 问答删行 / 作者
简介重写),分散在两个文件里,以后还会有新的。**靠"每个写入点都记得小心"防不住** ——
所以装在所有写入都要经过的地方:`SessionLocal` 的 `before_flush`(注册见
`app.core.database`)。web 与所有脚本都用 SessionLocal,新写的脚本自动受保护。

## 行为

- **记账(总是)**:每条损失写一行 `audio_invalidations`(key、所属行、语种、当时的文字、
  哪条命令)。丢了能照着挂回去;GC 也据此不删这些文件。
- **拦截(默认)**:进程里累计损失超过额度 → 抛 `AudioLossBlocked`,整次运行中止。
  额度默认 0;确需让音频失效(如文本改版后要重录)时显式放行:
  `GOMUSEUM_ALLOW_AUDIO_LOSS=N` 环境变量,或 `onboard ... --allow-audio-loss N`。
- **web 进程只记账不拦**(`set_record_only()`,在 app.main 启动时调用):
  用户请求里不该因为这道闸报错;web 侧的损失照样进台账,由每日盘点(第③层)兜。

## 什么算损失

「有 key → 没 key」:段/问答的 `audio_key` 被置空、带音频的行被删、作者 `bio_audio`
字典里某语种没了。**换成另一个 key 不算**(tts-1 → VoxCPM2 重录是升级,不是损失),
所以音频会话正常灌入不受影响。

⚠️ 管不到的:绕过 ORM 的写入(psql 手写 UPDATE、`query.update()/delete()` 批量语句)。
前者靠每日盘点兜;后者代码里不要对这三张表用批量语句改 audio_key 或删带音频的行。
"""

from __future__ import annotations

import os
import sys

from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select

ENV_ALLOW = "GOMUSEUM_ALLOW_AUDIO_LOSS"


class AudioLossBlocked(BaseException):
    """⚠️ 故意继承 BaseException 而非 Exception。

    生成管线里到处是 `except Exception: logger.exception(...); continue` —— 普通异常
    会被吞掉,批任务照样跑完,这道闸等于没有。BaseException 与 KeyboardInterrupt 同级,
    穿过这些 try/except 直达进程顶层。
    """


class _Policy:
    def __init__(self):
        self.record_only = False
        self.limit = int(os.environ.get(ENV_ALLOW, "0") or 0)
        self.used = 0


_policy = _Policy()


def set_record_only() -> None:
    """web 进程:只记账不拦(见模块 docstring)。"""
    _policy.record_only = True


def allow(n: int) -> None:
    """本进程最多允许 n 条已有音频失效(CLI 的 --allow-audio-loss)。"""
    _policy.limit = max(int(n or 0), 0)


def _reset_for_tests() -> None:
    _policy.record_only = False
    _policy.limit = 0
    _policy.used = 0


def _db_row(session, model, pk_col, pk, cols):
    """读**库里**的当前值(= 这次 flush 之前的值)。不用 ORM 属性历史:JSON 字段原地改
    再 flag_modified 时历史里没有旧值,读库最稳。"""
    return session.connection().execute(select(*cols).where(pk_col == pk)).first()


def find_losses(session) -> list[dict]:
    from app.models.artist import Artist
    from app.models.content import ObjectContentSection, ObjectSuggestedQuestion

    out: list[dict] = []

    def _changed(obj, attr) -> bool:
        return sa_inspect(obj).attrs[attr].history.has_changes()

    for obj in list(session.dirty) + list(session.deleted):
        deleted = obj in session.deleted
        if isinstance(obj, ObjectContentSection):
            if not deleted and not _changed(obj, "audio_key"):
                continue
            row = _db_row(
                session,
                ObjectContentSection,
                ObjectContentSection.id,
                obj.id,
                [
                    ObjectContentSection.audio_key,
                    ObjectContentSection.audio_engine,
                    ObjectContentSection.body,
                ],
            )
            if row and row[0] and (deleted or not obj.audio_key):
                out.append(
                    dict(
                        entity="section",
                        object_id=obj.object_id,
                        language=obj.language,
                        section_code=obj.section_code,
                        audio_key=row[0],
                        audio_engine=row[1],
                        old_text=row[2],
                        change="delete" if deleted else "cleared",
                    )
                )
        elif isinstance(obj, ObjectSuggestedQuestion):
            if not deleted and not _changed(obj, "audio_key"):
                continue
            row = _db_row(
                session,
                ObjectSuggestedQuestion,
                ObjectSuggestedQuestion.id,
                obj.id,
                [
                    ObjectSuggestedQuestion.audio_key,
                    ObjectSuggestedQuestion.audio_engine,
                    ObjectSuggestedQuestion.question,
                    ObjectSuggestedQuestion.answer,
                ],
            )
            if row and row[0] and (deleted or not obj.audio_key):
                out.append(
                    dict(
                        entity="qa",
                        object_id=obj.object_id,
                        language=obj.language,
                        qa_sort=obj.sort,
                        audio_key=row[0],
                        audio_engine=row[1],
                        old_text=f"{row[2]}\n{row[3]}",
                        change="delete" if deleted else "cleared",
                    )
                )
        elif isinstance(obj, Artist):
            row = _db_row(
                session,
                Artist,
                Artist.qid,
                obj.qid,
                [Artist.bio_audio, Artist.bio_audio_engine, Artist.bio],
            )
            if not row:
                continue
            old_keys, old_eng, old_bio = row[0] or {}, row[1] or {}, row[2] or {}
            new_keys = {} if deleted else (obj.bio_audio or {})
            for lang, key in old_keys.items():
                if key and not new_keys.get(lang):
                    out.append(
                        dict(
                            entity="artist_bio",
                            artist_qid=obj.qid,
                            language=lang,
                            audio_key=key,
                            audio_engine=old_eng.get(lang),
                            old_text=old_bio.get(lang),
                            change="delete" if deleted else "removed",
                        )
                    )
    return out


def _describe(loss: dict) -> str:
    who = loss.get("artist_qid") or str(loss.get("object_id"))
    part = loss.get("section_code") or (
        f"qa#{loss['qa_sort']}" if loss.get("qa_sort") is not None else "bio"
    )
    return (
        f"{loss['entity']:10s} {who} {loss.get('language')} {part} ({loss['change']})"
    )


def on_flush(session) -> None:
    losses = find_losses(session)
    if not losses:
        return
    from app.models.audio_invalidation import AudioInvalidation

    over = False
    if not _policy.record_only:
        _policy.used += len(losses)
        over = _policy.used > _policy.limit
    if over:
        lines = "\n".join("  " + _describe(x) for x in losses[:15])
        more = f"\n  … 另有 {len(losses) - 15} 条" if len(losses) > 15 else ""
        raise AudioLossBlocked(
            f"\n⛔ 音频损失闸(契约纪律 37):这次写入会让 {len(losses)} 条**已有音频**失效"
            f"(本进程累计 {_policy.used},额度 {_policy.limit}),已中止,什么都没写入。\n"
            f"{lines}{more}\n"
            "先确认这是不是你要的:共享实体(作者)是否被单件操作顺带改写?这些音频是谁的、\n"
            "要不要重录?确认后显式放行:`--allow-audio-loss N` 或 "
            f"`{ENV_ALLOW}=N`(N = 预期失效条数)。"
        )
    command = " ".join(sys.argv)[:500]
    allowed = "record_only" if _policy.record_only else "allowed"
    for x in losses:
        session.add(AudioInvalidation(command=command, allowed=allowed, **x))
