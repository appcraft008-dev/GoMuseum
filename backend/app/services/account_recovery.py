"""找回密码与邮箱验证。

## 为什么这是"上线前必须有"的东西

通票挂在账号上。用邮箱密码注册的用户忘了密码 → 永久登不进去 →
**付了钱的人拿不回自己买的东西**,而我们只能靠人工改库救。
触发条件不是"将来某天",是第一个真实付费用户忘记密码。

## 几条不显然的取舍

- **只给「已经有密码」的账号发重置信。** 纯 Google/Apple 登录的账号没有密码,
  给它"重置"等于**凭一封邮件新造一把绕过 Google 二步验证的钥匙** ——
  账号安全被降到"邮箱有多安全",而用户从没要求过这个。他们有能用的登录方式。

- **无论如何都返回 204。** 若"邮箱不存在"返 404,这个端点就成了**账号枚举器**:
  谁都能拿一份邮箱列表来问"你们这儿有哪些用户"。

- **发信失败必须让用户看见(502)。** 找回密码是他此刻唯一的路;
  静默失败 = 他守着一封永远不来的邮件反复重试,而我们日志干净、监控全绿。

- **令牌只存哈希、用一次即废、旧的重发即作废。** 见 models/auth_token.py。
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from app.core.config import settings
from app.core.security import hash_password
from app.models.auth_token import (
    PURPOSE_EMAIL_VERIFY,
    PURPOSE_PASSWORD_RESET,
    AuthToken,
)
from app.models.user import User
from app.services import mailer

logger = logging.getLogger(__name__)

# 认不出的语言一律回落英文 —— 宁可给一封看得懂的英文信,不给一封空的。
# zh-hant 与 App 的 apiLanguage() 同一个写法(2026-09-30 补:繁体用户曾拿到简体信)。
DEFAULT_LANG = "en"
SUPPORTED_LANGS = ("en", "fr", "zh", "zh-hant", "de", "es", "it", "pl", "ja", "ko")
# 浏览器 Accept-Language 常只带地区不带脚本码(zh-TW);脚本码优先于地区。
_HANT_REGIONS = ("tw", "hk", "mo")

_RESET_MAIL = {
    "en": (
        "Reset your GoMuseum password",
        "Open this link to choose a new password:\n\n{link}\n\n"
        "The link expires in {minutes} minutes and can be used once.\n"
        "If you didn't ask for this, you can ignore this email — "
        "your password stays unchanged.",
    ),
    "fr": (
        "Réinitialiser votre mot de passe GoMuseum",
        "Ouvrez ce lien pour choisir un nouveau mot de passe :\n\n{link}\n\n"
        "Le lien expire dans {minutes} minutes et ne peut servir qu'une fois.\n"
        "Si vous n'êtes pas à l'origine de cette demande, ignorez ce message — "
        "votre mot de passe reste inchangé.",
    ),
    "zh": (
        "重设 GoMuseum 密码",
        "打开这个链接设置新密码：\n\n{link}\n\n"
        "链接 {minutes} 分钟内有效，只能用一次。\n"
        "如果不是你本人操作，忽略这封邮件即可，密码不会有任何变化。",
    ),
    "zh-hant": (
        "重設 GoMuseum 密碼",
        "開啟這個連結設定新密碼：\n\n{link}\n\n"
        "連結 {minutes} 分鐘內有效，只能使用一次。\n"
        "如果不是你本人操作，忽略這封郵件即可，密碼不會有任何變更。",
    ),
    "de": (
        "GoMuseum-Passwort zurücksetzen",
        "Öffne diesen Link, um ein neues Passwort festzulegen:\n\n{link}\n\n"
        "Der Link ist {minutes} Minuten gültig und kann nur einmal verwendet werden.\n"
        "Wenn du das nicht angefordert hast, kannst du diese E-Mail ignorieren — "
        "dein Passwort bleibt unverändert.",
    ),
    "es": (
        "Restablece tu contraseña de GoMuseum",
        "Abre este enlace para elegir una contraseña nueva:\n\n{link}\n\n"
        "El enlace caduca en {minutes} minutos y solo puede usarse una vez.\n"
        "Si no lo has solicitado, ignora este correo: "
        "tu contraseña no cambiará.",
    ),
    "it": (
        "Reimposta la password di GoMuseum",
        "Apri questo link per scegliere una nuova password:\n\n{link}\n\n"
        "Il link scade tra {minutes} minuti e può essere usato una sola volta.\n"
        "Se non hai richiesto tu il ripristino, ignora questa e-mail: "
        "la tua password resta invariata.",
    ),
    "pl": (
        "Zresetuj hasło do GoMuseum",
        "Otwórz ten link, aby ustawić nowe hasło:\n\n{link}\n\n"
        "Link wygasa po {minutes} minutach i można go użyć tylko raz.\n"
        "Jeśli ta prośba nie pochodzi od Ciebie, zignoruj tę wiadomość — "
        "Twoje hasło pozostanie bez zmian.",
    ),
    "ja": (
        "GoMuseum のパスワード再設定",
        "以下のリンクを開いて、新しいパスワードを設定してください：\n\n{link}\n\n"
        "リンクの有効期限は {minutes} 分で、1 回だけ使用できます。\n"
        "お心当たりがない場合は、このメールを無視してください。"
        "パスワードは変更されません。",
    ),
    "ko": (
        "GoMuseum 비밀번호 재설정",
        "아래 링크를 열어 새 비밀번호를 설정하세요:\n\n{link}\n\n"
        "링크는 {minutes}분 동안 유효하며 한 번만 사용할 수 있습니다.\n"
        "직접 요청하지 않았다면 이 메일은 무시하셔도 됩니다. "
        "비밀번호는 변경되지 않습니다.",
    ),
}

_VERIFY_MAIL = {
    "en": (
        "Confirm your GoMuseum email",
        "Open this link to confirm this address:\n\n{link}\n\n"
        "The link expires in {minutes} minutes.\n"
        "Confirming keeps password recovery working if you ever need it.",
    ),
    "fr": (
        "Confirmez votre adresse e-mail GoMuseum",
        "Ouvrez ce lien pour confirmer cette adresse :\n\n{link}\n\n"
        "Le lien expire dans {minutes} minutes.\n"
        "La confirmation garantit que la récupération de mot de passe "
        "fonctionnera le jour où vous en aurez besoin.",
    ),
    "zh": (
        "确认你的 GoMuseum 邮箱",
        "打开这个链接确认这个邮箱地址：\n\n{link}\n\n"
        "链接 {minutes} 分钟内有效。\n"
        "确认之后，万一将来需要找回密码才走得通。",
    ),
    "zh-hant": (
        "確認你的 GoMuseum 電子郵件",
        "開啟這個連結確認這個電子郵件地址：\n\n{link}\n\n"
        "連結 {minutes} 分鐘內有效。\n"
        "確認之後，萬一將來需要找回密碼才走得通。",
    ),
    "de": (
        "Bestätige deine E-Mail-Adresse für GoMuseum",
        "Öffne diesen Link, um diese Adresse zu bestätigen:\n\n{link}\n\n"
        "Der Link ist {minutes} Minuten gültig.\n"
        "Mit der Bestätigung funktioniert die Passwort-Wiederherstellung, "
        "falls du sie einmal brauchst.",
    ),
    "es": (
        "Confirma tu correo de GoMuseum",
        "Abre este enlace para confirmar esta dirección:\n\n{link}\n\n"
        "El enlace caduca en {minutes} minutos.\n"
        "Al confirmarla, podrás recuperar tu contraseña si algún día lo necesitas.",
    ),
    "it": (
        "Conferma la tua e-mail GoMuseum",
        "Apri questo link per confermare questo indirizzo:\n\n{link}\n\n"
        "Il link scade tra {minutes} minuti.\n"
        "Confermandolo potrai recuperare la password se un giorno ne avrai bisogno.",
    ),
    "pl": (
        "Potwierdź swój adres e-mail w GoMuseum",
        "Otwórz ten link, aby potwierdzić ten adres:\n\n{link}\n\n"
        "Link wygasa po {minutes} minutach.\n"
        "Dzięki potwierdzeniu odzyskasz hasło, jeśli kiedyś będzie to potrzebne.",
    ),
    "ja": (
        "GoMuseum のメールアドレス確認",
        "以下のリンクを開いて、このメールアドレスを確認してください：\n\n{link}\n\n"
        "リンクの有効期限は {minutes} 分です。\n"
        "確認しておくと、パスワードを忘れたときに再設定できます。",
    ),
    "ko": (
        "GoMuseum 이메일 확인",
        "아래 링크를 열어 이 이메일 주소를 확인하세요:\n\n{link}\n\n"
        "링크는 {minutes}분 동안 유효합니다.\n"
        "확인해 두면 나중에 비밀번호를 잊었을 때 재설정할 수 있습니다.",
    ),
}


# 落地页文案。**和邮件放同一个文件、共用同一套语言归一** ——
# 信是中文的、点开却是英文页面,是最容易出现又最没道理的一种割裂
# (2026-09-07 真机发现:邮件跟着语言走,页面永远是三语堆叠)。
#
# `html_lang` 进 <html lang>:屏幕阅读器和浏览器的翻译提示都看它。
_PAGE_COPY = {
    "en": {
        "html_lang": "en",
        "title": "Reset password · GoMuseum",
        "h1": "Set a new password",
        "sub": "Choose a new password for your GoMuseum account.",
        "label_new": "New password",
        "hint_min": "At least 8 characters",
        "label_repeat": "Repeat password",
        "button": "Confirm",
        "msg_mismatch": "The two passwords don't match.",
        "msg_short": "At least 8 characters.",
        "msg_ok": "Password updated — sign in with it in the app.",
        "msg_expired": "This link has expired or was already used. "
        "Please request a new one from the app.",
        "msg_error": "Something went wrong. Please try again.",
        "msg_network": "Network error.",
        "notice_expired_title": "Link no longer valid",
        "notice_expired_body": "This reset link has expired or was already used.\n"
        "Please request a new one from the app.",
        "notice_verified_title": "Email confirmed",
        "notice_verified_body": "Your email address is confirmed.\n"
        "You can close this page.",
        "notice_verify_expired_title": "Link no longer valid",
        "notice_verify_expired_body": "This link has expired or was already used.\n"
        "You can send a new one from the app's settings.",
    },
    "fr": {
        "html_lang": "fr",
        "title": "Réinitialiser le mot de passe · GoMuseum",
        "h1": "Définir un nouveau mot de passe",
        "sub": "Choisissez un nouveau mot de passe pour votre compte GoMuseum.",
        "label_new": "Nouveau mot de passe",
        "hint_min": "Au moins 8 caractères",
        "label_repeat": "Répéter le mot de passe",
        "button": "Confirmer",
        "msg_mismatch": "Les deux mots de passe ne correspondent pas.",
        "msg_short": "Au moins 8 caractères.",
        "msg_ok": "Mot de passe mis à jour — connectez-vous dans l'application.",
        "msg_expired": "Ce lien a expiré ou a déjà été utilisé. "
        "Veuillez en demander un nouveau depuis l'application.",
        "msg_error": "Un problème est survenu. Veuillez réessayer.",
        "msg_network": "Erreur réseau.",
        "notice_expired_title": "Lien non valide",
        "notice_expired_body": "Ce lien de réinitialisation a expiré "
        "ou a déjà été utilisé.\n"
        "Veuillez en demander un nouveau depuis l'application.",
        "notice_verified_title": "Adresse confirmée",
        "notice_verified_body": "Votre adresse e-mail est confirmée.\n"
        "Vous pouvez fermer cette page.",
        "notice_verify_expired_title": "Lien non valide",
        "notice_verify_expired_body": "Ce lien a expiré ou a déjà été utilisé.\n"
        "Vous pouvez en renvoyer un depuis les réglages de l'application.",
    },
    "zh": {
        "html_lang": "zh-CN",
        "title": "重设密码 · GoMuseum",
        "h1": "重设密码",
        "sub": "为你的 GoMuseum 账号设置一个新密码。",
        "label_new": "新密码",
        "hint_min": "至少 8 个字符",
        "label_repeat": "再输一次",
        "button": "确认",
        "msg_mismatch": "两次输入不一致。",
        "msg_short": "至少 8 个字符。",
        "msg_ok": "密码已更新，回 App 用新密码登录即可。",
        "msg_expired": "链接已失效或已用过，请回 App 重新申请。",
        "msg_error": "出了点问题，请稍后再试。",
        "msg_network": "网络错误。",
        "notice_expired_title": "链接已失效",
        "notice_expired_body": "这个重置链接已经过期或用过了。\n请回 App 重新申请一次。",
        "notice_verified_title": "邮箱已确认",
        "notice_verified_body": "你的邮箱地址已确认。\n可以关掉这个页面了。",
        "notice_verify_expired_title": "链接已失效",
        "notice_verify_expired_body": "这个确认链接已经过期或用过了。\n"
        "可以在 App 的设置里重新发送。",
    },
    "zh-hant": {
        "html_lang": "zh-Hant",
        "title": "重設密碼 · GoMuseum",
        "h1": "重設密碼",
        "sub": "為你的 GoMuseum 帳號設定一個新密碼。",
        "label_new": "新密碼",
        "hint_min": "至少 8 個字元",
        "label_repeat": "再輸入一次",
        "button": "確認",
        "msg_mismatch": "兩次輸入不一致。",
        "msg_short": "至少 8 個字元。",
        "msg_ok": "密碼已更新，回到 App 用新密碼登入即可。",
        "msg_expired": "連結已失效或已使用過，請回到 App 重新申請。",
        "msg_error": "發生了一點問題，請稍後再試。",
        "msg_network": "網路錯誤。",
        "notice_expired_title": "連結已失效",
        "notice_expired_body": "這個重設連結已經過期或使用過了。\n請回到 App 重新申請一次。",
        "notice_verified_title": "電子郵件已確認",
        "notice_verified_body": "你的電子郵件地址已確認。\n可以關閉這個頁面了。",
        "notice_verify_expired_title": "連結已失效",
        "notice_verify_expired_body": "這個確認連結已經過期或使用過了。\n"
        "可以在 App 的設定裡重新傳送。",
    },
    "de": {
        "html_lang": "de",
        "title": "Passwort zurücksetzen · GoMuseum",
        "h1": "Neues Passwort festlegen",
        "sub": "Wähle ein neues Passwort für dein GoMuseum-Konto.",
        "label_new": "Neues Passwort",
        "hint_min": "Mindestens 8 Zeichen",
        "label_repeat": "Passwort wiederholen",
        "button": "Bestätigen",
        "msg_mismatch": "Die beiden Passwörter stimmen nicht überein.",
        "msg_short": "Mindestens 8 Zeichen.",
        "msg_ok": "Passwort geändert — melde dich damit in der App an.",
        "msg_expired": "Dieser Link ist abgelaufen oder wurde bereits verwendet. "
        "Bitte fordere in der App einen neuen an.",
        "msg_error": "Etwas ist schiefgelaufen. Bitte versuche es erneut.",
        "msg_network": "Netzwerkfehler.",
        "notice_expired_title": "Link nicht mehr gültig",
        "notice_expired_body": "Dieser Link zum Zurücksetzen ist abgelaufen "
        "oder wurde bereits verwendet.\n"
        "Bitte fordere in der App einen neuen an.",
        "notice_verified_title": "E-Mail-Adresse bestätigt",
        "notice_verified_body": "Deine E-Mail-Adresse ist bestätigt.\n"
        "Du kannst diese Seite schließen.",
        "notice_verify_expired_title": "Link nicht mehr gültig",
        "notice_verify_expired_body": "Dieser Link ist abgelaufen "
        "oder wurde bereits verwendet.\n"
        "Du kannst in den Einstellungen der App einen neuen senden.",
    },
    "es": {
        "html_lang": "es",
        "title": "Restablecer contraseña · GoMuseum",
        "h1": "Crea una contraseña nueva",
        "sub": "Elige una contraseña nueva para tu cuenta de GoMuseum.",
        "label_new": "Contraseña nueva",
        "hint_min": "Al menos 8 caracteres",
        "label_repeat": "Repite la contraseña",
        "button": "Confirmar",
        "msg_mismatch": "Las dos contraseñas no coinciden.",
        "msg_short": "Al menos 8 caracteres.",
        "msg_ok": "Contraseña actualizada: inicia sesión con ella en la app.",
        "msg_expired": "Este enlace ha caducado o ya se ha usado. "
        "Solicita uno nuevo desde la app.",
        "msg_error": "Algo ha salido mal. Inténtalo de nuevo.",
        "msg_network": "Error de red.",
        "notice_expired_title": "El enlace ya no es válido",
        "notice_expired_body": "Este enlace de restablecimiento ha caducado "
        "o ya se ha usado.\n"
        "Solicita uno nuevo desde la app.",
        "notice_verified_title": "Correo confirmado",
        "notice_verified_body": "Tu dirección de correo está confirmada.\n"
        "Ya puedes cerrar esta página.",
        "notice_verify_expired_title": "El enlace ya no es válido",
        "notice_verify_expired_body": "Este enlace ha caducado o ya se ha usado.\n"
        "Puedes enviar uno nuevo desde los ajustes de la app.",
    },
    "it": {
        "html_lang": "it",
        "title": "Reimposta password · GoMuseum",
        "h1": "Imposta una nuova password",
        "sub": "Scegli una nuova password per il tuo account GoMuseum.",
        "label_new": "Nuova password",
        "hint_min": "Almeno 8 caratteri",
        "label_repeat": "Ripeti la password",
        "button": "Conferma",
        "msg_mismatch": "Le due password non coincidono.",
        "msg_short": "Almeno 8 caratteri.",
        "msg_ok": "Password aggiornata: accedi con la nuova password nell'app.",
        "msg_expired": "Questo link è scaduto o è già stato usato. "
        "Richiedine uno nuovo dall'app.",
        "msg_error": "Si è verificato un problema. Riprova.",
        "msg_network": "Errore di rete.",
        "notice_expired_title": "Link non più valido",
        "notice_expired_body": "Questo link di ripristino è scaduto "
        "o è già stato usato.\n"
        "Richiedine uno nuovo dall'app.",
        "notice_verified_title": "E-mail confermata",
        "notice_verified_body": "Il tuo indirizzo e-mail è confermato.\n"
        "Puoi chiudere questa pagina.",
        "notice_verify_expired_title": "Link non più valido",
        "notice_verify_expired_body": "Questo link è scaduto o è già stato usato.\n"
        "Puoi inviarne uno nuovo dalle impostazioni dell'app.",
    },
    "pl": {
        "html_lang": "pl",
        "title": "Resetowanie hasła · GoMuseum",
        "h1": "Ustaw nowe hasło",
        "sub": "Wybierz nowe hasło do swojego konta GoMuseum.",
        "label_new": "Nowe hasło",
        "hint_min": "Co najmniej 8 znaków",
        "label_repeat": "Powtórz hasło",
        "button": "Potwierdź",
        "msg_mismatch": "Hasła nie są takie same.",
        "msg_short": "Co najmniej 8 znaków.",
        "msg_ok": "Hasło zmienione — zaloguj się nim w aplikacji.",
        "msg_expired": "Ten link wygasł lub został już użyty. "
        "Poproś o nowy w aplikacji.",
        "msg_error": "Coś poszło nie tak. Spróbuj ponownie.",
        "msg_network": "Błąd sieci.",
        "notice_expired_title": "Link jest już nieważny",
        "notice_expired_body": "Ten link do resetowania hasła wygasł "
        "lub został już użyty.\n"
        "Poproś o nowy w aplikacji.",
        "notice_verified_title": "Adres e-mail potwierdzony",
        "notice_verified_body": "Twój adres e-mail został potwierdzony.\n"
        "Możesz zamknąć tę stronę.",
        "notice_verify_expired_title": "Link jest już nieważny",
        "notice_verify_expired_body": "Ten link wygasł lub został już użyty.\n"
        "Nowy możesz wysłać w ustawieniach aplikacji.",
    },
    "ja": {
        "html_lang": "ja",
        "title": "パスワード再設定 · GoMuseum",
        "h1": "新しいパスワードを設定",
        "sub": "GoMuseum アカウントの新しいパスワードを設定してください。",
        "label_new": "新しいパスワード",
        "hint_min": "8 文字以上",
        "label_repeat": "もう一度入力",
        "button": "確定",
        "msg_mismatch": "2 つのパスワードが一致しません。",
        "msg_short": "8 文字以上で入力してください。",
        "msg_ok": "パスワードを更新しました。アプリで新しいパスワードを使ってログインしてください。",
        "msg_expired": "このリンクは期限切れか、すでに使用されています。"
        "アプリからもう一度リクエストしてください。",
        "msg_error": "問題が発生しました。もう一度お試しください。",
        "msg_network": "ネットワークエラー。",
        "notice_expired_title": "リンクは無効です",
        "notice_expired_body": "この再設定リンクは期限切れか、すでに使用されています。\n"
        "アプリからもう一度リクエストしてください。",
        "notice_verified_title": "メールアドレスを確認しました",
        "notice_verified_body": "メールアドレスの確認が完了しました。\n"
        "このページは閉じてかまいません。",
        "notice_verify_expired_title": "リンクは無効です",
        "notice_verify_expired_body": "この確認リンクは期限切れか、すでに使用されています。\n"
        "アプリの設定から再送信できます。",
    },
    "ko": {
        "html_lang": "ko",
        "title": "비밀번호 재설정 · GoMuseum",
        "h1": "새 비밀번호 설정",
        "sub": "GoMuseum 계정에 사용할 새 비밀번호를 정하세요.",
        "label_new": "새 비밀번호",
        "hint_min": "8자 이상",
        "label_repeat": "비밀번호 다시 입력",
        "button": "확인",
        "msg_mismatch": "두 비밀번호가 일치하지 않습니다.",
        "msg_short": "8자 이상 입력하세요.",
        "msg_ok": "비밀번호가 변경되었습니다. 앱에서 새 비밀번호로 로그인하세요.",
        "msg_expired": "링크가 만료되었거나 이미 사용되었습니다. "
        "앱에서 다시 요청하세요.",
        "msg_error": "문제가 발생했습니다. 다시 시도하세요.",
        "msg_network": "네트워크 오류입니다.",
        "notice_expired_title": "더 이상 유효하지 않은 링크",
        "notice_expired_body": "이 재설정 링크는 만료되었거나 이미 사용되었습니다.\n"
        "앱에서 다시 요청하세요.",
        "notice_verified_title": "이메일 확인 완료",
        "notice_verified_body": "이메일 주소가 확인되었습니다.\n"
        "이 페이지를 닫아도 됩니다.",
        "notice_verify_expired_title": "더 이상 유효하지 않은 링크",
        "notice_verify_expired_body": "이 확인 링크는 만료되었거나 이미 사용되었습니다.\n"
        "앱 설정에서 다시 보낼 수 있습니다.",
    },
}


def page_copy(code: Optional[str]) -> dict:
    """按语言取落地页文案。认不出一律英文,和邮件同一条回落规则。"""
    return _PAGE_COPY[resolve_lang(code)]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """SQLite 不存时区,Postgres 存。naive 一律按 UTC 解读(服务端时间为准)。"""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=timezone.utc)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def resolve_lang(code: Optional[str]) -> str:
    """把 `zh-Hans` / `fr_FR` / `zh-TW,zh;q=0.9` 这类归一到 SUPPORTED_LANGS 之一。

    也吃 `Accept-Language` 整个头(逗号分隔、带 q 值),取第一项即可 ——
    没带 `lang` 的老链接就靠它兜底。
    """
    if not code:
        return DEFAULT_LANG
    first = code.split(",")[0].split(";")[0].strip()
    parts = first.replace("_", "-").lower().split("-")
    base = parts[0]
    if base == "zh":
        rest = parts[1:]
        if "hant" in rest or (
            "hans" not in rest and any(r in _HANT_REGIONS for r in rest)
        ):
            return "zh-hant"
    return base if base in SUPPORTED_LANGS else DEFAULT_LANG


def issue(db, user_id: str, purpose: str, ttl_minutes: int) -> str:
    """签发一张一次性令牌,返回**明文**(只有这一次能拿到,库里只有哈希)。

    同一用户同一用途下**尚未使用的旧令牌一并作废**:重发之后旧链接还能用的话,
    用户收件箱里就积着好几把有效钥匙,而他以为只有最新那封算数。
    """
    db.query(AuthToken).filter(
        AuthToken.user_id == user_id,
        AuthToken.purpose == purpose,
        AuthToken.used_at.is_(None),
    ).update({"used_at": _now()}, synchronize_session=False)

    token = secrets.token_urlsafe(32)
    db.add(
        AuthToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=_digest(token),
            expires_at=_now() + timedelta(minutes=ttl_minutes),
        )
    )
    db.commit()
    return token


def peek(db, token: str, purpose: str) -> Optional[AuthToken]:
    """令牌可用就返回它,否则 None。**不消费** —— 给"先渲染页面"用。"""
    row = (
        db.query(AuthToken)
        .filter(
            AuthToken.token_hash == _digest(token),
            AuthToken.purpose == purpose,
        )
        .one_or_none()
    )
    if row is None or row.used_at is not None:
        return None
    expires = _aware(row.expires_at)
    return None if expires is not None and expires <= _now() else row


def consume(db, token: str, purpose: str) -> Optional[AuthToken]:
    """核销令牌。成功返回该行,并**当场标记已用**。"""
    row = peek(db, token, purpose)
    if row is None:
        return None
    row.used_at = _now()
    db.commit()
    return row


def _link(base_url: Optional[str], path: str, token: str, lang: str) -> str:
    """链接**必须带上语言**。

    落地页是服务端渲染的,它除了这条 URL 没有任何别的途径知道用户在用哪种语言:
    邮件是在 App 里发起的(那时知道语言),点开链接却是在系统浏览器里,
    既没有 App 的登录态也没有它的语言设置。
    不带的话就只能猜浏览器的 `Accept-Language` —— 而那是**手机系统语言**,
    未必等于用户在 App 里选的语言(这两者经常不一致,正是本项目做「跟随系统」
    选项的原因)。
    """
    base = (getattr(settings, "PUBLIC_API_BASE_URL", None) or base_url or "").rstrip(
        "/"
    )
    return f"{base}{path}?token={quote(token)}&lang={lang}"


# ────────────────────────────────────────────────────────────── 找回密码


def request_password_reset(db, email: str, *, base_url=None, language=None) -> None:
    """发一封重置信。**无论结果如何都不告诉调用方账号存不存在。**

    抛 MailNotConfigured / MailSendFailed 表示"信确实没发出去" ——
    那必须让用户看见,而它与"这个邮箱没注册过"是两回事,不会泄漏账号存在与否
    (因为不存在的邮箱压根不会走到发信这一步)。
    """
    user = db.query(User).filter(User.email == email).one_or_none()
    if user is None or user.is_guest or not user.is_active:
        return
    if not user.password_hash:
        # 纯 OAuth 账号。给它发重置 = 凭一封邮件新造一把绕过 Google 二步验证的
        # 钥匙,把账号安全降到"邮箱有多安全",而用户从没要求过。他有能用的登录方式。
        logger.info("password reset skipped for OAuth-only account")
        return

    ttl = settings.PASSWORD_RESET_TTL_MINUTES
    token = issue(db, str(user.id), PURPOSE_PASSWORD_RESET, ttl)
    lang = resolve_lang(language)
    subject, body = _RESET_MAIL[lang]
    mailer.send(
        user.email,
        subject,
        body.format(
            link=_link(base_url, "/api/v1/auth/reset", token, lang), minutes=ttl
        ),
    )


def confirm_password_reset(db, token: str, new_password: str) -> bool:
    """核销令牌并改密码。令牌无效/过期/用过 → False。"""
    row = consume(db, token, PURPOSE_PASSWORD_RESET)
    if row is None:
        return False
    import uuid as _uuid

    try:
        uid = _uuid.UUID(row.user_id)
    except ValueError:
        return False
    user = db.query(User).filter(User.id == uid).one_or_none()
    if user is None or not user.is_active:
        return False
    user.password_hash = hash_password(new_password)
    # 走到这一步说明他确实收得到这个邮箱的信 —— 顺带把邮箱标成已验证,
    # 省掉一次毫无意义的二次确认。
    if not user.is_verified:
        user.is_verified = True
        user.email_verified_at = datetime.utcnow()
    db.commit()
    return True


# ────────────────────────────────────────────────────────────── 邮箱验证


def request_email_verification(db, user: User, *, base_url=None, language=None) -> bool:
    """发一封验证信。没邮箱/已验证/未配置发信 → False(调用方按"没发"处理)。

    ⚠️ **注册时调用它绝不能让注册失败**:发信是锦上添花,注册是主线。
    """
    if not user.email or user.is_guest or user.is_verified:
        return False
    if not mailer.is_configured():
        return False
    ttl = settings.EMAIL_VERIFY_TTL_MINUTES
    token = issue(db, str(user.id), PURPOSE_EMAIL_VERIFY, ttl)
    lang = resolve_lang(language)
    subject, body = _VERIFY_MAIL[lang]
    try:
        mailer.send(
            user.email,
            subject,
            body.format(
                link=_link(base_url, "/api/v1/auth/verify-email", token, lang),
                minutes=ttl,
            ),
        )
    except mailer.MailSendFailed:
        return False
    return True


def confirm_email_verification(db, token: str) -> bool:
    row = consume(db, token, PURPOSE_EMAIL_VERIFY)
    if row is None:
        return False
    import uuid as _uuid

    try:
        uid = _uuid.UUID(row.user_id)
    except ValueError:
        return False
    user = db.query(User).filter(User.id == uid).one_or_none()
    if user is None:
        return False
    user.is_verified = True
    user.email_verified_at = datetime.utcnow()
    db.commit()
    return True
