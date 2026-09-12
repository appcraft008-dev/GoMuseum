"""从 prod API 取待念正文(只读)。**唯一实现** —— 跑批与预检共用这一份。

单独成模块的理由:这段逻辑在实验室脚本里被抄过两遍,而它踩过的坑
(`tabs` 里的字段名是 `section_code` 不是 `code`、artist_bio 要 `via_qid`)
是**静默**的 —— 抄错只会让整类段落被判成"无文本,跳过",看起来像内容缺失。
抄一份就多一处能独立走样的地方,所以只留一份。

导入它不需要 voxcpm/librosa/mlx_whisper 那套重依赖(run_batch.py 需要),
预检、比对工具都能直接 import。
"""

import os

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API = os.environ.get("GOMUSEUM_API", "https://api.gomuseum.app/api/v1")

# 取文本的 HTTP 会话:对网关错误自动重试。prod 部署会 recreate 容器,窗口里
# Nginx 返 502 —— 实测一次 502 就把跑了 4 小时的批次整个掐断(run_chunked.sh
# 是 set -e,一个 python 非零退出就中止整轮)。用 urllib3 自带的重试策略,
# 不自己写重试分支:它只重试 502/503/504 与连接错误,4xx(内容真的没有)照常上抛。
_HTTP = requests.Session()
_HTTP.mount(
    "https://",
    HTTPAdapter(
        max_retries=Retry(
            total=5,
            backoff_factor=5,  # 退避 5→10→20→40s,足够跨过一次部署窗口
            status_forcelist=(502, 503, 504),
            allowed_methods=("GET",),
        )
    ),
)

_cache: dict[tuple, dict] = {}


def content(museum, via_qid, language, use_cache=False):
    """取一件作品的 /content 响应。[use_cache] 给预检用(同一件多段共享一次请求)。"""
    k = (museum, via_qid, language)
    if use_cache and k in _cache:
        return _cache[k]
    r = _HTTP.get(
        f"{API}/museums/{museum}/objects/{via_qid}/content",
        params={"language": language},
        timeout=30,
    )
    r.raise_for_status()
    d = r.json()
    if use_cache:
        _cache[k] = d
    return d


def pick_section(d, sec):
    """从 /content 响应里挑出某一段的正文。取不到返回 None。"""
    if sec == "artist_bio":
        return ((d.get("artist") or {}).get("bio")) or None
    if sec.startswith("qa_"):
        idx = int(sec.split("_", 1)[1])
        for q in d.get("suggested_questions") or []:
            if q.get("sort") == idx:
                # QA 按'问+答'拼接,与后端质量闸取文本方式一致(分开念会内容对不上)
                return f"{q['question']}\n\n{q['answer']}"
        return None
    if sec == "guide":
        return ((d.get("default_guide") or {}).get("body")) or None
    for t in d.get("tabs") or []:
        # 🔴 字段名是 section_code,不是 code。第1批只做 guide(走 default_guide),
        # 从没走到这一行 —— 于是 t.get("code") 恒为 None,深度段会**全部**被判
        # "无文本,跳过",而且状态里写的是 no_text,看起来像内容缺失而不是 bug。
        if t.get("section_code") == sec:
            return t.get("body")
    return None


def fetch_text(job, use_cache=False):
    """按一条 job 取正文。

    ⚠️ artist_bio 的 job["qid"] 是**作者 qid**,而 bio 正文挂在作品的 content
    响应上 —— 所以这类 job 必须额外带一个 job["via_qid"](该作者名下任一作品)。
    """
    via = job.get("via_qid", job["qid"])
    d = content(job["museum"], via, job["language"], use_cache=use_cache)
    return pick_section(d, job["section"])
