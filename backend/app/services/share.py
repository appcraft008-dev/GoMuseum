"""分享层判定的单一真相源(spec 2026-09-20-share-web-pages-design §三/§四)。

内容接口的 `share` 字段、公开网页 `/a/{slug}/{qid}`、分享图三处都走这里 ——
各判一遍的话,迟早有一处漏掉可见性闸或按错语言。

- 可见性一律按**外人**判(preview=False):链接是发给朋友的,预览账号能看到的
  隐身馆,朋友打开是 404。
- 「可分享」按**请求语言**判有无已发布 guide 正文,不看对象级 content_status
  (对象 ready 不代表这个语言有正文 —— 分享一个空页 = 负向拉新)。
- 这里没有任何音频:音频是收费核心资产,公开层一个字节都不给。
"""

from urllib.parse import urlencode

from app.core.config import settings
from app.models.content import ObjectContentSection
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.visibility import museum_visible

PLAY_URL = (
    "https://play.google.com/store/apps/details?id=com.gomuseum.app"
    "&referrer=utm_source%3Dgomuseum.app%26utm_medium%3Dshare"
)


def public_object(db, slug: str, qid: str) -> MuseumObject | None:
    """外人能看到的藏品:馆已放出 + qid 属于该馆。"""
    if not museum_visible(db, slug, preview=False):
        return None
    return (
        db.query(MuseumObject)
        .join(Museum, Museum.id == MuseumObject.museum_id)
        .filter(Museum.slug == slug, MuseumObject.qid == qid)
        .one_or_none()
    )


def guide_languages(db, obj: MuseumObject) -> list[str]:
    """该件有已发布、非空 guide 正文的语言。"""
    rows = (
        db.query(ObjectContentSection.language, ObjectContentSection.body)
        .filter(
            ObjectContentSection.object_id == obj.id,
            ObjectContentSection.section_code == "guide",
            ObjectContentSection.status == "published",
        )
        .all()
    )
    return sorted({lang for lang, body in rows if body and body.strip()})


def primary_image(db, obj: MuseumObject) -> ObjectImage | None:
    """分享图/OG 用的那张:与讲解页图集同序、同样排除隔离图,且必须有自存副本。"""
    return (
        db.query(ObjectImage)
        .filter(
            ObjectImage.object_id == obj.id,
            ObjectImage.role != "view_quarantine",
            ObjectImage.image_key.isnot(None),
        )
        .order_by(ObjectImage.sort)
        .first()
    )


def _accept_codes(accept_language: str):
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if not tag:
            continue
        if tag.startswith("zh"):
            yield (
                "zh-hant"
                if any(x in tag for x in ("hant", "-tw", "-hk", "-mo"))
                else "zh"
            )
        else:
            yield tag.split("-")[0]


def pick_language(requested: str, accept_language: str, available: list[str]) -> str:
    """请求的有 → 用它;否则浏览器语言里第一个有的;再否则 en;再否则第一个。"""
    if requested in available:
        return requested
    for code in _accept_codes(accept_language):
        if code in available:
            return code
    return "en" if "en" in available else available[0]


def page_url(slug: str, qid: str, language: str, source: str | None = None) -> str:
    q = {"lang": language, **({"s": source} if source else {})}
    return f"{settings.PUBLIC_WEB_BASE_URL}/a/{slug}/{qid}?{urlencode(q)}"


def card_url(slug: str, qid: str, language: str) -> str:
    return f"{settings.PUBLIC_WEB_BASE_URL}/a/{slug}/{qid}/card.png?lang={language}"


_TITLE_MARKS = {"zh": "《》", "zh-hant": "《》", "ko": "《》", "ja": "『』"}


def share_text(title: str, artist: str | None, language: str) -> str:
    marks = _TITLE_MARKS.get(language)
    t = f"{marks[0]}{title}{marks[1]}" if marks else title
    sep = "— " if marks else " — "  # 全角书名号自带间距,前面不再补空格
    return f"{t}{sep}{artist}" if artist else t


def share_info(db, slug: str, qid: str, language: str, content: dict) -> dict | None:
    """内容接口的 `share` 字段。content = get_object_content 的返回(标题/作者已本地化)。"""
    obj = public_object(db, slug, qid)
    if obj is None or primary_image(db, obj) is None:
        return None
    if language not in guide_languages(db, obj):
        return None
    artist = (content.get("artist") or {}).get("name")
    return {
        "url": page_url(slug, qid, language, source="app"),
        "text": share_text(content.get("title") or qid, artist, language),
        "image_url": card_url(slug, qid, language),
    }


# 网页上的固定文案(正文/分节标题来自内容本身,已本地化)。
COPY: dict[str, dict[str, str]] = {
    "zh": {
        "cta": "在博物馆现场，拍一张就能认出它",
        "audio": "这件有语音讲解，在 App 里听",
        "faq": "常见问题",
        "artist": "关于作者",
        "credits": "图片来源",
        "android_only": "目前只有 Android 版",
    },
    "zh-hant": {
        "cta": "在博物館現場，拍一張就能認出它",
        "audio": "這件有語音導覽，在 App 裡聽",
        "faq": "常見問題",
        "artist": "關於作者",
        "credits": "圖片來源",
        "android_only": "目前只有 Android 版",
    },
    "en": {
        "cta": "At the museum? Snap a photo and GoMuseum recognises it",
        "audio": "This work has an audio guide — listen in the app",
        "faq": "Questions visitors ask",
        "artist": "About the artist",
        "credits": "Image credits",
        "android_only": "Currently Android only",
    },
    "fr": {
        "cta": "Au musée, prenez-la en photo : GoMuseum la reconnaît",
        "audio": "Cette œuvre a un audioguide — à écouter dans l'app",
        "faq": "Questions fréquentes",
        "artist": "L'artiste",
        "credits": "Crédits image",
        "android_only": "Pour l'instant sur Android uniquement",
    },
    "es": {
        "cta": "En el museo, hazle una foto y GoMuseum la reconoce",
        "audio": "Esta obra tiene audioguía: escúchala en la app",
        "faq": "Preguntas frecuentes",
        "artist": "Sobre el artista",
        "credits": "Créditos de imagen",
        "android_only": "Por ahora solo en Android",
    },
    "de": {
        "cta": "Im Museum: Foto machen, GoMuseum erkennt das Werk",
        "audio": "Zu diesem Werk gibt es einen Audioguide – in der App anhören",
        "faq": "Häufige Fragen",
        "artist": "Über den Künstler",
        "credits": "Bildnachweis",
        "android_only": "Derzeit nur für Android",
    },
    "it": {
        "cta": "Al museo, scatta una foto e GoMuseum la riconosce",
        "audio": "Quest'opera ha un'audioguida: ascoltala nell'app",
        "faq": "Domande frequenti",
        "artist": "L'artista",
        "credits": "Crediti immagine",
        "android_only": "Per ora solo su Android",
    },
    "pl": {
        "cta": "W muzeum zrób zdjęcie, a GoMuseum rozpozna dzieło",
        "audio": "To dzieło ma audioprzewodnik – posłuchaj w aplikacji",
        "faq": "Częste pytania",
        "artist": "O artyście",
        "credits": "Źródła zdjęć",
        "android_only": "Na razie tylko na Androida",
    },
    "ja": {
        "cta": "美術館で写真を撮るだけで、GoMuseum が作品を認識します",
        "audio": "この作品には音声ガイドがあります（アプリで再生）",
        "faq": "よくある質問",
        "artist": "作者について",
        "credits": "画像クレジット",
        "android_only": "現在は Android 版のみ",
    },
    "ko": {
        "cta": "박물관에서 사진 한 장이면 GoMuseum이 작품을 알아봅니다",
        "audio": "이 작품에는 오디오 가이드가 있습니다 — 앱에서 들어 보세요",
        "faq": "자주 묻는 질문",
        "artist": "작가 소개",
        "credits": "이미지 출처",
        "android_only": "현재 Android 전용",
    },
}


def copy_for(language: str) -> dict[str, str]:
    return COPY.get(language, COPY["en"])
