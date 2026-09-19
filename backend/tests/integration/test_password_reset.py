"""找回密码 / 邮箱验证。

在这之前**账号没有任何找回手段** —— 邮箱密码注册的人忘了密码就永久登不进去,
而通票挂在账号上,等于付了钱的人拿不回自己买的东西。

这里钉的几条,每一条都对应一种"看起来能用、实际是个洞"的形态:
  - 泄漏账号是否存在(端点变成账号枚举器)
  - 发信失败被吞成 204(用户守着永远不来的邮件)
  - 令牌可重复使用 / 重发后旧的还有效(收件箱里积着好几把有效钥匙)
  - 给纯 OAuth 账号发重置(凭邮箱新造一把绕过 Google 二步验证的钥匙)
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import settings
from app.core.database import Base, get_db
from app.core.security import verify_password
from app.main import app
from app.models.auth_token import PURPOSE_PASSWORD_RESET, AuthToken
from app.models.user import User
from app.services import account_recovery, mailer
from tests.conftest import account_tables


class Outbox(list):
    """替掉真发信。每封记 (to, subject, body)。"""

    def send(self, to, subject, body):
        self.append((to, subject, body))


@pytest.fixture()
def outbox(monkeypatch):
    box = Outbox()
    monkeypatch.setattr(mailer, "send", box.send)
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    return box


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(bind=engine, tables=account_tables())
    s = sessionmaker(bind=engine, autoflush=False, autocommit=False)()
    app.dependency_overrides[get_db] = lambda: s
    yield TestClient(app), s
    app.dependency_overrides.clear()
    s.close()


def _register(c, email="a@test.com", password="OldPass123!"):
    r = c.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "username": "u"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _link(body: str) -> str:
    """从邮件正文里把链接抠出来 —— 用户拿到的就只有这封信。"""
    for word in body.split():
        if "token=" in word:
            return word
    raise AssertionError(f"邮件里没有链接:\n{body}")


def _link_token(body: str) -> str:
    """只要 token。⚠️ 链接现在还带 `&lang=`,不能一路取到行尾。"""
    return _link(body).split("token=", 1)[1].split("&", 1)[0]


# ───────────────────────────────────────────────────── 主线:真的能找回


def test_forgotten_password_can_actually_be_reset(client, outbox):
    """整条路走通:申请 → 收信 → 用新密码登录,且旧密码作废。"""
    c, db = client
    _register(c)
    outbox.clear()  # 注册时那封验证信不算

    assert (
        c.post(
            "/api/v1/auth/password-reset/request", json={"email": "a@test.com"}
        ).status_code
        == 204
    )
    assert len(outbox) == 1
    token = _link_token(outbox[0][2])

    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "BrandNew456!"},
        ).status_code
        == 204
    )

    ok = c.post(
        "/api/v1/auth/login", json={"email": "a@test.com", "password": "BrandNew456!"}
    )
    assert ok.status_code == 200, "新密码登不进去 = 这条路白建了"
    bad = c.post(
        "/api/v1/auth/login", json={"email": "a@test.com", "password": "OldPass123!"}
    )
    assert bad.status_code == 401, "旧密码还能用 = 重置没生效"


def test_reset_page_renders_the_form_for_a_live_token(client, outbox):
    """邮件里那条链接必须真能落到一张能填新密码的页面上。"""
    c, _ = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    page = c.get(f"/api/v1/auth/reset?token={token}")
    assert page.status_code == 200
    assert "password-reset/confirm" in page.text, "页面没接上提交端点"
    assert token in page.text, "令牌没注入进页面,提交时无从带上"


def test_reset_page_does_not_consume_the_token(client, outbox):
    """**打开页面不等于用掉链接。**

    先消费的话,用户点开却没提交(手滑关掉、想换个密码再想)链接就废了,
    而他完全不知道为什么。
    """
    c, _ = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    c.get(f"/api/v1/auth/reset?token={token}")
    c.get(f"/api/v1/auth/reset?token={token}")  # 再看一次也不该失效

    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "BrandNew456!"},
        ).status_code
        == 204
    )


# ───────────────────────────────────────────────── 洞:一个都不能漏


def test_unknown_email_is_indistinguishable_from_a_real_one(client, outbox):
    """⭐ **不能泄漏账号是否存在。**

    若"查无此邮箱"返 404,这个端点就是个账号枚举器:拿一份邮箱列表来问一遍,
    就知道你们这儿有哪些用户。响应必须与真实存在时完全一致。
    """
    c, _ = client
    _register(c, email="real@test.com")
    outbox.clear()

    hit = c.post("/api/v1/auth/password-reset/request", json={"email": "real@test.com"})
    miss = c.post(
        "/api/v1/auth/password-reset/request", json={"email": "ghost@test.com"}
    )

    assert hit.status_code == miss.status_code == 204
    assert hit.text == miss.text
    assert len(outbox) == 1, "给不存在的邮箱也发了信"


def test_no_enumeration_even_when_mail_is_unconfigured(client, monkeypatch):
    """⭐ **枚举与"让失败可见"会打架,而第一版输了。**

    上面那条只在"SMTP 已配好"这一种配置下比较两者,于是全绿;
    而 staging/prod 上线之初恰恰**还没配 SMTP**,真实表现是:

        不存在的邮箱          → 204(压根走不到发信那步)
        真实存在的邮箱        → 503 mail_not_configured

    响应因账号是否存在而不同 = 账号枚举器,正是上面那条声称堵住的洞。
    2026-09-05 在 staging 实跑时撞见 —— 单测一条都没红。

    解法是**顺序**:配置检查放在查库之前,没配时对谁都是 503。
    """
    c, _ = client
    # 先在"配好"的状态下注册一个真实账号
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda *a, **k: None)
    _register(c, email="real@test.com")

    # 再把发信通道拿掉 —— 这就是上线之初的真实状态
    monkeypatch.setattr(mailer, "is_configured", lambda: False)

    hit = c.post("/api/v1/auth/password-reset/request", json={"email": "real@test.com"})
    miss = c.post(
        "/api/v1/auth/password-reset/request", json={"email": "ghost@test.com"}
    )
    assert hit.status_code == miss.status_code, (
        f"注册过的返 {hit.status_code}、没注册的返 {miss.status_code} "
        "—— 这个差别就是账号枚举器"
    )
    assert hit.text == miss.text
    assert hit.status_code == 503, "没配发信仍必须明确失败,不能假装发出去了"


def test_oauth_only_account_gets_no_reset_mail(client, outbox):
    """⭐ 纯 Google 账号没有密码。

    给它发"重置"= 凭一封邮件**新造一把绕过 Google 二步验证的钥匙**,
    把账号安全降到"邮箱有多安全",而用户从没要求过这个。他有能用的登录方式。
    """
    c, db = client
    db.add(
        User(
            email="g@test.com",
            username="g",
            google_id="google-123",
            password_hash=None,
            is_active=True,
            is_verified=True,
        )
    )
    db.commit()
    outbox.clear()

    r = c.post("/api/v1/auth/password-reset/request", json={"email": "g@test.com"})
    assert r.status_code == 204, "不能因此泄漏这个账号的登录方式"
    assert outbox == [], "给纯 OAuth 账号发了重置信"


def test_guest_account_gets_no_reset_mail(client, outbox):
    c, db = client
    db.add(
        User(
            email="guest@test.com",
            username="游客",
            password_hash="x",
            is_active=True,
            is_guest=True,
        )
    )
    db.commit()
    outbox.clear()

    c.post("/api/v1/auth/password-reset/request", json={"email": "guest@test.com"})
    assert outbox == []


def test_mail_send_failure_is_surfaced_not_swallowed(client, monkeypatch):
    """⭐ **发信失败必须让用户看见。**

    这条路是他此刻唯一的出口。吞成 204 = 他守着一封永远不来的邮件反复重试,
    而我们日志干净、监控全绿 —— 最难发现的那种故障。
    """
    c, _ = client
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda *a, **k: None)
    _register(c)

    def _boom(*a, **k):
        raise mailer.MailSendFailed("connection refused")

    monkeypatch.setattr(mailer, "send", _boom)
    r = c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    assert r.status_code == 502


def test_unconfigured_smtp_is_surfaced_not_swallowed(client, monkeypatch):
    """没配 SMTP 时必须 503,绝不"假装发出去了"。"""
    c, _ = client
    monkeypatch.setattr(mailer, "is_configured", lambda: True)
    monkeypatch.setattr(mailer, "send", lambda *a, **k: None)
    _register(c)

    def _nope(*a, **k):
        raise mailer.MailNotConfigured("SMTP_HOST 未配置")

    monkeypatch.setattr(mailer, "send", _nope)
    r = c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    assert r.status_code == 503


def test_token_works_exactly_once(client, outbox):
    """⭐ 邮件会一直躺在收件箱里。可重复使用的重置链接 =
    这个账号从此挂着一把永久备用钥匙。"""
    c, _ = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    first = c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "First12345!"},
    )
    second = c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "Second12345!"},
    )
    assert first.status_code == 204
    assert second.status_code == 400

    # 第二次没生效:密码还是第一次设的那个
    assert (
        c.post(
            "/api/v1/auth/login",
            json={"email": "a@test.com", "password": "First12345!"},
        ).status_code
        == 200
    )


def test_resending_invalidates_the_previous_link(client, outbox):
    """⭐ 重发之后旧链接必须作废。

    否则收件箱里积着好几把有效钥匙,而用户以为只有最新那封算数。
    """
    c, _ = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    old = _link_token(outbox[0][2])
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    new = _link_token(outbox[1][2])
    assert old != new

    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": old, "new_password": "Whatever123!"},
        ).status_code
        == 400
    )
    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": new, "new_password": "Whatever123!"},
        ).status_code
        == 204
    )


def test_expired_token_is_rejected(client, outbox, monkeypatch):
    c, db = client
    monkeypatch.setattr(settings, "PASSWORD_RESET_TTL_MINUTES", 0)
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "Whatever123!"},
        ).status_code
        == 400
    )
    page = c.get(f"/api/v1/auth/reset?token={token}&lang=zh")
    assert "失效" in page.text


def test_plaintext_token_is_never_stored(client, outbox):
    """⭐ 库里只能有哈希。

    明文入库 = **一次只读的泄漏(备份、慢查询日志、只读副本)就等于批量接管账号**。
    """
    c, db = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    rows = db.query(AuthToken).filter_by(purpose=PURPOSE_PASSWORD_RESET).all()
    assert rows, "没落库"
    for r in rows:
        assert r.token_hash != token
        assert token not in r.token_hash
        assert len(r.token_hash) == 64  # SHA-256 hex


def test_password_is_stored_hashed_after_reset(client, outbox):
    c, db = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])
    c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "BrandNew456!"},
    )

    user = db.query(User).filter_by(email="a@test.com").one()
    assert user.password_hash != "BrandNew456!"
    assert verify_password("BrandNew456!", user.password_hash)


def test_short_password_rejected(client, outbox):
    c, _ = client
    _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    r = c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": token, "new_password": "short"},
    )
    assert r.status_code == 422


def test_deleting_the_account_kills_its_live_tokens(client, outbox):
    """删号之后,收件箱里那封信不能还是一把能用的钥匙。"""
    c, db = client
    tokens = _register(c)
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    token = _link_token(outbox[0][2])

    c.delete(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )

    assert db.query(AuthToken).count() == 0
    assert (
        c.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "Whatever123!"},
        ).status_code
        == 400
    )


# ───────────────────────────────────────────────────────── 邮箱验证


def test_registration_sends_a_verification_mail(client, outbox):
    """邮箱写错了(少个字母、填成别人的)此刻毫无症状,直到某天他忘了密码 ——
    那时才发现唯一的找回通道从一开始就是断的。所以注册时就发一封。"""
    c, _ = client
    _register(c, email="typo@test.com")
    assert len(outbox) == 1
    assert outbox[0][0] == "typo@test.com"


def test_registration_survives_a_broken_mailer(client, monkeypatch):
    """⚠️ 发信是锦上添花,注册是主线。SMTP 抽风绝不能让人注册不了。"""
    c, _ = client
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.example.com")
    monkeypatch.setattr(mailer, "is_configured", lambda: True)

    def _boom(*a, **k):
        raise RuntimeError("SMTP exploded")

    monkeypatch.setattr(mailer, "send", _boom)
    r = c.post(
        "/api/v1/auth/register",
        json={"email": "x@test.com", "password": "Pass12345!", "username": "x"},
    )
    assert r.status_code == 201


def test_email_verification_link_marks_the_account_verified(client, outbox):
    c, db = client
    _register(c, email="v@test.com")
    token = _link_token(outbox[0][2])

    page = c.get(f"/api/v1/auth/verify-email?token={token}&lang=zh")
    assert page.status_code == 200
    assert "已确认" in page.text

    user = db.query(User).filter_by(email="v@test.com").one()
    assert user.is_verified is True
    assert user.email_verified_at is not None


def test_email_verification_link_is_single_use(client, outbox):
    c, _ = client
    _register(c, email="v@test.com")
    token = _link_token(outbox[0][2])

    c.get(f"/api/v1/auth/verify-email?token={token}&lang=zh")
    again = c.get(f"/api/v1/auth/verify-email?token={token}&lang=zh")
    assert "失效" in again.text


def test_reset_and_verify_tokens_are_not_interchangeable(client, outbox):
    """⭐ 两种令牌同表不同 purpose。**不能拿一种去换另一种的权限。**

    验证信的有效期是 24 小时、重置信只有 30 分钟 —— 若能混用,
    等于给每个注册用户发了一把 24 小时有效的改密钥匙。
    """
    c, _ = client
    _register(c, email="v@test.com")
    verify_token = _link_token(outbox[0][2])

    r = c.post(
        "/api/v1/auth/password-reset/confirm",
        json={"token": verify_token, "new_password": "Hijacked123!"},
    )
    assert r.status_code == 400

    # 反过来同理
    outbox.clear()
    c.post("/api/v1/auth/password-reset/request", json={"email": "v@test.com"})
    reset_token = _link_token(outbox[0][2])
    assert (
        "失效" in c.get(f"/api/v1/auth/verify-email?token={reset_token}&lang=zh").text
    )


def test_mail_language_follows_the_request(client, outbox):
    """老 App 不传 language → 默认英文(加法字段,契约前向兼容)。"""
    c, _ = client
    _register(c)
    outbox.clear()

    c.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "a@test.com", "language": "zh"},
    )
    assert "重设" in outbox[-1][1]

    c.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "a@test.com", "language": "fr-FR"},
    )
    assert "mot de passe" in outbox[-1][1]

    c.post("/api/v1/auth/password-reset/request", json={"email": "a@test.com"})
    assert "Reset your" in outbox[-1][1]

    c.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "a@test.com", "language": "sw"},  # 没文案的语言
    )
    assert "Reset your" in outbox[-1][1], "认不出的语言该回落英文,不能发空信"


def test_token_is_html_escaped_in_the_page(client, monkeypatch):
    """页面把令牌注进 <script>。**任何注入都必须被转义** ——
    这个值来自 URL,完全由攻击者控制。"""
    c, db = client
    payload = '"></script><script>alert(1)</script>'
    monkeypatch.setattr(
        account_recovery,
        "peek",
        lambda *a, **k: object(),  # 假装令牌有效,只看渲染
    )
    page = c.get("/api/v1/auth/reset", params={"token": payload})
    assert "<script>alert(1)</script>" not in page.text
    assert "&lt;script&gt;" in page.text or "&quot;" in page.text


# ─────────────────────────────────────────── 落地页的语言(2026-09-07 真机发现)


def _reset_page(c, token: str, **kw):
    return c.get(f"/api/v1/auth/reset?token={token}", **kw)


def test_mail_link_carries_the_language(client, outbox):
    """链接必须带 lang —— 落地页除了这条 URL 没有别的途径知道用户用哪种语言。

    ⚠️ 这是整条修复的支点:邮件是在 App 里发起的(那时知道语言),
    但链接是在系统浏览器里打开的,既没有 App 的登录态也没有它的语言设置。
    """
    c, _ = client
    _register(c)
    c.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "a@test.com", "language": "zh"},
    )
    assert "&lang=zh" in _link(outbox[-1][2])


def test_page_language_follows_the_language_the_mail_was_sent_in(client, outbox):
    """信是哪种语言,页面就是哪种语言 —— 而且**不掺另外两种**。

    修复前:邮件跟着语言走,页面永远是三语堆叠(重设密码 / Set a new password /
    Définir un nouveau mot de passe)。用户真机报的就是这个。
    """
    c, _ = client
    expected = {
        "zh": ("重设密码", ["Set a new password", "Définir un nouveau"]),
        "en": ("Set a new password", ["重设密码", "Définir un nouveau"]),
        "fr": ("Définir un nouveau mot de passe", ["重设密码", "Set a new password"]),
    }
    for i, (lang, (want, must_not)) in enumerate(expected.items()):
        email = f"u{i}@test.com"
        _register(c, email=email)
        c.post(
            "/api/v1/auth/password-reset/request",
            json={"email": email, "language": lang},
        )
        body = outbox[-1][2]
        html = c.get(_link(body).replace("http://testserver", "")).text
        assert want in html, f"{lang}:页面上没有该语言的标题"
        for other in must_not:
            assert other not in html, f"{lang}:页面上混进了别的语言「{other}」"
        assert f'<html lang="{ "zh-CN" if lang == "zh" else lang }"' in html


def test_expired_link_notice_follows_the_language_too(client, outbox):
    """「链接已失效」是最常被看到的一页(重复点开就是它),不能漏。"""
    c, _ = client
    html = c.get("/api/v1/auth/reset?token=bogus&lang=fr").text
    assert "Lien non valide" in html
    assert "链接已失效" not in html


def test_unknown_language_falls_back_to_english(client, outbox):
    """认不出的语言回落英文 —— 和邮件同一条规则,不能两处不一致。"""
    c, _ = client
    html = c.get("/api/v1/auth/reset?token=bogus&lang=ja").text
    assert "Link no longer valid" in html


def test_old_links_without_lang_fall_back_to_the_browser(client, outbox):
    """本次改动之前发出去的链接没有 lang —— 那时只能问浏览器,不能崩、不能空白。"""
    c, _ = client
    html = c.get(
        "/api/v1/auth/reset?token=bogus", headers={"Accept-Language": "fr-FR,fr;q=0.9"}
    ).text
    assert "Lien non valide" in html


def test_page_copy_never_gets_inlined_into_the_script(client, outbox):
    """⭐ 文案必须走 data-* 属性,**不能拼进 <script> 字面量**。

    模板替换会做 HTML 转义。转义后的 `&#x27;` 在属性值里会被浏览器还原成 `'`
    (正确),拼进 <script> 里却会原样显示成 `&#x27;`(错误)。
    法语文案里就有撇号(l'application),这不是假想的边角 —— 而它**只在法语下
    现形**,英语中文都看不出来。
    """
    import html as _html
    import re

    c, _ = client
    _register(c, email="fr@test.com")
    c.post(
        "/api/v1/auth/password-reset/request",
        json={"email": "fr@test.com", "language": "fr"},
    )
    page = c.get(_link(outbox[-1][2]).replace("http://testserver", "")).text

    script = page[page.rindex("<script>") : page.rindex("</script>")]
    assert (
        "l&#x27;application" not in script and "l'application" not in script
    ), "法语文案被拼进了 <script>:转义后的实体会原样显示给用户"

    attr = re.search(r'data-ok="([^"]*)"', page).group(1)
    assert _html.unescape(attr) == (
        "Mot de passe mis à jour — connectez-vous dans l'application."
    )
