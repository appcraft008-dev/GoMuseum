"""公开网页层(spec 2026-09-20-share-web-pages-design §四/§五)。

⚠️ 这里只读 repo 层,**不调内容接口、不带任何身份**:懒生成闸按"有无身份"判,
给这里配一个服务账号令牌 = 把 2026-09-20 关掉的匿名成本洞原样打开。
⚠️ 这里没有音频,一个字节都没有(音频是收费核心资产)。
"""

import html as _html
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.museum import Museum
from app.services.event_log import log_event
from app.services.museum_repo import get_object_content, museum_name
from app.services.share import (
    PLAY_URL,
    card_url,
    copy_for,
    guide_languages,
    pick_language,
    primary_image,
    public_object,
)
from app.services.share_card import render_card
from app.services.storage import get_object_storage

router = APIRouter(tags=["share-web"])

_TEMPLATE = (
    Path(__file__).resolve().parents[2] / "templates" / "share_object.html"
).read_text(encoding="utf-8")
_NOT_FOUND = (
    "<!DOCTYPE html><html><head><meta charset='utf-8'>"
    "<meta name='robots' content='noindex'><title>GoMuseum</title></head>"
    "<body><p>404</p></body></html>"
)

e = _html.escape


def _not_found() -> HTMLResponse:
    """隐身馆 / 未知 qid / 无正文 → 同一个响应,不泄漏差异。"""
    return HTMLResponse(
        _NOT_FOUND, status_code=404, headers={"X-Robots-Tag": "noindex"}
    )


def _paras(text: str) -> str:
    return "".join(f"<p>{e(p)}</p>" for p in text.split("\n\n") if p.strip())


def _cta(ua: str, copy: dict) -> str:
    # 推正式前内测轨道的 Play 链接对外人是"找不到该应用";微信里打不开 Play → 都只给一句话
    if not settings.SHARE_PLAY_LIVE or "MicroMessenger" in ua:
        return f'<div class="cta">{e(copy["cta"])}</div>'
    if "iPhone" in ua or "iPad" in ua:
        return (
            f'<div class="cta">{e(copy["cta"])}'
            f"<small>{e(copy['android_only'])}</small></div>"
        )
    return f'<a class="cta" href="{e(PLAY_URL)}">{e(copy["cta"])} →</a>'


def _render(text: dict[str, str], raw: dict[str, str]) -> str:
    out = _TEMPLATE
    for k, v in text.items():
        out = out.replace(f"__{k}__", e(v, quote=True))
    for k, v in raw.items():  # 已在拼装时逐段转义过
        out = out.replace(f"__{k}__", v)
    return out


@router.get("/a/{slug}/{qid}", response_class=HTMLResponse)
def share_page(
    slug: str,
    qid: str,
    request: Request,
    lang: str = "",
    s: str = "",
    db: Session = Depends(get_db),
):
    obj = public_object(db, slug, qid)
    langs = guide_languages(db, obj) if obj else []
    if not langs:
        return _not_found()
    chosen = pick_language(lang, request.headers.get("accept-language", ""), langs)
    if lang and lang != chosen:
        suffix = f"&s={s}" if s else ""
        return RedirectResponse(
            f"/a/{slug}/{qid}?lang={chosen}{suffix}", status_code=302
        )

    data = get_object_content(db, slug, qid, chosen)
    if data is None:
        return _not_found()
    copy = copy_for(chosen)
    guide = data.get("default_guide") or {}
    artist = data.get("artist") or {}
    facts = data.get("facts") or {}
    images = data.get("images") or []
    title = data.get("title") or qid

    body = _paras(guide.get("body") or "")
    for tab in data.get("tabs") or []:
        body += f"<section><h2>{e(tab['label'])}</h2>{_paras(tab['body'])}</section>"
    qs = data.get("suggested_questions") or []
    if qs:
        body += (
            f"<section><h2>{e(copy['faq'])}</h2>"
            + "".join(
                f"<details><summary>{e(q['question'])}</summary>{_paras(q.get('answer') or '')}</details>"
                for q in qs
            )
            + "</section>"
        )
    if artist.get("bio"):
        body += (
            f"<section><h2>{e(copy['artist'])}</h2>{_paras(artist['bio'])}</section>"
        )

    credits = [i["credit"] for i in images if i.get("credit")]
    base = settings.PUBLIC_WEB_BASE_URL
    hreflang = "\n".join(
        f'<link rel="alternate" hreflang="{l}" href="{e(f"{base}/a/{slug}/{qid}?lang={l}")}" />'
        for l in langs
    )

    log_event(
        db,
        "share_page_view",
        museum_slug=slug,
        qid=qid,
        lang=chosen,
        source=s or "direct",
    )
    db.commit()

    return HTMLResponse(
        _render(
            {
                "HTMLLANG": chosen,
                "TITLE": title,
                "OGTITLE": (
                    f"{title} — {artist['name']}" if artist.get("name") else title
                ),
                "OGDESC": copy["og"],
                "OGIMAGE": images[0]["url"] if images else card_url(slug, qid, chosen),
                "CANONICAL": f"{base}/a/{slug}/{qid}?lang={chosen}",
                "BYLINE": " · ".join(
                    x for x in (artist.get("name"), facts.get("date")) if x
                ),
            },
            {
                "HREFLANG": hreflang,
                "HERO": (
                    f'<img class="hero" src="{e(images[0]["url"])}" alt="{e(title)}" />'
                    if images
                    else ""
                ),
                "AUDIO": (
                    f'<div class="audio">🎧 {e(copy["audio"])}</div>'
                    if guide.get("has_audio")
                    else ""
                ),
                "BODY": body,
                "CREDITS": (
                    f"{e(copy['credits'])}: " + " · ".join(e(c) for c in credits)
                    if credits
                    else ""
                ),
                "CTA": _cta(request.headers.get("user-agent", ""), copy),
            },
        )
    )


@router.get("/a/{slug}/{qid}/card.png")
def share_card(
    slug: str,
    qid: str,
    request: Request,
    lang: str = "",
    db: Session = Depends(get_db),
):
    """分享图。判定规则与网页完全一致(同一组函数)。"""
    obj = public_object(db, slug, qid)
    langs = guide_languages(db, obj) if obj else []
    img = primary_image(db, obj) if langs else None
    if img is None:
        return _not_found()
    chosen = pick_language(lang, request.headers.get("accept-language", ""), langs)
    storage = get_object_storage()
    large = f"{img.image_key}_large.jpg"
    raw = storage.get(large)
    data = get_object_content(db, slug, qid, chosen)
    if raw is None or data is None:
        return _not_found()
    artist = (data.get("artist") or {}).get("name")
    date = (data.get("facts") or {}).get("date")
    museum = db.query(Museum).filter_by(slug=slug).one()
    # 署名取内容接口处理过的那份(画家本人不算署名,见 museum_repo._photo_credit),
    # 不读 img.credit 原值 —— 否则分享图上会多出一行画家名
    url = storage.public_url(large)
    credit = next(
        (i.get("credit") for i in data.get("images") or [] if i.get("url") == url), None
    )
    png = render_card(
        raw,
        title=data.get("title") or qid,
        byline=" · ".join(x for x in (artist, date) if x),
        footer=f"{museum_name(museum, chosen)} · GoMuseum",
        credit=credit,
        language=chosen,
    )
    return Response(
        png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )
