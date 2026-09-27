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


# ---- 签名过滤:看完图之后删掉转写了作者签名的句子 --------------------------
# 下面的描述原文都取自 prod(2026-09-27)。分类器用假的,钉住的是「判了之后删什么、
# 留什么」;分类器本身的判断力在 prod 全部 6 条带转写的描述上实测过(见 vision.py 注释)。


def _clf(answers):
    seen = []

    def classify(names, quoted):
        seen.append((names, quoted))
        return [answers[q] for q in quoted]

    return classify, seen


def test_strips_the_sentence_carrying_a_latinized_signature():
    """齐马《圣母子》:字条上的「IOANNES B」被当成铭文转写,下游 guide 写成
    「铭文暗示了艺术家的身份」。整句删掉,其它观察一句不少。"""
    text = (
        "Both figures have halos around their heads. "
        'At the bottom of the painting, the inscription "IOANNES B" is visible. '
        "The sky is partly cloudy."
    )
    classify, seen = _clf({"IOANNES B": True})
    out = vision.strip_signatures(text, ["Cima da Conegliano"], classify)
    assert "IOANNES" not in out
    assert (
        out == "Both figures have halos around their heads. The sky is partly cloudy."
    )
    assert seen == [(["Cima da Conegliano"], ["IOANNES B"])]


def test_keeps_scripture_and_motto_inscriptions():
    """对照组:作品上的经文/题字是**要**转写的(《Credo》教训),不能跟着签名一起删。
    句号在引号里面(「…PECCATA." The child…」)—— 断句要在引号后断开,
    否则删一句会连带吃掉下一句。"""
    text = (
        'A scroll reads "ECCE AGNUS DEI ECCE QUI TOLLIT PECCATA." '
        "The child points towards the central figure."
    )
    classify, _ = _clf({"ECCE AGNUS DEI ECCE QUI TOLLIT PECCATA.": False})
    assert vision.strip_signatures(text, ["Andrea Mantegna"], classify) == text


def test_lone_year_is_a_signing_date_without_asking_the_model():
    """克莱兰:单独一个「1876」模型判「不是签名」,但它就是落款年份 —— 代码直接删。"""
    text = 'The dog rests on a cushion. The number "1876" appears in the lower right.'

    def classify(names, quoted):
        raise AssertionError("纯年份不该送去问模型")

    out = vision.strip_signatures(text, ["Georges Clairin"], classify)
    assert out == "The dog rests on a cushion."


def test_classifier_failure_keeps_the_description():
    """判不出来 → 原样保留。签名漏网是老行为;为这一步失败丢掉整段视觉描述,
    那一件就回到脑补外观的状态,更糟。"""
    text = 'An inscription reads "Gustave Courbet 1842." The dog is black.'

    def boom(names, quoted):
        raise RuntimeError("openai down")

    assert vision.strip_signatures(text, ["Gustave Courbet"], boom) == text


def test_description_without_quotes_skips_the_artist_lookup(monkeypatch):
    """没有引号转写(绝大多数)→ 不查作者、不调模型。"""
    _patch(monkeypatch, desc="A donkey grazes.")
    monkeypatch.setattr(
        vision, "_artist_names", lambda db, o: (_ for _ in ()).throw(AssertionError)
    )
    o = _obj({})
    assert vision.ensure_description(_DB(), o) is True
    assert o.attributes[vision.KEY] == "A donkey grazes."


def test_ensure_description_strips_signature_before_saving(monkeypatch):
    _patch(monkeypatch, desc='A black dog. An inscription reads "G. Courbet 1842."')
    monkeypatch.setattr(vision, "_artist_names", lambda db, o: ["Gustave Courbet"])
    monkeypatch.setattr(vision, "_classify_signatures", lambda n, q: [True])
    o = _obj({})
    vision.ensure_description(_DB(), o)
    assert o.attributes[vision.KEY] == "A black dog."
