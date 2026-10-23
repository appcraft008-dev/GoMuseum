"""公开网站(spec 2026-10-22-website-v1)。

⚠️ 同 share_pages:只读 repo 层,不带身份、不调内容接口、不点火。
⚠️ 音频只有试听件、只经 /w/audio 签发短时效地址。
⚠️ 本 router 必须最后挂到 app 上(见 main.py):/{lang}/{city}/ 会吞掉之后注册的路由。
"""

import hashlib
import math
import re
import time
from pathlib import Path
from urllib.parse import quote
from xml.sax.saxutils import quoteattr

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from jinja2 import Environment, FileSystemLoader
from sqlalchemy.orm import Session

from app.api.web.share_pages import _not_found
from app.core.config import settings
from app.core.database import get_db
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.entitlement_service import pass_for_museum, pass_title
from app.services.museum_repo import (
    _sized,
    get_object_content,
    museum_name,
    museum_website,
)
from app.services.must_see import MUST_SEE
from app.services.search.inprocess import search as run_search
from app.services.share import _accept_codes, card_url, guide_languages
from app.services.storage import get_object_storage
from app.services.website import data as wd
from app.services.website.copy import t as _t
from app.services.website.tracking import (
    BEACON_MAX_BYTES,
    BEACON_NAMES,
    device_class,
    log_page_view,
    play_url,
    qr_data_uri,
)
from app.services.website.trials import trial_parts, trial_qids

router = APIRouter(tags=["website"])

_ROOT = Path(__file__).resolve().parents[2]
_STATIC = _ROOT / "static" / "web"
_STATIC_FILES = {p.name: p for p in _STATIC.iterdir() if p.is_file()}
ASSET_V = hashlib.sha1(
    b"".join(_STATIC_FILES[n].read_bytes() for n in ("site.css", "site.js"))
).hexdigest()[:8]
_env = Environment(
    loader=FileSystemLoader(_ROOT / "templates" / "web"), autoescape=True
)

LANG_NAMES = {
    "en": "English",
    "fr": "Français",
    "zh": "简体中文",
    "zh-hant": "繁體中文",
    "de": "Deutsch",
    "es": "Español",
    "it": "Italiano",
    "pl": "Polski",
    "ja": "日本語",
    "ko": "한국어",
}
_HREFLANG = {"zh-hant": "zh-Hant"}
PAGE_SIZE = 48


def _abs(path: str) -> str:
    return settings.PUBLIC_WEB_BASE_URL + path


_CJK = {"zh", "zh-hant", "ja"}
_SENT_END = re.compile(
    r"[。！？]|(?:[!?]|(?<!\d)\.)(?=\s|$)"
)  # 「12. Jh.」序数点不算句末


def _summary(text: str, lang: str) -> str:
    """meta description:搜索结果只显示 ~155 字符(中日 ~80 字),在句末截,找不到句末才按词截加省略号。"""
    n = 80 if lang in _CJK else 155
    text = " ".join(text.split())
    if len(text) <= n:
        return text
    ends = [m.end() for m in _SENT_END.finditer(text) if m.end() <= n]
    if ends and ends[-1] >= n // 3:
        return text[: ends[-1]]
    cut = text[: n - 1]
    if lang not in _CJK and " " in cut:
        cut = cut[: cut.rfind(" ")]
    return cut.rstrip(" ,，、;；:：") + "…"


def render(
    request: Request,
    template: str,
    *,
    lang: str,
    page_type: str,
    alternates: list[str],
    path_for,
    db=None,
    noindex: bool = False,
    description: str = "",
    jsonld: dict | None = None,
    **ctx,
) -> HTMLResponse:
    """所有网页的统一出口:hreflang/canonical/noindex/下载区/语言提示都在这里定。"""
    ua = request.headers.get("user-agent", "")
    device = device_class(ua)
    play = play_url(page_type)
    if db is not None:
        log_page_view(
            db,
            request,
            lang=lang,
            page_type=page_type,
            museum_slug=ctx.get("museum_slug"),
            qid=ctx.get("qid"),
        )
    hreflang = [
        (_HREFLANG.get(code, code), _abs(path_for(code))) for code in alternates
    ]
    if "en" in alternates:
        hreflang.append(("x-default", _abs(path_for("en"))))
    hint = None
    for code in _accept_codes(request.headers.get("accept-language", "")):
        if code == lang:
            break
        if code in alternates:
            hint = (path_for(code), LANG_NAMES[code])
            break
    html = _env.get_template(template).render(
        t=lambda key, **kw: _t(lang, key, **kw),
        lang=lang,
        langs=wd.LANGS,
        lang_names=LANG_NAMES,
        lang_href=lambda code: path_for(code) if code in alternates else f"/{code}/",
        hreflang=hreflang,
        canonical=_abs(path_for(lang)),
        noindex=noindex or lang not in alternates,
        page_type=page_type,
        play=play,
        device=device,
        qr=qr_data_uri(play) if play and device == "desktop" else None,
        free_n=settings.FREE_RECOGNITION_QUOTA,
        asset_v=ASSET_V,
        lang_hint=hint,
        description=_summary(description, lang),
        jsonld=jsonld,
        **ctx,
    )
    return HTMLResponse(html)


def _city_name(city: wd.City, lang: str) -> str:
    return city.names.get(lang) or city.names.get("en") or city.slug


def _museum_vm(db, m: Museum, lang: str) -> dict:
    cover = None
    if m.cover_image_key:
        cover = _sized(get_object_storage(), m.cover_image_key, "thumb")
    return {
        "slug": m.slug,
        "city": wd.museum_city_slug(m),
        "name": museum_name(m, lang),
        "count": wd.guide_count(db, [m.id], lang),
        "cover": cover,
    }


def _museum_vms(db, museums: list[Museum], lang: str) -> list[dict]:
    """该语言有内容的馆才上卡片(没内容的馆页是 404,不能链过去)。"""
    return [vm for vm in (_museum_vm(db, m, lang) for m in museums) if vm["count"]]


def _must_see_cards(db, m: Museum, lang: str) -> list:
    listed = MUST_SEE.get(m.slug) or []
    return wd.cards_for_qids(db, [m.id], lang, listed) if listed else []


def _panels(db, museums: list[Museum], lang: str) -> list[dict]:
    out = []
    for m in museums:
        cards = _must_see_cards(db, m, lang)
        if not cards:
            continue  # 没必看清单(或该语言都没内容)的馆不出必看区
        out.append(
            {
                "slug": m.slug,
                "city": wd.museum_city_slug(m),
                "name": museum_name(m, lang),
                "cards": cards[:6],
                "total": len(cards),
                "count": wd.guide_count(db, [m.id], lang),
                "trials": set(trial_qids(db, m, lang)),
            }
        )
    return out


def _pass_note(museums: list[Museum], lang: str) -> str | None:
    for m in museums:
        pid = pass_for_museum(m)
        if pid:
            return _t(lang, "pass_note", **{"pass": pass_title(pid, lang)})
    return None


def _screenshot(lang: str) -> tuple[str, str] | None:
    """首页手机两帧(扫描识别中 → 打开作品播放导览),缺该语言回落英文。"""
    for code in (lang, "en"):
        pair = (f"app-{code}-scan.jpg", f"app-{code}-play.jpg")
        if all(n in _STATIC_FILES for n in pair):
            return tuple(f"/w/static/{n}" for n in pair)
    return None


def _paras(text: str | None) -> list[str]:
    return [p.strip() for p in (text or "").split("\n\n") if p.strip()]


_SITEMAP_TTL = 3600
# ponytail: 进程内 1 小时缓存;单语言 sitemap 现约 1.2k 条,远低于协议 5 万条上限,未做分片——
# 某语言超过 5 万条时改成 sitemap-{lang}-{n}.xml 分片(索引同步列出)
_sitemap_cache: dict = {}


def _x(text: str) -> str:
    return quoteattr(text)[1:-1]  # 元素文本:同属性转义,去掉两端引号


def _xml(body: str) -> Response:
    return Response(
        '<?xml version="1.0" encoding="UTF-8"?>\n' + body,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/robots.txt")
def robots():
    return Response(
        "User-agent: *\nAllow: /\nDisallow: /w/audio/\nDisallow: /w/e\n"
        f"Sitemap: {_abs('/sitemap.xml')}\n",
        media_type="text/plain",
    )


@router.get("/sitemap.xml")
def sitemap_index():
    items = "".join(
        f"<sitemap><loc>{_x(_abs(f'/sitemap-{lang}.xml'))}</loc></sitemap>"
        for lang in wd.LANGS
    )
    return _xml(
        '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f"{items}</sitemapindex>"
    )


def _sitemap_entries(db, lang: str) -> list[tuple[str, list[str]]]:
    """(路径模板 '/{}/...', 该页存在的语言);只收 lang 在其中的页。"""
    pages = [("/{}/", list(wd.LANGS))]
    for c in wd.public_cities(db):
        ids = [m.id for m in c.museums]
        pages.append((f"/{{}}/{c.slug}/", wd.page_languages(db, ids)))
        for aq, langs in wd.artist_languages(db, ids).items():
            pages.append((f"/{{}}/{c.slug}/artists/{aq}/", langs))
        for m in c.museums:
            base = f"/{{}}/{c.slug}/{m.slug}/"
            pages.append((base, wd.page_languages(db, [m.id])))
            for aq, langs in wd.artist_languages(db, [m.id]).items():
                pages.append((f"{base}artists/{aq}/", langs))
            for qid, langs in wd.work_languages(db, [m.id]).items():
                pages.append((f"{base}{qid}/", langs))
    return [(p, langs) for p, langs in pages if lang in langs]


@router.get("/sitemap-{lang}.xml")
def sitemap_lang(lang: str, db: Session = Depends(get_db)):
    if lang not in wd.LANGS:
        return _not_found()
    hit = _sitemap_cache.get(lang)
    if hit and time.monotonic() - hit[0] < _SITEMAP_TTL:
        return _xml(hit[1])
    rows = []
    for tpl, langs in _sitemap_entries(db, lang):
        alts = "".join(
            f'<xhtml:link rel="alternate" hreflang="{_HREFLANG.get(code, code)}" '
            f"href={quoteattr(_abs(tpl.format(code)))}/>"
            for code in langs
        )
        if "en" in langs:
            alts += (
                '<xhtml:link rel="alternate" hreflang="x-default" '
                f"href={quoteattr(_abs(tpl.format('en')))}/>"
            )
        rows.append(f"<url><loc>{_x(_abs(tpl.format(lang)))}</loc>{alts}</url>")
    body = (
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" '
        'xmlns:xhtml="http://www.w3.org/1999/xhtml">' + "".join(rows) + "</urlset>"
    )
    _sitemap_cache[lang] = (time.monotonic(), body)
    return _xml(body)


@router.post("/w/e", status_code=204)
async def beacon(request: Request, db: Session = Depends(get_db)):
    """网页信标(sendBeacon)。白名单外、超长、坏 JSON 一律静默丢弃,恒 204、不设 cookie。"""
    import json

    raw = await request.body()
    if len(raw) > BEACON_MAX_BYTES:
        return Response(status_code=204)
    try:
        body = json.loads(raw or b"{}")
    except ValueError:
        return Response(status_code=204)
    name = body.get("name") if isinstance(body, dict) else None
    if not isinstance(name, str) or name not in BEACON_NAMES:
        return Response(status_code=204)
    from app.services.event_log import log_event

    def s(key):
        v = body.get(key)
        return str(v)[:64] if v is not None else None

    log_event(
        db,
        name,
        museum_slug=s("museum_slug"),
        lang=s("lang") if s("lang") in wd.LANGS else None,
        page_type=s("page_type"),
        qid=s("qid"),
        part=s("part"),
        channel=s("channel"),
        device=device_class(request.headers.get("user-agent", "")),
    )
    return Response(status_code=204)


@router.get("/w/static/{name}")
def static_file(name: str):
    path = _STATIC_FILES.get(name)
    if path is None:
        return _not_found()
    return FileResponse(path, headers={"Cache-Control": "public, max-age=86400"})


@router.get("/w/audio/{museum_slug}/{qid}/{part}")
def trial_audio(
    museum_slug: str, qid: str, part: str, lang: str = "", db: Session = Depends(get_db)
):
    if lang not in wd.LANGS:  # 先挡:任意 lang 进缓存键会无限撑大进程缓存
        return _not_found()
    m = (
        db.query(Museum)
        .filter(Museum.slug == museum_slug, Museum.published_at.isnot(None))
        .one_or_none()
    )
    # 页面可能由缓存更新的 worker 渲染(已给 ▶),本 worker 缓存未命中就重算一次再判。
    # ponytail: 非试听件每次 404 都多一次重算;被刷时靠 nginx 限流兜
    if m is None or (
        qid not in trial_qids(db, m, lang)
        and qid not in trial_qids(db, m, lang, fresh=True)
    ):
        return _not_found()
    obj = db.query(MuseumObject).filter_by(museum_id=m.id, qid=qid).one()
    key = trial_parts(db, obj, lang).get(part)
    if not key:
        return _not_found()
    return RedirectResponse(
        get_object_storage().presigned_url(key, 3600),
        status_code=302,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/{lang}/", response_class=HTMLResponse)
def home(lang: str, request: Request, db: Session = Depends(get_db)):
    if lang not in wd.LANGS:
        return _not_found()
    cities = []
    for c in wd.public_cities(db):
        vms = _museum_vms(db, c.museums, lang)
        if vms:
            cities.append((c, vms))
    hero_sub = _t(
        lang,
        "hero_sub",
        city=" · ".join(_city_name(c, lang) for c, _ in cities),
        n=sum(len(vms) for _, vms in cities),
    )
    return render(
        request,
        "home.html",
        db=db,
        lang=lang,
        page_type="home",
        alternates=list(wd.LANGS),
        path_for=lambda code: f"/{code}/",
        title=f"GoMuseum — {_t(lang, 'hero_title')}",
        description=hero_sub,
        jsonld={
            "@context": "https://schema.org",
            "@type": "MobileApplication",
            "name": "GoMuseum",
            "description": hero_sub,
            "url": _abs(f"/{lang}/"),
            "operatingSystem": "Android",
            "applicationCategory": "TravelApplication",
            "inLanguage": lang,
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
        },
        hero_sub=hero_sub,
        screenshot=_screenshot(lang),
        cities=[
            {"slug": c.slug, "name": _city_name(c, lang), "museums": vms}
            for c, vms in cities
        ],
        panels=_panels(db, cities[0][0].museums, lang) if len(cities) == 1 else [],
    )


@router.get("/{lang}/{city}/", response_class=HTMLResponse)
def city_page(lang: str, city: str, request: Request, db: Session = Depends(get_db)):
    c = wd.find_city(db, city) if lang in wd.LANGS else None
    ids = [m.id for m in c.museums] if c else []
    if not c or not wd.guide_count(db, ids, lang):
        return _not_found()
    name = _city_name(c, lang)
    vms = _museum_vms(db, c.museums, lang)
    hero_sub = _t(lang, "hero_sub", city=name, n=len(vms))
    return render(
        request,
        "city.html",
        db=db,
        lang=lang,
        page_type="city",
        alternates=wd.page_languages(db, ids),
        path_for=lambda code: f"/{code}/{city}/",
        title=f"{name} · GoMuseum",
        description=hero_sub,
        city=city,
        city_name=name,
        hero_sub=hero_sub,
        museums=vms,
        panels=_panels(db, c.museums, lang),
        artists=wd.top_artists(db, ids, lang),
        pass_note=_pass_note(c.museums, lang),
    )


def _artist_page(request, db, lang, city, artist_qid, museums, museum=None, page=1):
    ids = [m.id for m in museums]
    cards, total = wd.list_works(
        db, ids, lang, artist_qid=artist_qid, page=page, page_size=PAGE_SIZE
    )
    if not total or not cards:
        return _not_found()
    a = db.query(Artist).filter_by(qid=artist_qid).one_or_none()
    name = wd._artist_names(db, {artist_qid}, lang).get(artist_qid)
    if not name:
        return _not_found()  # 没名字的作者卡(佚名/哈希 qid)不出作者页
    c = wd.find_city(db, city)
    city_name = _city_name(c, lang)
    place = museum_name(museum, lang) if museum else city_name
    base = (
        f"/{{}}/{city}/{museum.slug}/artists/{artist_qid}/"
        if museum
        else f"/{{}}/{city}/artists/{artist_qid}/"
    )
    life = " – ".join(x for x in ((a.birth, a.death) if a else ()) if x)
    heading = _t(lang, "artist_at", artist=name, place=place)
    trials = set()
    for m in museums:
        trials |= set(trial_qids(db, m, lang))
    return render(
        request,
        "artist.html",
        db=db,
        lang=lang,
        page_type="artist",
        alternates=wd.page_languages(db, ids, artist_qid=artist_qid),
        path_for=lambda code: base.format(code) + (f"?page={page}" if page > 1 else ""),
        title=f"{heading} · GoMuseum",
        description=heading,
        city=city,
        city_name=city_name,
        museum_slug=museum.slug if museum else None,
        museum_name=place if museum else None,
        artist_name=name,
        heading=heading,
        life=life,
        bio=_paras(((a.bio or {}) if a else {}).get(lang)),
        works=cards,
        trials=trials,
        page=page,
        pages=math.ceil(total / PAGE_SIZE),
        page_href=lambda n: base.format(lang) + f"?page={n}",
    )


@router.get("/{lang}/{city}/artists/{artist_qid}/", response_class=HTMLResponse)
def city_artist(
    lang: str,
    city: str,
    artist_qid: str,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
):
    c = wd.find_city(db, city) if lang in wd.LANGS else None
    if not c:
        return _not_found()
    return _artist_page(request, db, lang, city, artist_qid, c.museums, page=page)


@router.get("/{lang}/{city}/{museum_slug}/", response_class=HTMLResponse)
def museum_page(
    lang: str,
    city: str,
    museum_slug: str,
    request: Request,
    page: int = 1,
    category: str = "",
    q: str = "",
    db: Session = Depends(get_db),
):
    m = wd.find_museum(db, city, museum_slug) if lang in wd.LANGS else None
    count = wd.guide_count(db, [m.id], lang) if m else 0
    if not count:
        return _not_found()
    q = q.strip()[:100]
    if q:
        _, hits = run_search(
            db,
            get_object_storage(),
            q,
            museum_id=m.id,
            language=lang,
            limit=PAGE_SIZE,
        )
        works = wd.cards_for_qids(db, [m.id], lang, [h["qid"] for h in hits])
        total, page = len(works), 1
    else:
        cats = wd.categories(db, [m.id], lang)
        if category and category not in {c for c, _, _ in cats}:
            return _not_found()  # 乱填的分类不出 200 空页(会被收录)
        works, total = wd.list_works(
            db, [m.id], lang, category=category or None, page=page, page_size=PAGE_SIZE
        )
        if page > 1 and not works:
            return _not_found()
    base = f"/{lang}/{city}/{museum_slug}/"
    cat_q = f"category={quote(category)}&" if category else ""
    name = museum_name(m, lang)
    c = wd.find_city(db, city)
    intro = _paras((m.description_i18n or {}).get(lang))
    # 馆封面:复用 App 的 cover_image_key(large 档),署名取同一张图
    cover = cover_credit = None
    if m.cover_image_key:
        cover = _sized(get_object_storage(), m.cover_image_key, "large")
        cover_credit = m.cover_credit or (
            db.query(ObjectImage.credit)
            .filter(ObjectImage.image_key == m.cover_image_key)
            .limit(1)
            .scalar()
        )

    def path_for(code):
        p = f"/{code}/{city}/{museum_slug}/"
        if category or page > 1:
            p += "?" + cat_q + (f"page={page}" if page > 1 else "")
        return p.rstrip("&?")

    return render(
        request,
        "museum.html",
        db=db,
        lang=lang,
        page_type="museum",
        alternates=wd.page_languages(db, [m.id]),
        path_for=path_for,
        noindex=bool(q),
        title=f"{name} · GoMuseum",
        description=(intro[0] if intro else name),
        jsonld={
            "@context": "https://schema.org",
            "@type": "Museum",
            "name": name,
            "url": _abs(f"/{lang}/{city}/{museum_slug}/"),
            "address": {
                "@type": "PostalAddress",
                "addressLocality": _city_name(c, lang),
                **({"addressCountry": m.country} if m.country else {}),
            },
            **({"image": cover} if cover else {}),
            **(
                {"sameAs": [museum_website(museum_slug)]}
                if museum_website(museum_slug)
                else {}
            ),
        },
        museum_slug=museum_slug,
        city=city,
        city_name=_city_name(c, lang),
        name=name,
        intro=intro,
        cover=cover,
        cover_credit=cover_credit,
        website=museum_website(museum_slug),
        pass_note=_pass_note([m], lang),
        must_see=_must_see_cards(db, m, lang),
        trials=set(trial_qids(db, m, lang)),
        artists=wd.top_artists(db, [m.id], lang),
        cats=wd.categories(db, [m.id], lang),
        category=category,
        q=q,
        works=works,
        base=base,
        page=page,
        pages=math.ceil(total / PAGE_SIZE) if total else 1,
        page_href=lambda n: f"{base}?{cat_q}page={n}#works",
    )


@router.get(
    "/{lang}/{city}/{museum_slug}/artists/{artist_qid}/",
    response_class=HTMLResponse,
)
def museum_artist(
    lang: str,
    city: str,
    museum_slug: str,
    artist_qid: str,
    request: Request,
    page: int = 1,
    db: Session = Depends(get_db),
):
    m = wd.find_museum(db, city, museum_slug) if lang in wd.LANGS else None
    if not m:
        return _not_found()
    return _artist_page(request, db, lang, city, artist_qid, [m], museum=m, page=page)


def _sections(data: dict, audio: set, src, lang: str) -> list[dict]:
    """导览 → 关于作者 → 深度段(类目顺序)→ 常见问题。audio=真有音频的段;src=None 表示非试听。"""

    def item(key, title, body):
        return {
            "key": key,
            "title": title,
            "body": _paras(body),
            "audio": key in audio,
            "src": src(key) if src and key in audio else None,
        }

    out = []
    guide = data.get("default_guide") or {}
    if (guide.get("body") or "").strip():
        out.append(item("guide", _t(lang, "guide"), guide["body"]))
    artist = data.get("artist") or {}
    if (artist.get("bio") or "").strip():
        title = _t(lang, "about_artist")
        if artist.get("name"):
            title += f" · {artist['name']}"
        out.append(item("artist_bio", title, artist["bio"]))
    for tab in data.get("tabs") or []:
        out.append(item(tab["section_code"], tab["label"], tab["body"]))
    for q in data.get("suggested_questions") or []:
        out.append(item(f"qa-{q['sort']}", q["question"], q.get("answer")))
    return out


@router.get("/{lang}/{city}/{museum_slug}/{qid}/", response_class=HTMLResponse)
def work_page(
    lang: str,
    city: str,
    museum_slug: str,
    qid: str,
    request: Request,
    db: Session = Depends(get_db),
):
    m = wd.find_museum(db, city, museum_slug) if lang in wd.LANGS else None
    obj = (
        db.query(MuseumObject).filter_by(museum_id=m.id, qid=qid).one_or_none()
        if m
        else None
    )
    langs = [x for x in guide_languages(db, obj) if x in wd.LANGS] if obj else []
    if lang not in langs:
        return _not_found()
    data = get_object_content(db, museum_slug, qid, lang)
    if data is None:
        return _not_found()
    is_trial = qid in trial_qids(db, m, lang)
    audio = set(trial_parts(db, obj, lang))
    src = (
        (lambda key: f"/w/audio/{museum_slug}/{qid}/{key}?lang={lang}")
        if is_trial
        else None
    )
    sections = _sections(data, audio, src, lang)
    title = data.get("title") or qid
    artist = (data.get("artist") or {}).get("name")
    mname = museum_name(m, lang)
    images = data.get("images") or []
    others = [c for c in _must_see_cards(db, m, lang) if c.qid != qid][:6]
    first = sections[0]["body"][0] if sections and sections[0]["body"] else ""
    return render(
        request,
        "work.html",
        db=db,
        lang=lang,
        page_type="work",
        alternates=langs,
        path_for=lambda code: f"/{code}/{city}/{museum_slug}/{qid}/",
        title=f"{title}{' — ' + artist if artist else ''} · {mname} · GoMuseum",
        description=first or title,
        og_image=images[0]["url"] if images else card_url(museum_slug, qid, lang),
        museum_slug=museum_slug,
        qid=qid,
        city=city,
        city_name=_city_name(wd.find_city(db, city), lang),
        museum_name=mname,
        work_title=title,
        byline=" · ".join(
            x for x in (artist, (data.get("facts") or {}).get("date"), mname) if x
        ),
        image=images[0]["url"] if images else None,
        credits=[i["credit"] for i in images if i.get("credit")],
        sections=sections,
        is_trial=is_trial,
        has_audio=bool(audio),
        trial_n=len(trial_qids(db, m, lang)),
        share_url=_abs(f"/{lang}/{city}/{museum_slug}/{qid}/"),
        card=card_url(museum_slug, qid, lang),
        others=others,
        trials=set(trial_qids(db, m, lang)),
        now_tpl=_t(lang, "now_playing", part="__PART__"),
    )
