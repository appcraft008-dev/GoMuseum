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
