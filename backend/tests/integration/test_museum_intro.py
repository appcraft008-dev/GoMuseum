"""馆介绍生成:按语言幂等补缺/gate失败不落/无材料skip;封面:否决件跳过选下一件。"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.museum_intro import generate_museum_intro, select_cover
from app.services.enrichment.quality import SectionQuality
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[Museum.__table__, MuseumObject.__table__, ObjectImage.__table__],
    )
    s = sessionmaker(bind=engine)()
    upsert_museum(s, {"slug": "orsay", "name_en": "Orsay", "qid": "Q23402"})
    s.commit()
    yield s


class _Gate:
    def __init__(self, ok=True):
        self.ok = ok

    def check_section(self, material, facts, body):
        return SectionQuality(
            body=body if self.ok else None,
            status="published" if self.ok else "needs_review",
            grounding_ratio=1.0,
            conflicts=[],
            score=1.0,
        )


class _Tr:
    def translate_section(self, body, lang, **kw):
        return f"{lang}:{body}"


def _mat(qid, **kw):
    return {"extract_en": "Housed in a 1900 railway station..."}


def test_generates_en_and_fills_langs(session):
    # LLM 返回固定三具名字段JSON(数组约束力不够,staging两轮实测3/3被合并成单段
    # 后改用具名必填字段——见 museum_intro.py 注释)
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: (
            '{"history": "Para one.", "highlights": "Para two.", '
            '"invitation": "Para three."}'
        ),
        gate=_Gate(),
        translator=_Tr(),
        langs=["en", "zh", "ja"],
        fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert m.description_i18n["en"] == "Para one.\n\nPara two.\n\nPara three."
    assert m.description_i18n["zh"].startswith("zh:")
    assert out["generated"] is True and set(out["translated"]) == {"zh", "ja"}


def test_generate_json_parse_failure_writes_nothing(session):
    # 模型没按JSON格式回(自由文本/坏JSON)→ 当生成失败,不落半成品(宁缺毋滥,重跑再试)
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: "not json at all",
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_mat,
    )
    assert (session.query(Museum).one().description_i18n or {}) == {}
    assert out["generated"] is False


def test_generate_empty_fields_writes_nothing(session):
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "", "highlights": "", "invitation": ""}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_mat,
    )
    assert (session.query(Museum).one().description_i18n or {}) == {}


def test_generate_missing_keys_skips_them_gracefully(session):
    # 模型漏填某key(常见容错):跳过空key,其余照拼——总比整体失败好
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "Only history."}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_mat,
    )
    assert session.query(Museum).one().description_i18n["en"] == "Only history."
    assert out["generated"] is True


def test_idempotent_fills_missing_language_only(session):
    m = session.query(Museum).one()
    m.description_i18n = {"en": "Existing.", "zh": "已有。"}
    session.commit()
    called = {"gen": 0}

    def complete(s, u):
        called["gen"] += 1
        return "regen"

    out = generate_museum_intro(
        session,
        "orsay",
        complete=complete,
        gate=_Gate(),
        translator=_Tr(),
        langs=["en", "zh", "ja"],
        fetch_material=_mat,
    )
    m = session.query(Museum).one()
    assert called["gen"] == 0  # en 在 → 不重生成(完整性按语言维度)
    assert m.description_i18n["zh"] == "已有。"  # 已有不动
    assert m.description_i18n["ja"] == "ja:Existing."  # 只补缺
    assert out["translated"] == ["ja"]


def test_gate_fail_writes_nothing(session):
    generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "bad"}',  # JSON合法,gate自己拒
        gate=_Gate(ok=False),
        translator=_Tr(),
        langs=["en", "zh"],
        fetch_material=_mat,
    )
    assert (session.query(Museum).one().description_i18n or {}) == {}


def test_no_material_skips(session):
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: "x",
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=lambda qid, **kw: {"extract_en": None},
    )
    assert out["skipped"] == "no_material"


def _add_obj(s, qid, title, pop, key="k"):
    m = s.query(Museum).one()
    o = upsert_object(s, m.id, {"qid": qid, "title_en": title, "category": "painting"})
    o.popularity = pop
    img = ObjectImage(object_id=o.id, role="primary", source_url="u", image_key=key)
    s.add(img)
    s.commit()
    return o


def test_cover_rejects_then_picks_next(session):
    _add_obj(session, "Q1", "L'Origine du monde", 99, key="imgA")
    _add_obj(session, "Q2", "Water Lilies", 50, key="imgB")

    def judge(system, user):
        return (
            '{"appropriate": false}' if "Origine" in user else '{"appropriate": true}'
        )

    key = select_cover(
        session, "orsay", complete=judge, fetch_candidates=lambda qid: []
    )
    assert key == "imgB"
    assert session.query(Museum).one().cover_image_key == "imgB"


def test_cover_judge_error_skips_conservatively(session):
    _add_obj(session, "Q1", "Top", 99, key="imgA")
    _add_obj(session, "Q2", "Second", 50, key="imgB")

    def judge(system, user):
        if "Top" in user:
            raise RuntimeError("llm down")
        return '{"appropriate": true}'

    assert (
        select_cover(session, "orsay", complete=judge, fetch_candidates=lambda qid: [])
        == "imgB"
    )


def test_cover_idempotent(session):
    m = session.query(Museum).one()
    m.cover_image_key = "fixed"
    session.commit()
    assert select_cover(session, "orsay", complete=lambda s, u: 1 / 0) == "fixed"


class _FakeStorage:
    def __init__(self):
        self.put_calls = []

    def exists(self, key):
        return False

    def put(self, key, data, content_type):
        self.put_calls.append(key)


def _fake_bytes(url):
    import io

    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (800, 600), color="white").save(buf, format="JPEG")
    return buf.getvalue()


INTERIOR = "https://commons.wikimedia.org/wiki/Special:FilePath/Hall.jpg"
FACADE = "https://commons.wikimedia.org/wiki/Special:FilePath/Facade.jpg"


def _cover(session, cands, *, exterior=lambda url: url == FACADE, **kw):
    kw.setdefault("storage", _FakeStorage())
    kw.setdefault("fetch_bytes", _fake_bytes)
    kw.setdefault("complete", lambda s, u: 1 / 0)  # 建筑照不走藏品安全闸
    return select_cover(
        session,
        "orsay",
        fetch_candidates=lambda qid: cands,
        is_exterior=exterior,
        fetch_credit=lambda url: f"credit of {url.rsplit('/', 1)[-1]}",
        **kw,
    )


def test_cover_skips_interior_takes_facade_with_credit(session):
    # 规则:封面只要建筑外观全景/正门;内景(小皇宫 10-23 实例)跳过
    storage = _FakeStorage()
    key = _cover(session, [INTERIOR, FACADE], storage=storage)
    assert key.startswith("images/Q23402/cover-")
    assert storage.put_calls == [f"{key}_thumb.jpg", f"{key}_large.jpg"]
    m = session.query(Museum).one()
    assert m.cover_image_key == key and m.cover_credit == "credit of Facade.jpg"


def test_cover_key_differs_per_photo(session):
    # 换了照片 key 就换:旧文件不被复用、App 缓存也跟着刷新
    a = _cover(session, [FACADE])
    b = _cover(
        session,
        [FACADE.replace("Facade", "Other")],
        exterior=lambda u: True,
        force=True,
    )
    assert a != b


def test_cover_exterior_check_error_skips_candidate(session):
    def judge(url):
        if url == INTERIOR:
            raise RuntimeError("vision down")
        return True

    assert _cover(session, [INTERIOR, FACADE], exterior=judge).startswith(
        "images/Q23402/cover-"
    )
    assert session.query(Museum).one().cover_credit == "credit of Facade.jpg"


def test_cover_falls_back_to_artwork_when_no_exterior(session):
    _add_obj(session, "Q1", "Water Lilies", 50, key="imgB")
    key = _cover(session, [INTERIOR], complete=lambda s, u: '{"appropriate": true}')
    assert key == "imgB"
    assert (
        session.query(Museum).one().cover_credit is None
    )  # 藏品图署名在 object_images


def test_cover_falls_back_to_artwork_when_materialize_fails(session):
    _add_obj(session, "Q1", "Water Lilies", 50, key="imgB")

    def _boom(url):
        raise RuntimeError("network down")

    key = _cover(
        session,
        [FACADE],
        fetch_bytes=_boom,
        complete=lambda s, u: '{"appropriate": true}',
    )
    assert key == "imgB"  # 建筑照下载失败不开天窗,回落藏品


def test_cover_no_qid_skips_building_photo(session):
    m = session.query(Museum).filter_by(slug="orsay").one()
    m.qid = None
    session.commit()
    called = {"n": 0}

    def _cands(qid):
        called["n"] += 1
        return [FACADE]

    key = select_cover(
        session, "orsay", complete=lambda s, u: 1 / 0, fetch_candidates=_cands
    )
    assert called["n"] == 0 and key is None  # 无qid跳过建筑照;无藏品可退→None


def test_generate_single_field_falls_back_to_sentence_split(session):
    # 模型把全部内容塞进一个key(已知失败模式)→ 句子边界确定性切分,不调LLM不改内容
    text = " ".join(f"Sentence {i}." for i in range(1, 7))  # 6句
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: f'{{"history": "{text}"}}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_mat,
    )
    en = session.query(Museum).one().description_i18n["en"]
    assert en.count("\n\n") >= 1  # 确实分了段
    assert en.replace("\n\n", " ") == text  # 内容一字不改,纯切分
    assert out["generated"] is True


def test_generate_short_single_field_not_split(session):
    # 太短(不足target段数句子)→ 原样返回,不强行硬切
    out = generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "Only one sentence here."}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_mat,
    )
    assert (
        session.query(Museum).one().description_i18n["en"] == "Only one sentence here."
    )
    assert out["generated"] is True


def test_material_qid_overrides_museum_qid(session):
    # 馆本体无 enwiki(小皇宫:Q59546080 只有 commonswiki),材料要从配置的
    # intro_qid(建筑条目)取——传了就用它,没传才回落 m.qid。
    seen = []

    def _fetch(qid):
        seen.append(qid)
        return {"extract_en": "A 1900 Beaux-Arts palace housing the city's fine arts."}

    generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "H.", "highlights": "L."}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_fetch,
        material_qid="Q820892",
    )
    assert seen == ["Q820892"]  # 不是 Museum.qid 的 Q23402


def test_material_qid_absent_falls_back_to_museum_qid(session):
    seen = []

    def _fetch(qid):
        seen.append(qid)
        return {"extract_en": "Housed in a 1900 railway station..."}

    generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "H.", "highlights": "L."}',
        gate=_Gate(),
        translator=_Tr(),
        langs=["en"],
        fetch_material=_fetch,
    )
    assert seen == ["Q23402"]


def test_museum_name_pinned_for_zh_variants_only(session):
    # 馆名真相唯一化:可字面直译的馆名(Petit Palais→"小宫殿")会与馆列表显示的
    # name_zh 分叉。zh/zh-hant 钉配置译名(繁体走 OpenCC),无真相源的语言不钉。
    seen = {}

    class _TrSpy:
        def translate_section(self, body, lang, museum=None, **kw):
            seen[lang] = museum
            return f"{lang}:{body}"

    m = session.query(Museum).one()
    m.name_zh = "小皇宫美术馆"
    session.flush()
    generate_museum_intro(
        session,
        "orsay",
        complete=lambda s, u: '{"history": "H.", "highlights": "L."}',
        gate=_Gate(),
        translator=_TrSpy(),
        langs=["en", "zh", "zh-hant", "fr"],
        fetch_material=_mat,
    )
    assert seen["zh"] == "小皇宫美术馆"
    assert seen["zh-hant"] == "小皇宮美術館"  # OpenCC 逐字转,不另配
    assert seen["fr"] is None  # 无权威译名 → 不钉
