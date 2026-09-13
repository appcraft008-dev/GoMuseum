"""懒生成路径上的看图:钉住"什么时候看、什么时候不看、看失败了怎么办"。

这一层的每种错法都是**静默**的:
- 该看没看 → 材料照旧没有视觉信息,正文照写、闸照过,只是内容是编的;
- 不该看又看了 → 每次重生成都重付 $0.0044 + 3.6s,账单上才看得出来;
- 看失败写了个标记 → 这件**永远**不会再重试,而它看起来和成功的一样。
"""

from types import SimpleNamespace

from app.services.enrichment import vision


def _obj(attrs=None):
    return SimpleNamespace(qid="Q1", attributes=attrs, _flagged=False)


class _DB:
    def __init__(self):
        self.flushed = 0

    def flush(self):
        self.flushed += 1


def _patch(
    monkeypatch, url="https://cdn.example/images/Q1/0_large.jpg", desc="A donkey."
):
    calls = []

    def fake_describe(u, **kw):
        calls.append(u)
        if isinstance(desc, Exception):
            raise desc
        return desc

    monkeypatch.setattr(vision, "primary_image_url", lambda db, o: url)
    monkeypatch.setattr(vision, "describe_image", fake_describe)
    monkeypatch.setattr("sqlalchemy.orm.attributes.flag_modified", lambda o, k: None)
    return calls


def test_writes_description_and_provenance_when_missing(monkeypatch):
    calls = _patch(monkeypatch)
    o = _obj({"medium_fr": "huile"})
    assert vision.ensure_description(_DB(), o) is True
    assert len(calls) == 1
    assert o.attributes[vision.KEY] == "A donkey."
    assert o.attributes[vision.VIA_KEY] == f"{vision.MODEL}/{vision.DETAIL}"
    assert o.attributes["medium_fr"] == "huile", "不能把原有属性冲掉"


def test_skips_when_already_described(monkeypatch):
    """幂等 —— 描述是**一次性**成本。

    漏掉这条不会报错,只会让每次 --force 重生成都重看一遍图:
    正文这辈子要重生成好几次(改 prompt/修闸/补语种),那就是几倍的钱。
    """
    calls = _patch(monkeypatch)
    o = _obj({vision.KEY: "已经看过了"})
    assert vision.ensure_description(_DB(), o) is False
    assert calls == [], "已有描述还去看图 = 重复付费"


def test_skips_when_there_is_no_image(monkeypatch):
    """没有本地图就不看 —— 小皇宫 45%、卢浮宫 40% 属于这种,它们走不了这条路。"""
    calls = _patch(monkeypatch, url=None)
    assert vision.ensure_description(_DB(), _obj({})) is False
    assert calls == []


def test_failure_does_not_block_generation(monkeypatch):
    """视觉调用挂了 → 退回老行为,用户照样看得到讲解,不能整件生成失败。"""
    _patch(monkeypatch, desc=RuntimeError("openai down"))
    o = _obj({})
    assert vision.ensure_description(_DB(), o) is False


def test_failure_leaves_the_key_absent_so_it_retries_later(monkeypatch):
    """失败**不留标记**。

    若失败时写个 `visual_via: failed` 之类的标记,这件就永远跳过重试了 ——
    而它在库里看起来和成功的件一模一样,没人会发现。键缺着,
    下次批跑或重生成自然会再试。
    """
    _patch(monkeypatch, desc=RuntimeError("boom"))
    o = _obj({"medium_fr": "huile"})
    vision.ensure_description(_DB(), o)
    assert vision.KEY not in (o.attributes or {})
    assert vision.VIA_KEY not in (o.attributes or {})


def test_handles_attributes_being_none(monkeypatch):
    """存量行的 attributes 可能是 NULL。"""
    _patch(monkeypatch)
    o = _obj(None)
    assert vision.ensure_description(_DB(), o) is True
    assert o.attributes[vision.KEY] == "A donkey."


def test_pipeline_looks_at_the_image_before_it_builds_the_material():
    """调用点必须在 build_material **之前**。

    挪到后面 = 描述写进了库,但这一轮的材料包里没有它 —— 正文依旧是编的,
    而且**一个报错都不会有**,库里还多了一条看起来成功的描述。
    源码顺序断言不优雅,但这个错法没有别的抓法。
    """
    import inspect

    from app.services.enrichment import pipeline

    src = inspect.getsource(pipeline.generate_object)
    i_vision = src.index("ensure_description(db, o)")
    i_material = src.index("material = build_material(obj)")
    assert i_vision < i_material, "ensure_description 必须在 build_material 之前调用"
