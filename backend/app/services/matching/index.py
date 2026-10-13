"""倒排索引:在搜索全局索引条目之上建 标题词/作者词 → 条目下标,召回只碰相关的几百件。

prod 10-07:26 万个名字逐个 difflib 一次 15–300s;倒排召回 + 精排 prod 主机 p50 0.23s。
倒排随搜索索引在后台线程里一起建好(prod 主机 4.5s),请求线程不碰冷建。"""

from __future__ import annotations

import bisect
import collections
import math
import threading

from rapidfuzz import process
from rapidfuzz.distance import OSA

from app.services.matching.normalize import is_cjk, tokens

_FUZZY_MIN = 4  # 拉丁词 ≥4 字母才容错
_PREFIX_MIN = 2
_SEP = "\x00"  # normalize 把控制符换成空格,名字里不会出现


class _Blob:
    """某字段全部名字拼成一条大串("\x00名1\x00名2…"),子串查找交给 C 层 str.find,
    语义与逐件 `q in n` / `n.startswith(q)` 完全一致(搜索分档召回,原来逐件扫 2.7 万件 ~170ms)。"""

    def __init__(self, entries: list[dict], key: str):
        parts: list[str] = []
        self.starts: list[int] = []  # 每个名字前 _SEP 的偏移
        self.owner: list[int] = []  # 该名字属于哪个条目下标
        off = 0
        for i, e in enumerate(entries):
            for n in sorted(e[key]):
                self.starts.append(off)
                self.owner.append(i)
                parts.append(_SEP + n)
                off += len(n) + 1
        self.starts.append(off)  # 哨兵:末名字的结尾
        self.text = "".join(parts)

    def hits(self, q: str) -> dict[int, bool]:
        """q 出现在哪些条目的名字里 → {条目下标: 是否某个名字以 q 开头}。"""
        out: dict[int, bool] = {}
        if not q or _SEP in q:
            return out
        text, starts, owner = self.text, self.starts, self.owner
        j = text.find(q)
        while j != -1:
            k = bisect.bisect_right(starts, j) - 1
            i = owner[k]
            pre = j == starts[k] + 1
            out[i] = out.get(i, False) or pre
            # 同一名字只看首次出现(前缀只可能是首次),直接跳到下个名字
            j = text.find(q, starts[k + 1])
        return out


class Core:
    def __init__(self, entries: list[dict]):
        self.entries = entries
        self.pos = {id(e): i for i, e in enumerate(entries)}
        post: dict[str, dict[str, set[int]]] = {
            "title": collections.defaultdict(set),
            "artist": collections.defaultdict(set),
        }
        self.title_df: collections.Counter = collections.Counter()
        for i, e in enumerate(entries):
            for n in e["names"]:
                self.title_df[n] += 1
                for t in tokens(n):
                    post["title"][t].add(i)
            for a in e["artists"]:
                for t in tokens(a):
                    post["artist"][t].add(i)
        n = max(len(entries), 1)
        # ponytail: 倒排用 list 省内存;若 prod 每 worker 超 300MB 再换 array('I')
        self.post = {f: {t: sorted(s) for t, s in p.items()} for f, p in post.items()}
        self.idf = {
            f: {t: math.log(n / len(s)) for t, s in p.items()}
            for f, p in self.post.items()
        }
        self.vocab = {f: sorted(p) for f, p in self.post.items()}
        # OSA 距离 ≥ 长度差 → 容错只需比长度差 ≤k 的词;按长度分桶(桶内保持字母序)
        self.by_len: dict[str, dict[int, list[str]]] = {}
        for f, words in self.vocab.items():
            b: dict[int, list[str]] = collections.defaultdict(list)
            for w in words:
                b[len(w)].append(w)
            self.by_len[f] = b
        self.by_inv: dict[str, list[int]] = collections.defaultdict(list)
        for i, e in enumerate(entries):
            if e.get("inv"):
                self.by_inv[e["inv"]].append(i)
        self.blobs = {
            "title": _Blob(entries, "names"),
            "artist": _Blob(entries, "artists"),
        }

    def substr(self, field: str, q: str) -> dict[int, bool]:
        """field 里含 q 的条目 → {下标: 是否前缀}(搜索分档用)。"""
        return self.blobs[field].hits(q)

    def expand(self, tok: str, field: str, prefix: bool = False) -> dict[str, float]:
        """查询词 → {库词: 相似度 0–1}。精确 1.0;拉丁 ≥4 字母按 OSA 容错;prefix=搜索框末词。"""
        post, vocab = self.post[field], self.vocab[field]
        out: dict[str, float] = {}
        if tok in post:
            out[tok] = 1.0
        if len(tok) >= _FUZZY_MIN and not is_cjk(tok):
            k = 1 if len(tok) < 7 else 2
            b = self.by_len[field]
            # 合并后重排回字母序:同距离并列时 limit=8 取到的词与扫全词表一致
            near = sorted(
                w for n in range(len(tok) - k, len(tok) + k + 1) for w in b.get(n, ())
            )
            for v, d, _ in process.extract(
                tok, near, scorer=OSA.distance, score_cutoff=k, limit=8
            ):
                out[v] = max(out.get(v, 0.0), 1 - d / max(len(tok), len(v)))
        if prefix and len(tok) >= _PREFIX_MIN:
            j = bisect.bisect_left(vocab, tok)
            while j < len(vocab) and vocab[j].startswith(tok):
                if vocab[j] != tok:
                    out[vocab[j]] = max(out.get(vocab[j], 0.0), 0.9)
                j += 1
        return out

    def _token_hits(self, tok, fields, prefix, allowed) -> dict[int, float]:
        best: dict[int, float] = {}
        for f in fields:
            idf = self.idf[f]
            for v, s in self.expand(tok, f, prefix).items():
                w = s * idf[v]
                for i in self.post[f][v]:
                    if (allowed is None or i in allowed) and w >= best.get(i, 0.0):
                        best[i] = w  # >=:idf=0 的词(每件都有)也算命中
        return best

    def recall(self, qtoks, k=200, allowed=None, use_artist=False):
        """各词加权分累加 → 前 k 个 (下标, 分)。识别用(不要求每词都中)。"""
        fields = ("title", "artist") if use_artist else ("title",)
        acc: dict[int, float] = collections.defaultdict(float)
        for t in qtoks:
            for i, w in self._token_hits(t, fields, False, allowed).items():
                acc[i] += w
        return sorted(acc.items(), key=lambda kv: -kv[1])[:k]

    def and_hits(self, qtoks, allowed=None) -> dict[int, float]:
        """搜索用:每个词都要在标题或作者里命中(末词前缀)→ {下标: 加权分}。"""
        acc: dict[int, float] | None = None
        for j, t in enumerate(qtoks):
            hits = self._token_hits(
                t, ("title", "artist"), j == len(qtoks) - 1, allowed
            )
            if acc is None:
                acc = hits
            else:
                acc = {i: acc[i] + w for i, w in hits.items() if i in acc}
            if not acc:
                return {}
        return acc or {}


_cores: collections.OrderedDict = collections.OrderedDict()  # id(index) → (index, Core)
_pinned: tuple | None = None  # (全局索引, 它的倒排):不参与淘汰
_lock = threading.Lock()


def get_core(index: list[dict], pin: bool = False) -> Core:
    """pin=True:全局索引的倒排(_warm_core 调用),单独钉住——刷新竞态时子集临时建的倒排
    只进 2 槽 LRU,挤不掉它(否则下个请求要重建,prod 4.5s)。"""
    global _pinned
    with _lock:
        if _pinned and _pinned[0] is index:
            return _pinned[1]
        hit = _cores.get(id(index))
        if hit and hit[0] is index:
            if pin:
                _pinned = hit
            return hit[1]
    core = Core(index)
    with _lock:
        if pin:
            _pinned = (index, core)
        else:
            _cores[id(index)] = (index, core)  # 持有 index 引用,id 不会被复用
            while len(_cores) > 2:
                _cores.popitem(last=False)
    return core


def core_for(index: list[dict]) -> tuple[Core, set[int] | None]:
    """全局索引 → (全局倒排, None);其子集(馆域/可见性过滤,同一批 dict)→ (全局倒排, 允许下标);
    其它列表 → 单建并缓存:测试自建的列表,或后台刷新刚把全局索引换掉时、请求手里还是旧索引
    的子集(极窄窗口,结果仍正确,只是这一次慢)。"""
    from app.services.search.inprocess import _index_cache

    hit = _index_cache.get(None)
    g = hit[1] if hit else None
    if g is not None and index is not g:
        gcore = get_core(g)
        pos = gcore.pos
        allowed = {pos[id(e)] for e in index if id(e) in pos}
        if len(allowed) == len(index):
            return gcore, allowed
    return get_core(index), None
