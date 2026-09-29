# 分享功能 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 讲解页一键分享「分享图 + 链接」；链接落在只有文字、没有音频的公开网页；已装 App 的人点链接直达那件藏品。

**Architecture:** 后端新增一个判定模块 `app/services/share.py`（可见性 + 语言 + 有图），它是内容接口 `share` 字段、公开网页 `/a/{slug}/{qid}`、分享图 `/a/{slug}/{qid}/card.png` 三处的唯一真相源。App 只渲染 `share` 字段、调系统分享面板，另加 App Links 路由与登录守卫的深链接保留。分两个 PR：后端（Task 1-4）先合 staging 并上 prod，前端（Task 5-6）后发。

**Tech Stack:** FastAPI + SQLAlchemy、Pillow、stdlib `html`（沿用 `auth.py` 的 `__KEY__` 模板写法，不引 Jinja）、Flutter + go_router + Riverpod、`share_plus`。

**Spec:** `docs/superpowers/specs/2026-09-20-share-web-pages-design.md`

## Global Constraints

- **网页 / 分享图里绝不出现任何音频**：不许有 `audio_key`、音频存储域名、`/audio` 接口地址。页面只写一句「这件有语音讲解，在 App 里听」。
- **网页路由直接查 repo 层**（`get_object_content`），不调内容接口、不配服务账号令牌，不触发任何懒生成。
- **可见性**：一律 `museum_visible(db, slug, preview=False)`；预览账号也按普通人算（链接是给外人的）。
- **无已发布 guide 正文 = 不可分享**：网页 404 + `X-Robots-Tag: noindex`，`share` 字段为 null。按**请求语言**判，不按对象级 `content_status`。
- 隐身馆 / 未知 qid / 无正文 → **同一个** 404 响应（不泄漏差异）。
- `share` 字段是**加法**；Flutter 解析禁止裸 `as String`，缺字段一律 `null`。
- 新路由必须登记进 `tests/unit/api/test_visibility_routes.py` 的 `REGISTRY`，**不许** `include_in_schema=False`。
- 语言码：`de en es fr it ja ko pl zh zh-hant`（后端内容语言码；繁中是 `zh-hant`）。
- Commit 遵循 Conventional Commits；每个 commit 结尾带：
  ```
  Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01EQgJmCjbBm5Z2hmZMXmurZ
  ```
- 禁止 `git add <目录>/`，逐个文件 add；不碰未跟踪的 `docs/marketing/aso/google-play-round1/video-storyboard.md`、`tools/aso/_review/`。

## File Structure

| 文件 | 职责 |
|---|---|
| Create `backend/app/services/share.py` | 判定（公开藏品、可分享语言、主图）、URL、分享文字、语言选择、网页文案 10 语 |
| Create `backend/app/services/share_card.py` | Pillow 合成分享图（纯函数：字节进、PNG 出） |
| Create `backend/app/api/web/__init__.py`、`backend/app/api/web/share_pages.py` | `/a/{slug}/{qid}` 网页与 `card.png` 两个路由 |
| Create `backend/app/templates/share_object.html` | 网页模板 |
| Modify `backend/app/core/config.py` | `PUBLIC_WEB_BASE_URL`、`SHARE_PLAY_LIVE`、字体路径 |
| Modify `backend/app/api/v1/endpoints/museums.py:111-142` | 内容接口加 `share` 字段 |
| Modify `backend/app/main.py:93` | 挂载网页路由（无前缀） |
| Modify `backend/Dockerfile`、`.github/workflows/ci.yml` | 装 `fonts-noto-cjk` |
| Create `deployment/website/.well-known/assetlinks.json`、`deployment/production/nginx-gomuseum.app.share.conf` | App Links 验证文件；给用户手动贴的 nginx 片段 |
| Modify `docs/architecture/museum-api-contract.md` | 回写 `share` 字段 |
| Tests: `backend/tests/integration/test_share.py`、`backend/tests/unit/test_share_card.py` | |
| Modify `frontend/.../content/data/models/object_content_model.dart` | `ShareInfo` |
| Create `frontend/.../guide/presentation/share_object.dart` | 下载分享图 → 系统分享面板 |
| Modify `frontend/.../guide/presentation/pages/guide_page.dart` | 顶栏分享键 |
| Modify `frontend/.../ui/gm/gm_icon.dart` | `share` 图标 |
| Modify `frontend/.../core/router/app_router.dart`、`login_page.dart`、`register_page.dart` | `/a/:slug/:qid` 路由 + 守卫保留深链接 |
| Create `frontend/.../android/app/src/prod/AndroidManifest.xml` | App Links intent-filter（仅 prod flavor） |

`frontend/...` = `frontend/gomuseum_app/lib`（Android 文件在 `frontend/gomuseum_app/android`）。

---

## PR 1 · 后端（分支 `feature/share-backend`，从最新 staging 切）

### Task 1: 判定模块 + 内容接口 `share` 字段

**Files:**
- Create: `backend/app/services/share.py`
- Modify: `backend/app/core/config.py`（`Settings` 类内，挨着 `R2_PUBLIC_BASE_URL`）
- Modify: `backend/app/api/v1/endpoints/museums.py:139-142`
- Test: `backend/tests/integration/test_share.py`

**Interfaces:**
- Produces（Task 2/3 用）：
  - `public_object(db, slug: str, qid: str) -> MuseumObject | None`
  - `guide_languages(db, obj: MuseumObject) -> list[str]`
  - `primary_image(db, obj: MuseumObject) -> ObjectImage | None`
  - `pick_language(requested: str, accept_language: str, available: list[str]) -> str`
  - `page_url(slug, qid, language, source: str | None = None) -> str`、`card_url(slug, qid, language) -> str`
  - `share_text(title: str, artist: str | None, language: str) -> str`
  - `share_info(db, slug, qid, language, content: dict) -> dict | None`
  - `COPY: dict[str, dict[str, str]]`、`copy_for(language) -> dict[str, str]`
  - settings：`PUBLIC_WEB_BASE_URL`、`SHARE_PLAY_LIVE`、`SHARE_CARD_FONT`、`SHARE_CARD_FONT_BOLD`

- [ ] **Step 1: 写失败测试** —— `backend/tests/integration/test_share.py`

fixture 照抄 `tests/integration/test_visibility_gate.py` 的 SQLite 建表写法，另加主图和音频 key：

```python
"""分享层(spec 2026-09-20-share-web-pages-design)。

三处出口(内容接口 share 字段 / 公开网页 / 分享图)共用 app.services.share 的判定。
这里钉的是会被后人顺手改坏的几条:隐身馆对外人不可分享(预览账号也不行)、
按**请求语言**判有没有正文、网页里绝不出现音频、匿名访问不点燃生成。
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.main import app
from app.models.app_event import AppEvent
from app.models.artist import Artist
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.object_importer import upsert_museum, upsert_object

AUDIO_KEY = "object-audio/Q1/zh/guide-7f3a9c.mp3"
PREVIEW = {"Authorization": "Bearer preview"}


class _User:
    def __init__(self, uid, can_preview):
        self.id = uid
        self.can_preview = can_preview
        self.is_guest = False


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            SectionType.__table__,
            CategorySection.__table__,
            ObjectContentSection.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
            AppEvent.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    s.add(SectionType(code="guide", label_zh="讲解", label_en="Guide", default_sort=1))
    s.add(CategorySection(category="painting", section_code="guide", sort_order=1))
    # orsay 已放出:Q1 有主图+中文正文+音频;Q2 有中文正文但无图;Q3 无任何正文
    # rijks 隐身:Q9 什么都有
    for slug, qid, body, image in (
        ("orsay", "Q1", "这是一幅画。它画于 1863 年。", True),
        ("orsay", "Q2", "无图的一件。", False),
        ("orsay", "Q3", None, True),
        ("rijks", "Q9", "夜巡正文。", True),
    ):
        m = upsert_museum(s, {"slug": slug, "name_en": slug, "city_en": "X"})
        o = upsert_object(
            s,
            m.id,
            {"qid": qid, "title_en": f"T{qid}", "category": "painting", "attributes": {}},
        )
        if image:
            s.add(ObjectImage(object_id=o.id, image_key=f"images/{qid}/0", sort=0,
                              credit="Photo: Test Museum"))
        if body:
            s.add(ObjectContentSection(
                object_id=o.id, language="zh", section_code="guide", body=body,
                audio_key=AUDIO_KEY if qid == "Q1" else None,
            ))
    s.query(Museum).filter_by(slug="orsay").update({"published_at": datetime(2026, 1, 1)})
    s.commit()

    from app.services.auth_service import AuthService

    def _current(db, token):
        if token != "preview":
            raise ValueError("bad token")
        return _User("u-preview", True)

    monkeypatch.setattr(AuthService, "get_current_user", staticmethod(_current))
    monkeypatch.setattr(settings, "PUBLIC_WEB_BASE_URL", "https://gomuseum.app")
    app.dependency_overrides[get_db] = lambda: (yield s)
    yield s
    app.dependency_overrides.clear()


@pytest.fixture()
def client(db):
    return TestClient(app)


def _content(client, slug, qid, lang="zh", headers=None):
    r = client.get(
        f"/api/v1/museums/{slug}/objects/{qid}/content",
        params={"language": lang},
        headers=headers or {},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_share_field_for_shareable_object(client):
    share = _content(client, "orsay", "Q1")["share"]
    assert share == {
        "url": "https://gomuseum.app/a/orsay/Q1?lang=zh&s=app",
        "text": "《TQ1》",
        "image_url": "https://gomuseum.app/a/orsay/Q1/card.png?lang=zh",
    }


def test_share_null_when_language_has_no_guide(client):
    # 对象在 zh 有正文,en 没有 —— 按请求语言判,不按对象级状态
    assert _content(client, "orsay", "Q1", lang="en")["share"] is None


def test_share_null_without_image(client):
    assert _content(client, "orsay", "Q2")["share"] is None


def test_share_null_without_guide_text(client):
    assert _content(client, "orsay", "Q3")["share"] is None


def test_share_null_for_hidden_museum_even_for_preview_account(client):
    # 预览账号看得到隐身馆,但分享出去的链接朋友打开是 404 → 不给分享
    assert _content(client, "rijks", "Q9", headers=PREVIEW)["share"] is None


def test_pick_language():
    from app.services.share import pick_language

    assert pick_language("fr", "", ["en", "fr"]) == "fr"
    assert pick_language("de", "", ["en", "zh"]) == "en"  # 请求的没有 → en
    assert pick_language("", "zh-TW,zh;q=0.9", ["zh", "zh-hant"]) == "zh-hant"
    assert pick_language("", "zh-CN,zh;q=0.9", ["en", "zh"]) == "zh"
    assert pick_language("", "ja-JP", ["ja", "en"]) == "ja"
    assert pick_language("", "", ["zh"]) == "zh"  # 连 en 都没有 → 第一个


def test_share_text_per_language():
    from app.services.share import share_text

    assert share_text("门闩", "弗拉戈纳尔", "zh") == "《门闩》— 弗拉戈纳尔"
    assert share_text("夜警", "レンブラント", "ja") == "『夜警』— レンブラント"
    assert share_text("The Bolt", "Fragonard", "en") == "The Bolt — Fragonard"
    assert share_text("The Bolt", None, "en") == "The Bolt"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/integration/test_share.py -v`
Expected: FAIL（`KeyError: 'share'` / `ModuleNotFoundError: app.services.share`）

- [ ] **Step 3: 加配置** —— `backend/app/core/config.py`，`R2_PUBLIC_BASE_URL` 那行下面：

```python
    # 分享层(spec 2026-09-20-share-web-pages-design)。链接域名 = 公开网页所在站点;
    # staging 设成 https://staging-api.gomuseum.app(它的 nginx 把 / 整个反代到后端)。
    PUBLIC_WEB_BASE_URL: str = "https://gomuseum.app"
    # 推正式轨道那天改 true:网页粘底条才变成 Play 下载按钮(内测轨道的链接对外人是"找不到该应用")
    SHARE_PLAY_LIVE: bool = False
    # 分享图字体(镜像装 fonts-noto-cjk;标题有中日韩文,没字体就是一排方框)
    SHARE_CARD_FONT: str = "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"
    SHARE_CARD_FONT_BOLD: str = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
```

- [ ] **Step 4: 写 `backend/app/services/share.py`**

```python
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
            yield "zh-hant" if any(
                x in tag for x in ("hant", "-tw", "-hk", "-mo")
            ) else "zh"
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
    return f"{t} — {artist}" if artist else t


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
    "zh": {"cta": "在博物馆现场，拍一张就能认出它", "audio": "这件有语音讲解，在 App 里听",
           "faq": "常见问题", "artist": "关于作者", "credits": "图片来源",
           "android_only": "目前只有 Android 版"},
    "zh-hant": {"cta": "在博物館現場，拍一張就能認出它", "audio": "這件有語音導覽，在 App 裡聽",
                "faq": "常見問題", "artist": "關於作者", "credits": "圖片來源",
                "android_only": "目前只有 Android 版"},
    "en": {"cta": "At the museum? Snap a photo and GoMuseum recognises it",
           "audio": "This work has an audio guide — listen in the app",
           "faq": "Questions visitors ask", "artist": "About the artist",
           "credits": "Image credits", "android_only": "Currently Android only"},
    "fr": {"cta": "Au musée, prenez-la en photo : GoMuseum la reconnaît",
           "audio": "Cette œuvre a un audioguide — à écouter dans l'app",
           "faq": "Questions fréquentes", "artist": "L'artiste",
           "credits": "Crédits image", "android_only": "Pour l'instant sur Android uniquement"},
    "es": {"cta": "En el museo, hazle una foto y GoMuseum la reconoce",
           "audio": "Esta obra tiene audioguía: escúchala en la app",
           "faq": "Preguntas frecuentes", "artist": "Sobre el artista",
           "credits": "Créditos de imagen", "android_only": "Por ahora solo en Android"},
    "de": {"cta": "Im Museum: Foto machen, GoMuseum erkennt das Werk",
           "audio": "Zu diesem Werk gibt es einen Audioguide – in der App anhören",
           "faq": "Häufige Fragen", "artist": "Über den Künstler",
           "credits": "Bildnachweis", "android_only": "Derzeit nur für Android"},
    "it": {"cta": "Al museo, scatta una foto e GoMuseum la riconosce",
           "audio": "Quest'opera ha un'audioguida: ascoltala nell'app",
           "faq": "Domande frequenti", "artist": "L'artista",
           "credits": "Crediti immagine", "android_only": "Per ora solo su Android"},
    "pl": {"cta": "W muzeum zrób zdjęcie, a GoMuseum rozpozna dzieło",
           "audio": "To dzieło ma audioprzewodnik – posłuchaj w aplikacji",
           "faq": "Częste pytania", "artist": "O artyście",
           "credits": "Źródła zdjęć", "android_only": "Na razie tylko na Androida"},
    "ja": {"cta": "美術館で写真を撮るだけで、GoMuseum が作品を認識します",
           "audio": "この作品には音声ガイドがあります（アプリで再生）",
           "faq": "よくある質問", "artist": "作者について",
           "credits": "画像クレジット", "android_only": "現在は Android 版のみ"},
    "ko": {"cta": "박물관에서 사진 한 장이면 GoMuseum이 작품을 알아봅니다",
           "audio": "이 작품에는 오디오 가이드가 있습니다 — 앱에서 들어 보세요",
           "faq": "자주 묻는 질문", "artist": "작가 소개",
           "credits": "이미지 출처", "android_only": "현재 Android 전용"},
}


def copy_for(language: str) -> dict[str, str]:
    return COPY.get(language, COPY["en"])
```

（black 会重排 `COPY` 的换行，照 black 的结果提交即可。）

- [ ] **Step 5: 内容接口挂 `share`** —— `backend/app/api/v1/endpoints/museums.py` 的 `object_content` 末尾，把

```python
    data = get_object_content(db, slug, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    return data
```

改为

```python
    data = get_object_content(db, slug, qid, language)
    if data is None:
        raise HTTPException(status_code=404, detail=f"object not found: {qid}")
    # 加法字段(2026-09-29 分享):null = 这件在这个语言下不可分享,App 不显示分享键
    data["share"] = share_info(db, slug, qid, language, data)
    return data
```

并在文件顶部 import 区加 `from app.services.share import share_info`。

- [ ] **Step 6: 跑测试确认通过**

Run: `cd backend && pytest tests/integration/test_share.py tests/integration/test_visibility_gate.py -v`
Expected: 全 PASS

- [ ] **Step 7: 破坏验证（先提交再破坏）**

```bash
git add backend/app/services/share.py backend/app/core/config.py backend/app/api/v1/endpoints/museums.py backend/tests/integration/test_share.py
git commit -m "feat(share): 内容接口下发 share 字段——可见性按外人判、按请求语言判有无正文"
```
然后把 `public_object` 里的 `preview=False` 改成 `preview=True`，跑 `pytest tests/integration/test_share.py -v`，
Expected: `test_share_null_for_hidden_museum_even_for_preview_account` FAIL。
再把 `share_info` 里 `if language not in guide_languages(...)` 两行删掉，Expected: `test_share_null_when_language_has_no_guide` FAIL。
每次破坏后 `git checkout -- backend/app/services/share.py` 还原。

---

### Task 2: 公开网页 `/a/{slug}/{qid}`

**Files:**
- Create: `backend/app/api/web/__init__.py`（空文件）
- Create: `backend/app/api/web/share_pages.py`
- Create: `backend/app/templates/share_object.html`
- Modify: `backend/app/main.py:93`
- Modify: `backend/app/models/app_event.py`（`EVENTS` 白名单）
- Modify: `backend/tests/unit/api/test_visibility_routes.py`（`REGISTRY`）
- Test: `backend/tests/integration/test_share.py`（追加）

**Interfaces:**
- Consumes: Task 1 的 `public_object`、`guide_languages`、`primary_image`、`pick_language`、`copy_for`、`card_url`、`PLAY_URL`；`app.services.museum_repo.get_object_content`、`museum_name`；`app.services.event_log.log_event`
- Produces: `router`（`APIRouter`），`_not_found() -> HTMLResponse`（Task 3 复用）

- [ ] **Step 1: 追加失败测试** —— `backend/tests/integration/test_share.py` 末尾

```python
ANDROID = {"User-Agent": "Mozilla/5.0 (Linux; Android 14; Pixel 8) Chrome/129 Mobile"}
WECHAT = {"User-Agent": ANDROID["User-Agent"] + " MicroMessenger/8.0.50"}


def test_page_renders_text(client):
    r = client.get("/a/orsay/Q1?lang=zh&s=app")
    assert r.status_code == 200
    assert "TQ1" in r.text and "这是一幅画。" in r.text
    assert 'property="og:image"' in r.text
    assert "这件有语音讲解，在 App 里听" in r.text  # Q1 guide 有音频 → 只写一句


def test_page_never_contains_audio(client):
    html = client.get("/a/orsay/Q1?lang=zh").text
    for leak in (AUDIO_KEY, "object-audio", "/audio", ".mp3", "<audio"):
        assert leak not in html, f"网页里出现了音频痕迹: {leak}"


def test_page_404_is_identical_for_hidden_unknown_and_empty(client):
    hidden = client.get("/a/rijks/Q9?lang=zh")
    unknown = client.get("/a/orsay/Q404?lang=zh")
    empty = client.get("/a/orsay/Q3?lang=zh")
    wrong_museum = client.get("/a/rijks/Q1?lang=zh")
    for r in (hidden, unknown, empty, wrong_museum):
        assert r.status_code == 404
        assert r.headers["x-robots-tag"] == "noindex"
        assert r.text == unknown.text


def test_page_redirects_language_without_text(client):
    r = client.get("/a/orsay/Q1?lang=en&s=app", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/a/orsay/Q1?lang=zh&s=app"


def test_page_never_triggers_generation(client, monkeypatch):
    import app.services.enrichment.lazy as lazy

    def boom(*a, **kw):
        raise AssertionError("公开网页点燃了懒生成")

    monkeypatch.setattr(lazy, "maybe_trigger", boom)
    assert client.get("/a/orsay/Q1?lang=zh").status_code == 200


def test_cta_has_no_play_link_before_launch(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", False)
    assert "play.google.com" not in client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text


def test_cta_links_play_after_launch_but_not_in_wechat(client, monkeypatch):
    monkeypatch.setattr(settings, "SHARE_PLAY_LIVE", True)
    assert "play.google.com" in client.get("/a/orsay/Q1?lang=zh", headers=ANDROID).text
    assert "play.google.com" not in client.get("/a/orsay/Q1?lang=zh", headers=WECHAT).text


def test_page_view_logged_with_source(client, db):
    client.get("/a/orsay/Q1?lang=zh&s=app")
    ev = db.query(AppEvent).filter_by(name="share_page_view").one()
    assert ev.props["source"] == "app"
```

（`AppEvent` 的属性列名以 `app/models/app_event.py` 为准；若不叫 `props`，改成实际列名。）

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/integration/test_share.py -v -k "page or cta"`
Expected: FAIL（404 —— 路由不存在）

- [ ] **Step 3: 模板** —— `backend/app/templates/share_object.html`

```html
<!DOCTYPE html>
<html lang="__HTMLLANG__">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>__TITLE__ · GoMuseum</title>
<meta name="description" content="__OGDESC__" />
<link rel="canonical" href="__CANONICAL__" />
__HREFLANG__
<meta property="og:type" content="article" />
<meta property="og:title" content="__OGTITLE__" />
<meta property="og:description" content="__OGDESC__" />
<meta property="og:image" content="__OGIMAGE__" />
<meta property="og:url" content="__CANONICAL__" />
<meta name="twitter:card" content="summary_large_image" />
<style>
  :root { --bg:#F3EDDF; --card:#FBF7EC; --ink:#2C2316; --sub:#8A7A5F; --line:#DCD2B8; --accent:#9A4A2E; }
  @media (prefers-color-scheme: dark) {
    :root { --bg:#1C1812; --card:#241F17; --ink:#EDE4D0; --sub:#A89878; --line:#3A3226; --accent:#D98A63; }
  }
  * { box-sizing:border-box; margin:0; }
  body { background:var(--bg); color:var(--ink); font-family:-apple-system,'Noto Sans','PingFang SC','Noto Sans CJK SC',sans-serif; line-height:1.75; padding-bottom:88px; }
  main { max-width:680px; margin:0 auto; padding:0 16px; }
  .hero { width:100%; max-height:70vh; object-fit:contain; background:var(--card); display:block; margin:0 auto; }
  h1 { font-family:Georgia,'Noto Serif SC','Songti SC',serif; font-size:26px; line-height:1.3; margin-top:20px; text-wrap:balance; }
  .byline { color:var(--sub); margin-top:6px; }
  .audio { margin-top:14px; padding:10px 14px; border:1px solid var(--line); border-radius:10px; background:var(--card); font-size:14px; }
  section { margin-top:28px; }
  h2 { font-size:17px; margin-bottom:8px; }
  p { margin-top:10px; white-space:pre-line; }
  details { border-top:1px solid var(--line); padding:10px 0; }
  summary { cursor:pointer; font-weight:600; }
  .credits { margin-top:36px; font-size:12px; color:var(--sub); }
  .cta { position:fixed; left:0; right:0; bottom:0; display:block; padding:16px; text-align:center; background:var(--ink); color:var(--bg); text-decoration:none; font-weight:600; }
  .cta small { display:block; font-weight:400; opacity:.75; }
  a.cta:focus-visible { outline:3px solid var(--accent); outline-offset:-3px; }
</style>
</head>
<body>
<main>
  __HERO__
  <h1>__TITLE__</h1>
  <div class="byline">__BYLINE__</div>
  __AUDIO__
  __BODY__
  <div class="credits">__CREDITS__</div>
</main>
__CTA__
</body>
</html>
```

- [ ] **Step 4: 路由** —— `backend/app/api/web/share_pages.py`

```python
"""公开网页层(spec 2026-09-20-share-web-pages-design §四/§五)。

⚠️ 这里只读 repo 层,**不调内容接口、不带任何身份**:懒生成闸按"有无身份"判,
给这里配一个服务账号令牌 = 把 2026-09-20 关掉的匿名成本洞原样打开。
⚠️ 这里没有音频,一个字节都没有(音频是收费核心资产)。
"""

import html as _html
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.services.event_log import log_event
from app.services.museum_repo import get_object_content
from app.services.share import (
    PLAY_URL,
    card_url,
    copy_for,
    guide_languages,
    pick_language,
    public_object,
)

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
    return HTMLResponse(_NOT_FOUND, status_code=404, headers={"X-Robots-Tag": "noindex"})


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
        return RedirectResponse(f"/a/{slug}/{qid}?lang={chosen}{suffix}", status_code=302)

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
        body += f"<section><h2>{e(copy['faq'])}</h2>" + "".join(
            f"<details><summary>{e(q['question'])}</summary>{_paras(q.get('answer') or '')}</details>"
            for q in qs
        ) + "</section>"
    if artist.get("bio"):
        body += f"<section><h2>{e(copy['artist'])}</h2>{_paras(artist['bio'])}</section>"

    credits = [i["credit"] for i in images if i.get("credit")]
    base = settings.PUBLIC_WEB_BASE_URL
    hreflang = "\n".join(
        f'<link rel="alternate" hreflang="{l}" href="{e(f"{base}/a/{slug}/{qid}?lang={l}")}" />'
        for l in langs
    )
    desc = (guide.get("body") or "").replace("\n", " ")[:120]

    log_event(db, "share_page_view", museum_slug=slug, qid=qid, lang=chosen, source=s or "direct")
    db.commit()

    return HTMLResponse(
        _render(
            {
                "HTMLLANG": chosen,
                "TITLE": title,
                "OGTITLE": f"{title} — {artist['name']}" if artist.get("name") else title,
                "OGDESC": desc,
                "OGIMAGE": images[0]["url"] if images else card_url(slug, qid, chosen),
                "CANONICAL": f"{base}/a/{slug}/{qid}?lang={chosen}",
                "BYLINE": " · ".join(x for x in (artist.get("name"), facts.get("date")) if x),
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
```

- [ ] **Step 4b: 事件白名单** —— `backend/app/models/app_event.py` 的 `EVENTS` 元组末尾（`"guest_created",` 之后）加：

```python
    # 分享落地页被看(props.source=app 是 App 分享来的,direct 是其余)。
    # 回答的问题:分享这条获客渠道有没有人进来 —— ≥100 真实活跃用户前别看(spec §八)。
    # 分享次数 ≈ card.png 的 nginx 访问量,不另设事件。
    "share_page_view",
```

并把该元组上方注释里的「14 个核心事件」改成「15 个核心事件」。

- [ ] **Step 5: 挂载** —— `backend/app/main.py`，`app.include_router(api_router, prefix="/api/v1")` 下一行：

```python
# 公开网页层(分享落地页)不带 /api/v1 前缀:链接是 gomuseum.app/a/{slug}/{qid}
from app.api.web.share_pages import router as share_web_router  # noqa: E402

app.include_router(share_web_router)
```

- [ ] **Step 6: 登记可见性闸** —— `tests/unit/api/test_visibility_routes.py` 的 `REGISTRY` 里加：

```python
    ("GET", "/a/{slug}/{qid}"): GATED,  # 公开网页:public_object 按外人判
```

- [ ] **Step 7: 跑测试**

Run: `cd backend && pytest tests/integration/test_share.py tests/unit/api/test_visibility_routes.py -v`
Expected: 全 PASS

- [ ] **Step 8: 提交 + 破坏验证**

```bash
git add backend/app/api/web/__init__.py backend/app/api/web/share_pages.py backend/app/templates/share_object.html backend/app/main.py backend/app/models/app_event.py backend/tests/unit/api/test_visibility_routes.py backend/tests/integration/test_share.py
git commit -m "feat(share): 公开网页 /a/{slug}/{qid}——只有文字、按语言跳转、隐身与不存在同一个 404"
```
破坏 ①（模拟"后人顺手把内容接口换成带直链的版本"）：临时在 `museum_repo.get_object_content` 的 `default_guide` 字典里加 `"audio_key": guide_row.audio_key`，并把 `share_page` 里 `"BODY": body` 改成 `"BODY": body + e(str(guide))`，
Expected: `test_page_never_contains_audio` FAIL。
破坏 ②：`_not_found()` 的 `headers=` 去掉，Expected: `test_page_404_is_identical_for_hidden_unknown_and_empty` FAIL。
每次 `git checkout -- backend/app/services/museum_repo.py backend/app/api/web/share_pages.py` 还原。

---

### Task 3: 分享图 `card.png` + 字体

**Files:**
- Create: `backend/app/services/share_card.py`
- Modify: `backend/app/api/web/share_pages.py`（加路由）
- Modify: `backend/Dockerfile:36-38`（runtime 阶段 apt 包）
- Modify: `.github/workflows/ci.yml`（backend-tests job 装字体）
- Modify: `backend/tests/unit/api/test_visibility_routes.py`（`REGISTRY`）
- Test: `backend/tests/unit/test_share_card.py`、`backend/tests/integration/test_share.py`（追加）

**Interfaces:**
- Consumes: Task 1 `public_object`、`guide_languages`、`primary_image`、`pick_language`；Task 2 `_not_found`；`museum_repo.museum_name(museum, language) -> str`；`get_object_storage().get(key) -> bytes | None`
- Produces: `render_card(image: bytes, title: str, byline: str, excerpt: str, footer: str, credit: str | None, language: str) -> bytes`（PNG）、`first_sentence(text: str, limit: int = 80) -> str`

- [ ] **Step 1: 失败测试** —— `backend/tests/unit/test_share_card.py`

```python
"""分享图:中日韩/波兰语不能出方框,输出是 PNG,文字过长不越界崩溃。

本地 macOS 没装 Noto CJK 时跳过;CI 与 prod 镜像都装 fonts-noto-cjk,
CI 上字体缺失直接判红 —— 否则这组测试会在"哪里都没跑过"的状态下一直绿。
"""

import io
import os
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings

HAS_FONT = Path(settings.SHARE_CARD_FONT).exists()


def test_font_present_in_ci():
    if os.getenv("CI"):
        assert HAS_FONT, f"CI 缺字体 {settings.SHARE_CARD_FONT}:ci.yml 没装 fonts-noto-cjk"


needs_font = pytest.mark.skipif(not HAS_FONT, reason="本机无 Noto CJK")


def _jpeg(w=800, h=600):
    buf = io.BytesIO()
    Image.new("RGB", (w, h), (120, 90, 60)).save(buf, "JPEG")
    return buf.getvalue()


@needs_font
@pytest.mark.parametrize(
    "lang,sample",
    [("zh", "门闩弗拉戈纳尔"), ("zh-hant", "門閂導覽"), ("ja", "夜警レンブラント"),
     ("ko", "야경 렘브란트"), ("pl", "łąśćżźń"), ("fr", "œuvre à côté")],
)
def test_glyphs_exist(lang, sample):
    from app.services.share_card import _font

    f = _font(lang, 40)
    tofu = bytes(f.getmask("\U000F0000"))  # 私用区,必然走 .notdef
    for ch in sample:
        assert bytes(f.getmask(ch)) != tofu, f"{lang} 字体缺字形: {ch!r}"


@needs_font
def test_render_card_png_and_long_text():
    from app.services.share_card import render_card

    png = render_card(
        _jpeg(600, 1400),  # 竖长图要被限高
        title="很长的标题" * 20,
        byline="作者 · 1777",
        excerpt="一句很长的摘要" * 30,
        footer="卢浮宫 · GoMuseum",
        credit="Photo: RMN",
        language="zh",
    )
    img = Image.open(io.BytesIO(png))
    assert img.format == "PNG"
    assert img.width == 1080 and img.height <= 1600


def test_first_sentence():
    from app.services.share_card import first_sentence

    assert first_sentence("这是一幅画。它画于 1863 年。") == "这是一幅画。"
    assert first_sentence("One. Two.") == "One."
    assert first_sentence("没有句号" * 50, limit=10) == "没有句号没有句号没有…"
```

追加到 `backend/tests/integration/test_share.py`：

```python
def test_card_404_matches_page_rules(client):
    for path in ("/a/rijks/Q9/card.png?lang=zh", "/a/orsay/Q3/card.png?lang=zh",
                 "/a/orsay/Q2/card.png?lang=zh"):  # 隐身 / 无正文 / 无图
        assert client.get(path).status_code == 404, path


def test_card_renders_png(client, monkeypatch):
    import app.api.web.share_pages as sp

    monkeypatch.setattr(sp, "render_card", lambda image, **kw: b"\x89PNG-fake")

    class _Storage:
        def get(self, key):
            assert key == "images/Q1/0_large.jpg"
            return b"jpeg-bytes"

    monkeypatch.setattr(sp, "get_object_storage", lambda: _Storage())
    r = client.get("/a/orsay/Q1/card.png?lang=zh")
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/png"
    assert "max-age" in r.headers["cache-control"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd backend && pytest tests/unit/test_share_card.py tests/integration/test_share.py -v -k "card or first_sentence or glyph"`
Expected: FAIL（模块不存在 / 路由 404 断言 200 失败）

- [ ] **Step 3: `backend/app/services/share_card.py`**

```python
"""分享图(spec §五)。服务端合成,版式以后改不用发 App。

字体:Noto Sans CJK 的 .ttc 里按语言挑字面(JP/KR/SC/TC 字形不同),拉丁/波兰字母它也全覆盖。
# ponytail: 每次请求现场合成;可分享集合有上限(有正文件数 × 语言),CPU 成问题再落 R2
"""

import io
import re
from functools import lru_cache

from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings

W = 1080
PAD = 64
MAX_IMG_H = 1000
BG = (251, 247, 236)
INK = (44, 35, 22)
SUB = (138, 122, 95)
LINE = (220, 210, 184)
_FACE = {"ja": "JP", "ko": "KR", "zh-hant": "TC"}  # 其余一律 SC


@lru_cache(maxsize=32)
def _font(language: str, size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = settings.SHARE_CARD_FONT_BOLD if bold else settings.SHARE_CARD_FONT
    want = f"Noto Sans CJK {_FACE.get(language, 'SC')}"
    for i in range(12):
        try:
            f = ImageFont.truetype(path, size, index=i)
        except OSError:
            break
        if f.getname()[0] == want:
            return f
    return ImageFont.truetype(path, size)


def first_sentence(text: str, limit: int = 80) -> str:
    s = re.split(r"(?<=[。！？.!?])\s*", text.strip(), maxsplit=1)[0]
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _wrap(draw, text: str, font, width: int, max_lines: int) -> list[str]:
    # 有空格按词断(拉丁),否则按字断(中日韩)。
    # ponytail: 单个超长拉丁词不再拆,会略微出界;真遇到再按字符硬断
    sep = " " if " " in text else ""
    tokens = text.split(" ") if sep else list(text)
    lines, cur = [], ""
    for t in tokens:
        trial = f"{cur}{sep}{t}" if cur else t
        if cur and draw.textlength(trial, font=font) > width:
            lines.append(cur)
            cur = t
        else:
            cur = trial
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip()[:-1] + "…"
    return lines


def render_card(
    image: bytes,
    *,
    title: str,
    byline: str,
    excerpt: str,
    footer: str,
    credit: str | None,
    language: str,
) -> bytes:
    art = Image.open(io.BytesIO(image)).convert("RGB")
    art.thumbnail((W, MAX_IMG_H))
    probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    f_title, f_body, f_small = _font(language, 52, True), _font(language, 34), _font(language, 26)
    text_w = W - 2 * PAD
    blocks = [
        (_wrap(probe, title, f_title, text_w, 2), f_title, INK, 66),
        (_wrap(probe, byline, f_body, text_w, 1), f_body, SUB, 48),
        (_wrap(probe, f"“{excerpt}”", f_body, text_w, 3), f_body, INK, 50),
    ]
    text_h = sum(len(ls) * lh for ls, _, _, lh in blocks) + 3 * 20
    foot = [footer] + ([credit] if credit else [])
    h = art.height + PAD + text_h + 40 + len(foot) * 38 + PAD
    card = Image.new("RGB", (W, h), BG)
    card.paste(art, ((W - art.width) // 2, 0))
    d = ImageDraw.Draw(card)
    y = art.height + PAD
    for lines, font, color, lh in blocks:
        for line in lines:
            d.text((PAD, y), line, font=font, fill=color)
            y += lh
        y += 20
    d.line((PAD, y, W - PAD, y), fill=LINE, width=2)
    y += 20
    for line in foot:
        d.text((PAD, y), line[:80], font=f_small, fill=SUB)
        y += 38
    buf = io.BytesIO()
    card.save(buf, "PNG", optimize=True)
    return buf.getvalue()
```

- [ ] **Step 4: 路由** —— `backend/app/api/web/share_pages.py` 追加（顶部 import 补 `from fastapi.responses import Response`、`from app.models.museum import Museum`、`from app.services.museum_repo import museum_name`、`from app.services.share import primary_image`、`from app.services.share_card import first_sentence, render_card`、`from app.services.storage import get_object_storage`）：

```python
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
    raw = get_object_storage().get(f"{img.image_key}_large.jpg")
    data = get_object_content(db, slug, qid, chosen)
    if raw is None or data is None:
        return _not_found()
    artist = (data.get("artist") or {}).get("name")
    date = (data.get("facts") or {}).get("date")
    museum = db.query(Museum).filter_by(slug=slug).one()
    png = render_card(
        raw,
        title=data.get("title") or qid,
        byline=" · ".join(x for x in (artist, date) if x),
        excerpt=first_sentence((data.get("default_guide") or {}).get("body") or ""),
        footer=f"{museum_name(museum, chosen)} · GoMuseum",
        credit=img.credit,
        language=chosen,
    )
    return Response(
        png, media_type="image/png", headers={"Cache-Control": "public, max-age=86400"}
    )
```

`REGISTRY` 加：`("GET", "/a/{slug}/{qid}/card.png"): GATED,  # 分享图:同网页判定`

- [ ] **Step 5: 字体进镜像与 CI**

`backend/Dockerfile` runtime 阶段：

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*
```

`.github/workflows/ci.yml`，backend-tests job 的 `Install backend dependencies (from poetry.lock)` 步骤**之前**插入：

```yaml
      # 分享图要中日韩字体(与 prod 镜像同一个 apt 包);缺了 test_font_present_in_ci 判红
      - name: Install CJK fonts (share card)
        run: sudo apt-get update && sudo apt-get install -y --no-install-recommends fonts-noto-cjk
```

- [ ] **Step 6: 跑测试**

Run: `cd backend && pytest tests/unit/test_share_card.py tests/integration/test_share.py tests/unit/api/test_visibility_routes.py -v`
Expected: PASS（本机无字体时 glyph/render 两条 SKIP，其余 PASS）

本机肉眼看一张：如果 macOS 上 `brew install --cask font-noto-sans-cjk` 装不了，就在 Linux 容器里跑：
```bash
cd backend && docker build --target runtime -t gm-share-test . && \
docker run --rm -v "$PWD":/app -w /app gm-share-test python -c "
import io; from PIL import Image
from app.services.share_card import render_card
b=io.BytesIO(); Image.new('RGB',(800,600),(120,90,60)).save(b,'JPEG')
open('/app/card_sample.png','wb').write(render_card(b.getvalue(),title='门闩',byline='弗拉戈纳尔 · 1777',excerpt='这幅小画在 1777 年完成。',footer='卢浮宫 · GoMuseum',credit='Photo: RMN',language='zh'))"
```
读 `backend/card_sample.png` 看版式，**看完删掉，不提交**。

- [ ] **Step 7: 提交**

```bash
git add backend/app/services/share_card.py backend/app/api/web/share_pages.py backend/Dockerfile .github/workflows/ci.yml backend/tests/unit/test_share_card.py backend/tests/integration/test_share.py backend/tests/unit/api/test_visibility_routes.py
git commit -m "feat(share): 服务端合成分享图——镜像装 Noto CJK,判定与网页同一组函数"
```

---

### Task 4: App Links 验证文件、nginx 片段、契约回写 → PR 1

**Files:**
- Create: `deployment/website/.well-known/assetlinks.json`
- Create: `deployment/production/nginx-gomuseum.app.share.conf`
- Modify: `docs/architecture/museum-api-contract.md`（`default_guide` 说明那段之后）

- [ ] **Step 1: 取上传密钥指纹**（不需要密码：V41 AAB 就是上传密钥签的）

Run: `keytool -printcert -jarfile ~/Desktop/gomuseum-v41.aab | grep SHA256:`
Expected: 一行 `SHA256: AB:CD:...`

- [ ] **Step 2: `deployment/website/.well-known/assetlinks.json`**（把上一步的值填进第二项；第一项在发 App 前由用户从 Play Console「应用完整性 → 应用签名密钥证书」提供后替换）

```json
[
  {
    "relation": ["delegate_permission/common.handle_all_urls"],
    "target": {
      "namespace": "android_app",
      "package_name": "com.gomuseum.app",
      "sha256_cert_fingerprints": [
        "PLAY_APP_SIGNING_SHA256_FROM_CONSOLE",
        "<Step 1 的上传密钥 SHA256>"
      ]
    }
  }
]
```

`PLAY_APP_SIGNING_SHA256_FROM_CONSOLE` 是**有意保留的待填值**（只有用户能从 Console 拿到）；发 App 前的上线清单第 2 步会替换它。

- [ ] **Step 3: `deployment/production/nginx-gomuseum.app.share.conf`**

```nginx
# 分享层要贴进宿主机 /etc/nginx/sites-available/gomuseum.app 的片段(CD 带不过去,用户手动)。
# ① limit_req_zone 放在 server {} 之外(文件顶部);② 两个 location 放进 443 的 server {} 里。
# 改完:nginx -t && systemctl reload nginx
# 验证:curl -sI https://gomuseum.app/a/<slug>/<qid> | head -1 → 200/404(不是 nginx 的 404 页)
#       curl -s https://gomuseum.app/.well-known/assetlinks.json | python3 -m json.tool

limit_req_zone $binary_remote_addr zone=gomuseum_web:10m rate=5r/s;

location /a/ {
    limit_req zone=gomuseum_web burst=20 nodelay;
    limit_req_status 429;
    proxy_pass http://127.0.0.1:8100;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}

location = /.well-known/assetlinks.json {
    default_type application/json;
    alias /opt/gomuseum/website/.well-known/assetlinks.json;
}
```

- [ ] **Step 4: 契约回写** —— `docs/architecture/museum-api-contract.md` 的 `default_guide` 条目之后加一条：

```markdown
- `share`(加法字段,2026-09-29):`{url, text, image_url}` 或 `null`。null = 这件在**请求语言**下不可分享
  (该语言无已发布 guide 正文 / 所在馆未放出 —— **预览账号也是 null** / 无自存主图),App 据此不显示分享键。
  `url` 落在公开网页 `/a/{slug}/{qid}`(只有文字,**没有任何音频**),`image_url` 是服务端合成的分享图。
  判定唯一真相源 `app/services/share.py`,网页 / 分享图 / 本字段共用。
```

- [ ] **Step 5: 全量后端测试 + 格式**

Run: `cd backend && black app tests && isort app tests && pytest -q`
Expected: 全 PASS（fileno 那条已知基线 flake 例外，单独重跑确认）

- [ ] **Step 6: 提交、推送、开 PR**

```bash
git add deployment/website/.well-known/assetlinks.json deployment/production/nginx-gomuseum.app.share.conf docs/architecture/museum-api-contract.md
git commit -m "chore(share): App Links 验证文件 + gomuseum.app 的 nginx 片段 + 契约回写 share 字段"
git push -u origin feature/share-backend
gh pr create --base staging --title "feat(share): 分享后端——share 字段、公开文字网页、分享图" --body "..."
```
等 `gh pr checks` 非 pass 项为 0 → `gh pr merge --squash --delete-branch`。

- [ ] **Step 7: staging 实测**（合并后 CD 自动部署 staging）

先在 staging 服务器的 env 里设 `PUBLIC_WEB_BASE_URL=https://staging-api.gomuseum.app` 并重启 staging 后端（staging 配置，非 prod）。然后：
```bash
curl -s "https://staging-api.gomuseum.app/api/v1/museums/louvre/objects/<有正文的qid>/content?language=zh" | python3 -c "import sys,json;print(json.load(sys.stdin)['share'])"
curl -s -o /dev/null -w "%{http_code}\n" "https://staging-api.gomuseum.app/a/louvre/<qid>?lang=zh"   # 200
curl -s "https://staging-api.gomuseum.app/a/louvre/<qid>?lang=zh" | grep -c -E "mp3|audio_key|object-audio"  # 0
curl -s -o /tmp/card.png "https://staging-api.gomuseum.app/a/louvre/<qid>/card.png?lang=zh" && file /tmp/card.png
curl -s -o /dev/null -w "%{http_code}\n" "https://staging-api.gomuseum.app/a/rijksmuseum/Q219831?lang=zh"  # 404(隐身)
```
读 `/tmp/card.png` 看中文与日文各一张（`lang=ja` 需挑有日文正文的件）。

---

## PR 2 · 前端（分支 `feature/share-app`，**PR 1 合 staging 后**从最新 staging 切）

### Task 5: `ShareInfo` + 讲解页分享键

**Files:**
- Modify: `frontend/gomuseum_app/pubspec.yaml`（`flutter pub add share_plus`）
- Modify: `frontend/gomuseum_app/lib/features/content/data/models/object_content_model.dart`
- Create: `frontend/gomuseum_app/lib/features/guide/presentation/share_object.dart`
- Modify: `frontend/gomuseum_app/lib/ui/gm/gm_icon.dart`
- Modify: `frontend/gomuseum_app/lib/features/guide/presentation/pages/guide_page.dart:325-337, 779-842`
- Modify: `frontend/gomuseum_app/lib/l10n/app_*.arb`（10 个）+ `flutter gen-l10n`
- Test: `frontend/gomuseum_app/test/features/guide/guide_share_test.dart`、`test/features/guide/guide_hero_actions_test.dart`

**Interfaces:**
- Produces:
  - `class ShareInfo { final String url, text, imageUrl; static ShareInfo? fromJson(Object? j); }`
  - `ObjectContent.share`（`ShareInfo?`）
  - `Future<void> shareObject(ShareInfo s, {Future<Uint8List?> Function(String url)? fetch, Future<void> Function(ShareParams p)? send})`
  - `GmIcons.share`
  - l10n key `guideShare`

- [ ] **Step 1: 加依赖**

Run: `cd frontend/gomuseum_app && flutter pub add share_plus`
（记下装到的版本；下面用的是 share_plus ≥11 的 `SharePlus.instance.share(ShareParams(...))` API，若装到的版本 API 不同，以该版本 README 为准改写 `_send`。）

- [ ] **Step 2: 失败测试** —— `test/features/guide/guide_share_test.dart`

```dart
// 分享键(spec 2026-09-20-share-web-pages-design §六)。
// 钉三件事:share 为 null 时根本没有分享键(空页不分享)、解析容错(不裸 as String)、
// 分享图下载失败时退化为只发文字+链接,而不是报错打断。
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';
import 'package:gomuseum_app/features/guide/presentation/share_object.dart';
import 'package:share_plus/share_plus.dart';

void main() {
  group('ShareInfo.fromJson 容错', () {
    test('完整字段', () {
      final s = ShareInfo.fromJson({
        'url': 'https://gomuseum.app/a/louvre/Q1?lang=zh&s=app',
        'text': '《门闩》— 弗拉戈纳尔',
        'image_url': 'https://gomuseum.app/a/louvre/Q1/card.png?lang=zh',
      })!;
      expect(s.text, '《门闩》— 弗拉戈纳尔');
    });
    test('null / 非 Map / 缺 url → null(老后端没有这个字段)', () {
      expect(ShareInfo.fromJson(null), isNull);
      expect(ShareInfo.fromJson('x'), isNull);
      expect(ShareInfo.fromJson({'text': 't'}), isNull);
      expect(ShareInfo.fromJson({'url': 42}), isNull);
    });
    test('ObjectContent 缺 share 字段 → null', () {
      final c = ObjectContent.fromJson({'qid': 'Q1'});
      expect(c.share, isNull);
    });
  });

  group('shareObject', () {
    const info = ShareInfo(
      url: 'https://gomuseum.app/a/louvre/Q1?lang=zh&s=app',
      text: '《门闩》— 弗拉戈纳尔',
      imageUrl: 'https://gomuseum.app/a/louvre/Q1/card.png?lang=zh',
    );

    test('图下载成功 → 图 + 文字 + 链接', () async {
      ShareParams? sent;
      await shareObject(info,
          fetch: (_) async => Uint8List.fromList([1, 2, 3]),
          send: (p) async => sent = p);
      expect(sent!.files, hasLength(1));
      expect(sent!.text, '《门闩》— 弗拉戈纳尔\nhttps://gomuseum.app/a/louvre/Q1?lang=zh&s=app');
    });

    test('图下载失败 → 只发文字 + 链接,不抛', () async {
      ShareParams? sent;
      await shareObject(info, fetch: (_) async => null, send: (p) async => sent = p);
      expect(sent!.files, anyOf(isNull, isEmpty));
      expect(sent!.text, contains(info.url));
    });
  });
}
```

在 `test/features/guide/guide_hero_actions_test.dart` 里：
- `_sample()` 增加参数 `{ShareInfo? share}` 并传给 `ObjectContent(share: share)`；`_pumpGuide` 增加 `{ShareInfo? share}` 透传。
- 新增两条：

```dart
  testWidgets('share 为 null → 没有分享键(不可分享的件不给入口)', (t) async {
    await _pumpGuide(t);
    expect(_icon(GmIcons.share), findsNothing);
  });

  testWidgets('share 非 null → 有分享键,且与反馈键同款底衬', (t) async {
    await _pumpGuide(t,
        share: const ShareInfo(url: 'https://x/a/orsay/Q1', text: 't', imageUrl: 'https://x/c.png'));
    expect(_icon(GmIcons.share), findsOneWidget);
    final box = t.widget<Container>(
      find.ancestor(of: _icon(GmIcons.share), matching: find.byType(Container)).first,
    );
    expect((box.decoration as BoxDecoration).shape, BoxShape.circle);
  });
```

- [ ] **Step 3: 跑测试确认失败**

Run: `cd frontend/gomuseum_app && flutter test test/features/guide/guide_share_test.dart test/features/guide/guide_hero_actions_test.dart`
Expected: 编译失败（`ShareInfo` / `GmIcons.share` 未定义）

- [ ] **Step 4: 模型** —— `object_content_model.dart`，`class ObjectContent` 之前加：

```dart
/// 分享(加法字段 `share`,2026-09-29)。null = 这件在当前语言下不可分享 → 不显示分享键。
/// 链接/文字/分享图全由服务端下发:版式和文案以后改不用发版。
class ShareInfo extends Equatable {
  const ShareInfo({required this.url, required this.text, required this.imageUrl});

  final String url, text, imageUrl;

  static ShareInfo? fromJson(Object? j) {
    if (j is! Map<String, dynamic>) return null;
    final url = j['url'];
    if (url is! String || url.isEmpty) return null;
    final text = j['text'];
    final image = j['image_url'];
    return ShareInfo(
      url: url,
      text: text is String ? text : '',
      imageUrl: image is String ? image : '',
    );
  }

  @override
  List<Object?> get props => [url, text, imageUrl];
}
```

`ObjectContent`：构造加 `this.share,`，字段 `final ShareInfo? share;`，`fromJson` 加 `share: ShareInfo.fromJson(j['share']),`，`props` 末尾加 `share`。

- [ ] **Step 5: `lib/features/guide/presentation/share_object.dart`**

```dart
/// 讲解页「分享」:下载服务端合成的分享图 → 系统分享面板发「图 + 文字 + 链接」。
///
/// 图下载失败就只发文字 + 链接:分享这个动作不该因为一张图失败。
/// 微信会丢掉附带文字只收图 —— 已知且接受(spec §六)。
library;

import 'dart:typed_data';

import 'package:dio/dio.dart';
import 'package:share_plus/share_plus.dart';
import 'package:gomuseum_app/features/content/data/models/object_content_model.dart';

Future<Uint8List?> _download(String url) async {
  if (url.isEmpty) return null;
  try {
    final r = await Dio(BaseOptions(receiveTimeout: const Duration(seconds: 8)))
        .get<List<int>>(url, options: Options(responseType: ResponseType.bytes));
    final data = r.data;
    return data == null ? null : Uint8List.fromList(data);
  } catch (_) {
    return null;
  }
}

Future<void> _send(ShareParams p) async {
  await SharePlus.instance.share(p);
}

Future<void> shareObject(
  ShareInfo s, {
  Future<Uint8List?> Function(String url)? fetch,
  Future<void> Function(ShareParams p)? send,
}) async {
  final text = s.text.isEmpty ? s.url : '${s.text}\n${s.url}';
  final bytes = await (fetch ?? _download)(s.imageUrl);
  await (send ?? _send)(ShareParams(
    text: text,
    files: bytes == null
        ? null
        : [XFile.fromData(bytes, mimeType: 'image/png', name: 'gomuseum.png')],
  ));
}
```

- [ ] **Step 6: 图标** —— `gm_icon.dart`：enum 末尾（`flag` 之后）加

```dart
  /// 分享(方框里向上的箭头 —— 安卓/iOS 通用的分享语义)。
  share,
```

`_iconPaths` 里加：

```dart
  GmIcons.share: ['M12 3.5v11', 'M8 7.5 12 3.5l4 4', 'M6 11.5v8h12v-8'],
```

- [ ] **Step 7: 顶栏分享键** —— `guide_page.dart`

`_A5HeroSliverAppBar` 加字段（`onFeedback` 之后）：

```dart
  /// 分享。null = 这件不可分享(后端 share 为 null),不渲染这个键。
  final VoidCallback? onShare;
```

构造加 `this.onShare,`，并删掉 `onFeedback` 文档里「分享以后加在它右边。」那一句。`actions:` 改为：

```dart
        actions: [
          if (onShare != null)
            Padding(
              padding: const EdgeInsets.only(right: 6),
              child: _HeroAction(
                icon: GmIcons.share,
                onTap: onShare!,
                label: AppLocalizations.of(context)!.guideShare,
              ),
            ),
          Padding(
            padding: const EdgeInsets.only(right: 8),
            child: _HeroAction(
              icon: GmIcons.flag,
              onTap: onFeedback,
              label: AppLocalizations.of(context)!.fbTitleObject,
            ),
          ),
        ],
```

`_buildA5Page` 里构造 `_A5HeroSliverAppBar(` 处加：

```dart
                  onShare: content.share == null
                      ? null
                      : () => shareObject(content.share!),
```

并在文件顶部 import `package:gomuseum_app/features/guide/presentation/share_object.dart`。

- [ ] **Step 8: l10n** —— 10 个 arb 各加一条 `guideShare`（读屏标签）：

| arb | 值 |
|---|---|
| zh | 分享 |
| zh_Hant | 分享 |
| en | Share |
| fr | Partager |
| es | Compartir |
| de | Teilen |
| it | Condividi |
| pl | Udostępnij |
| ja | 共有 |
| ko | 공유 |

`app_en.arb` 另加 `"@guideShare": {"description": "讲解页顶栏分享键的读屏标签"}`。然后：

Run: `cd frontend/gomuseum_app && flutter gen-l10n`

- [ ] **Step 9: 跑测试 + analyze**

Run: `cd frontend/gomuseum_app && dart format lib test && flutter analyze && flutter test test/features/guide/`
Expected: analyze 0 issue；测试全 PASS

- [ ] **Step 10: 提交**

```bash
git add frontend/gomuseum_app/pubspec.yaml frontend/gomuseum_app/pubspec.lock \
  frontend/gomuseum_app/lib/features/content/data/models/object_content_model.dart \
  frontend/gomuseum_app/lib/features/guide/presentation/share_object.dart \
  frontend/gomuseum_app/lib/ui/gm/gm_icon.dart \
  frontend/gomuseum_app/lib/features/guide/presentation/pages/guide_page.dart \
  frontend/gomuseum_app/test/features/guide/guide_share_test.dart \
  frontend/gomuseum_app/test/features/guide/guide_hero_actions_test.dart
git add frontend/gomuseum_app/lib/l10n/app_*.arb frontend/gomuseum_app/lib/l10n/app_localizations*.dart
git commit -m "feat(share): 讲解页分享键——分享图+文字+链接全由服务端下发,不可分享的件不给入口"
```

---

### Task 6: App Links —— 链接直达藏品 + 守卫保留深链接 → PR 2

**Files:**
- Create: `frontend/gomuseum_app/android/app/src/prod/AndroidManifest.xml`
- Modify: `frontend/gomuseum_app/lib/core/router/app_router.dart`
- Modify: `frontend/gomuseum_app/lib/features/auth/presentation/login_page.dart`（4 处 `context.go('/')` + 注册链接）
- Modify: `frontend/gomuseum_app/lib/features/auth/presentation/register_page.dart`（1 处 `context.go('/')`）
- Test: `frontend/gomuseum_app/test/core/router/auth_guard_test.dart`

**Interfaces:**
- Produces:
  - `String? authRedirect({required User? user, required String path, bool upgrading = false, String? location, String? from})`
  - `String? deepLinkReturn(String? from)` —— 合法深链接原样返回，否则 null
  - `LoginPage({bool upgrading = false, String? returnTo})`、`RegisterPage({String? returnTo})`

- [ ] **Step 1: 失败测试** —— `auth_guard_test.dart` 末尾加 group

```dart
  group('🔴 App Links 深链接不能在冷启动的登录来回里丢掉', () {
    // 时序:点链接冷启动 → 登录态 loading(user=null) → 守卫弹去 /login →
    // 加载完已登录 → 守卫再跑。旧行为送回 '/' —— 用户点了作品链接却落在首页。
    const link = '/a/louvre/Q1?lang=zh&s=app';

    test('未登录访问深链接 → 去登录页并带上原目标', () {
      expect(
        authRedirect(user: null, path: '/a/louvre/Q1', location: link),
        '/login?from=${Uri.encodeComponent(link)}',
      );
    });

    test('登录态就绪后停在 /login?from=深链接 → 送回原目标,不是首页', () {
      expect(authRedirect(user: _user(isGuest: true), path: '/login', from: link), link);
      expect(authRedirect(user: _user(isGuest: false), path: '/login', from: link), link);
    });

    test('from 不是深链接(伪造/外部)→ 照旧回首页', () {
      expect(authRedirect(user: _user(isGuest: true), path: '/login', from: '/benefits'), '/');
      expect(authRedirect(user: _user(isGuest: true), path: '/login', from: 'https://evil.example/a/x'), '/');
    });

    test('非深链接的受保护路由行为不变:仍是裸 /login', () {
      expect(authRedirect(user: null, path: '/benefits', location: '/benefits'), '/login');
    });

    test('已登录直接访问深链接 → 放行', () {
      expect(authRedirect(user: _user(isGuest: false), path: '/a/louvre/Q1', location: link), isNull);
    });

    test('deepLinkReturn 只认 /a/ 开头的站内路径', () {
      expect(deepLinkReturn(link), link);
      expect(deepLinkReturn('/history'), isNull);
      expect(deepLinkReturn(null), isNull);
      expect(deepLinkReturn('//evil.example/a/x'), isNull);
    });
  });
```

- [ ] **Step 2: 跑测试确认失败**

Run: `cd frontend/gomuseum_app && flutter test test/core/router/auth_guard_test.dart`
Expected: 编译失败（`location`/`from` 参数、`deepLinkReturn` 不存在）

- [ ] **Step 3: 守卫** —— `app_router.dart`，`authRedirect` 之前加：

```dart
/// App Links 落点前缀(spec 2026-09-20-share-web-pages-design §六)。
const kDeepLinkPrefix = '/a/';

/// 登录后可以送回去的目标:只认站内的 `/a/...` 深链接。
/// 其余受保护路由被弹去登录后照旧回首页(不改既有行为);外部/伪造的 from 一律丢弃。
String? deepLinkReturn(String? from) =>
    from != null && from.startsWith(kDeepLinkPrefix) ? from : null;
```

`authRedirect` 改为：

```dart
String? authRedirect({
  required User? user,
  required String path,
  bool upgrading = false,
  String? location,
  String? from,
}) {
  final isLoggedIn = user != null;
  final isPublicRoute = path == '/login' || path == '/register';

  // 未登录且访问受保护路由 → 跳转登录页。
  // 深链接要把原目标带过去:冷启动时登录态还在 loading,user 是 null,
  // 不带的话等登录态就绪就只剩"回首页",用户点的那件作品丢了。
  if (!isLoggedIn && !isPublicRoute) {
    final back = deepLinkReturn(location);
    return back == null ? '/login' : '/login?from=${Uri.encodeComponent(back)}';
  }

  // (保留原有「已登录还停在登录/注册页 → 回首页」那一大段注释)
  if (isLoggedIn && isPublicRoute && !upgrading) {
    return deepLinkReturn(from) ?? '/';
  }

  return null;
}
```

`goRouterProvider` 的 `redirect` 里调用处加两参：

```dart
        location: state.uri.toString(),
        from: state.uri.queryParameters['from'],
```

`/login`、`/register` 两个 GoRoute 的 builder 改为：

```dart
        builder: (context, state) => LoginPage(
          upgrading: state.uri.queryParameters[kUpgradeParam] == '1',
          returnTo: deepLinkReturn(state.uri.queryParameters['from']),
        ),
```

```dart
        builder: (context, state) => RegisterPage(
          returnTo: deepLinkReturn(state.uri.queryParameters['from']),
        ),
```

在「讲解页」GoRoute 之后加深链接路由：

```dart
      // App Links 落点:gomuseum.app/a/{slug}/{qid} → 直达那件藏品的讲解页。
      // 链接里的 lang 忽略:App 用用户自己的语言。隐身馆/不存在的 qid 走讲解页自己的错误态。
      GoRoute(
        path: '/a/:slug/:qid',
        name: 'deeplink-object',
        builder: (context, state) => GuidePage(
          args: GuideArgs(
            slug: state.pathParameters['slug'],
            qid: state.pathParameters['qid'],
          ),
        ),
      ),
```

- [ ] **Step 4: 登录/注册页带回原目标**

`login_page.dart`：`LoginPage` 加

```dart
  /// 登录成功后回到哪里。只可能是 App Links 深链接(路由已用 deepLinkReturn 过滤);
  /// null = 首页。
  final String? returnTo;
```

构造 `const LoginPage({super.key, this.upgrading = false, this.returnTo});`（保留现有其它参数）。
把文件里 4 处 `context.go('/');` 全部替换为 `context.go(widget.returnTo ?? '/');`。
注册链接改为保留 from：

```dart
                  onTap: () => context.push(Uri(
                    path: '/register',
                    queryParameters: {
                      if (upgrading) kUpgradeParam: '1',
                      if (widget.returnTo != null) 'from': widget.returnTo!,
                    },
                  ).toString()),
```

`register_page.dart`：同样加 `final String? returnTo;`（构造 `this.returnTo`），唯一一处 `context.go('/');` → `context.go(widget.returnTo ?? '/');`。

- [ ] **Step 5: prod flavor manifest** —— `android/app/src/prod/AndroidManifest.xml`

```xml
<!-- App Links(spec 2026-09-20-share-web-pages-design §六):只挂 prod flavor。
     staging 包名是 com.gomuseum.app.staging,assetlinks.json 只登记了正式包名,挂上也验证不过。
     staging 手测用:adb shell am start -a android.intent.action.VIEW
       -n com.gomuseum.app.staging/com.gomuseum.app.MainActivity -d "https://gomuseum.app/a/louvre/Q..." -->
<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <activity android:name=".MainActivity">
            <intent-filter android:autoVerify="true">
                <action android:name="android.intent.action.VIEW" />
                <category android:name="android.intent.category.DEFAULT" />
                <category android:name="android.intent.category.BROWSABLE" />
                <data android:scheme="https" android:host="gomuseum.app" android:pathPrefix="/a/" />
            </intent-filter>
        </activity>
    </application>
</manifest>
```

- [ ] **Step 6: 验证合并后的 manifest**

Run:
```bash
cd frontend/gomuseum_app && flutter build apk --flavor prod --debug --dart-define=API_BASE_URL=https://api.gomuseum.app && \
grep -rl 'pathPrefix="/a/"' build/app/intermediates/merged_manifest* | head -3; \
flutter build apk --flavor staging --debug --dart-define=API_BASE_URL=https://staging-api.gomuseum.app && \
grep -rl 'pathPrefix="/a/"' build/app/intermediates/merged_manifest*/stagingDebug* | wc -l
```
Expected: prod 能 grep 到；staging 那条计数为 0。

- [ ] **Step 7: 测试 + analyze + 提交 + PR**

Run: `cd frontend/gomuseum_app && dart format lib test && flutter analyze && flutter test`
Expected: 全 PASS

```bash
git add frontend/gomuseum_app/android/app/src/prod/AndroidManifest.xml \
  frontend/gomuseum_app/lib/core/router/app_router.dart \
  frontend/gomuseum_app/lib/features/auth/presentation/login_page.dart \
  frontend/gomuseum_app/lib/features/auth/presentation/register_page.dart \
  frontend/gomuseum_app/test/core/router/auth_guard_test.dart
git commit -m "feat(share): App Links 直达藏品讲解页——守卫在冷启动登录来回里保留深链接目标"
git push -u origin feature/share-app
gh pr create --base staging --title "feat(share): App 分享键 + App Links 直达藏品" --body "..."
```
checks 非 pass 为 0 → `gh pr merge --squash --delete-branch`。

破坏验证（提交后）：把 `authRedirect` 里 `return deepLinkReturn(from) ?? '/';` 改回 `return '/';`，Expected: 「送回原目标」那条 FAIL；`git checkout -- lib/core/router/app_router.dart` 还原。

---

## 上线清单（非代码，按序；标 👤 的只能用户做）

1. 👤 staging→main 合并，后端上 prod（合 main 前先查 prod 有无长任务在跑）。
2. 👤 Play Console →「应用完整性」复制**应用签名密钥** SHA-256 给我 → 我替换 `assetlinks.json` 里的 `PLAY_APP_SIGNING_SHA256_FROM_CONSOLE`（小 PR）→ 👤 把 `deployment/website/.well-known/assetlinks.json` 放到 `/opt/gomuseum/website/.well-known/`。
3. 👤 按 `deployment/production/nginx-gomuseum.app.share.conf` 配 nginx，`nginx -t && systemctl reload nginx`；我用片段里的两条 curl 验证。
4. 版本号 +1（`pubspec.yaml` **和** `settings_page.dart` 的 `kVersionFootnote` 两处）→ PR → CI 全绿 → 合 → 出 AAB（`--flavor prod --release --dart-define=API_BASE_URL=https://api.gomuseum.app`）→ 核证书 CN=GoMuseum。
5. 👤 上传内测 → 真机验（我同步看 nginx 日志）：
   - WhatsApp 发给自己：卡片带图、标题；收到的有分享图
   - 微信发给自己：收到图片
   - 已装 App 点链接 → 直接进那件讲解页（`adb shell pm get-app-links com.gomuseum.app` 显示 `verified`）
   - 杀进程后点链接（冷启动）→ 仍进讲解页，不落首页
   - 不可分享的件（无正文语言 / 隐身馆预览账号）→ 没有分享键
6. 推正式轨道那天：👤 prod env 设 `SHARE_PLAY_LIVE=true` 并重启后端 → 网页粘底条变 Play 下载按钮（不发版）。
