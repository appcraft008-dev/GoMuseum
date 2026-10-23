"""网站自记统计与下载链接(spec 2026-10-22-website-v1 §七/§八)。不设 cookie、不存个人信息。"""

from app.core.config import settings
from app.services.share import is_bot

PLAY_BASE = "https://play.google.com/store/apps/details?id=com.gomuseum.app"


def device_class(ua: str) -> str:
    """iphone / ipad / android / desktop / bot。只用于统计与下载区分支。"""
    if is_bot(ua or ""):
        return "bot"
    if "iPad" in ua:
        return "ipad"
    if "iPhone" in ua:
        return "iphone"
    if "Android" in ua:
        return "android"
    return "desktop"


def play_url(page_type: str) -> str | None:
    """正式版过审前(SHARE_PLAY_LIVE=false)Play 链接对外人打不开 → 不给。"""
    if not settings.SHARE_PLAY_LIVE:
        return None
    return (
        f"{PLAY_BASE}&referrer=utm_source%3Dgomuseum.app%26utm_medium%3Dweb"
        f"%26utm_content%3D{page_type}"
    )


BEACON_NAMES = frozenset(
    {"web_download_click", "web_trial_play", "web_trial_complete", "web_share_click"}
)
BEACON_MAX_BYTES = 2048


def internal_referrer(referer: str) -> bool:
    """来自本站另一页 = 同一次访问里的「下一页」。每次访问看几页 = 总访问数 / 非站内来源数。"""
    if not referer:
        return False
    host = settings.PUBLIC_WEB_BASE_URL.split("://", 1)[-1].rstrip("/")
    return referer.split("://", 1)[-1].split("/", 1)[0] == host


def qr_data_uri(url: str) -> str:
    """电脑访客用安卓手机扫码下载(复用分享图已在用的 segno)。"""
    import segno

    return segno.make(url, error="m").svg_data_uri(scale=4, border=2)


def log_page_view(db, request, *, lang, page_type, museum_slug=None, qid=None):
    from app.services.event_log import log_event

    ua = request.headers.get("user-agent", "")
    if is_bot(ua):  # 爬虫全站扫一遍就是上万行写入;统计只要真人
        return
    log_event(
        db,
        "web_page_view",
        museum_slug=museum_slug,
        qid=qid,
        lang=lang,
        page_type=page_type,
        device=device_class(ua),
        internal_ref=internal_referrer(request.headers.get("referer", "")),
        bot=is_bot(ua),
    )
