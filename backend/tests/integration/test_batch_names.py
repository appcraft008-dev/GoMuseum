"""Batch names:collect 只收缺的(权威已落库不进JSONL);apply 合并+剥号+坏行跳过。"""

import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services.enrichment.batch_names import (
    BatchTask,
    apply,
    collect_missing,
    load_state,
    poll,
    save_state,
    submit,
)
from app.services.object_importer import upsert_museum, upsert_object


@pytest.fixture()
def session():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "louvre", "name_en": "Louvre"})
    upsert_object(
        s,
        m.id,
        {
            "qid": "Q1",
            "title_en": "Mona Lisa",
            "artist_en": "Leonardo",
            "category": "painting",
            "attributes": {"artist_qid": "QA1"},
        },
    )
    s.add(Artist(qid="QA1", name_en="Leonardo", name_i18n={"en": "Leonardo"}))
    s.commit()
    yield s


def test_collect_authoritative_lands_and_only_missing_emitted(session):
    tasks = collect_missing(
        session,
        "louvre",
        ["en", "fr", "zh"],
        fetch_labels=lambda qid, langs: ({"fr": "La Joconde"} if qid == "Q1" else {}),
    )
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["fr"] == "La Joconde"  # 权威直接落库
    ids = {t.custom_id for t in tasks}
    assert "title|Q1|zh" in ids and "title|Q1|fr" not in ids
    assert "artist|QA1|zh" in ids  # 作者名 zh 缺
    t = next(t for t in tasks if t.custom_id == "title|Q1|zh")
    assert t.name == "Mona Lisa" and t.lang == "zh"


def test_collect_limit_and_idempotent(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {
        **o.attributes,
        "title_i18n": {"en": "Mona Lisa", "zh": "蒙娜丽莎", "fr": "La Joconde"},
    }
    a = session.query(Artist).one()
    a.name_i18n = {"en": "Leonardo", "zh": "达芬奇", "fr": "Léonard"}
    session.commit()
    tasks = collect_missing(
        session, "louvre", ["en", "fr", "zh"], fetch_labels=lambda q, l: {}
    )
    assert tasks == []  # 全齐→零任务(按语言维度幂等)


class _FakeClient:
    """OpenAI Batch 三接口 fake:files.create/batches.create+retrieve/files.content。"""

    def __init__(self, results):
        self._results = results
        outer = self

        class _Files:
            def create(self, file, purpose):
                outer.uploaded = file.read().decode()

                class R:
                    id = "file-in"

                return R()

            def content(self, fid):
                class R:
                    text = "\n".join(json.dumps(r) for r in outer._results)

                return R()

        class _Batches:
            def create(self, **kw):
                outer.batch_kwargs = kw

                class R:
                    id = "batch-1"

                return R()

            def retrieve(self, bid):
                class R:
                    status = "completed"
                    output_file_id = "file-out"

                return R()

        self.files, self.batches = _Files(), _Batches()


def _ok_line(cid, text, tin=100, tout=10):
    return {
        "custom_id": cid,
        "response": {
            "status_code": 200,
            "body": {
                "choices": [{"message": {"content": text}}],
                "usage": {"prompt_tokens": tin, "completion_tokens": tout},
            },
        },
        "error": None,
    }


def test_submit_builds_jsonl_and_poll_returns_lines(session):
    fake = _FakeClient([_ok_line("title|Q1|zh", "《蒙娜丽莎》")])
    job = submit([BatchTask("title|Q1|zh", "Mona Lisa", "zh")], fake)
    assert job == "batch-1"
    line = json.loads(fake.uploaded.splitlines()[0])
    assert line["custom_id"] == "title|Q1|zh" and line["body"]["model"] == "gpt-4o"
    assert "Mona Lisa" in line["body"]["messages"][1]["content"]
    lines = poll(job, fake, interval=0)
    assert lines[0]["custom_id"] == "title|Q1|zh"


def test_apply_merges_strips_and_skips_bad(session, monkeypatch):
    import app.services.enrichment.batch_names as bn

    recorded = []
    monkeypatch.setattr(
        bn,
        "record_llm_usage",
        lambda ch, model, tin, tout, db=None: recorded.append(model),
    )
    lines = [
        _ok_line("title|Q1|zh", "《蒙娜丽莎》"),
        _ok_line("artist|QA1|zh", "达·芬奇"),
        {"custom_id": "title|Q1|ja", "response": None, "error": {"message": "boom"}},
        _ok_line("title|Q404|zh", "无主"),
    ]
    out = apply(session, lines)
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    assert o.attributes["title_i18n"]["zh"] == "蒙娜丽莎"
    assert session.query(Artist).one().name_i18n["zh"] == "达·芬奇"
    assert (
        out["applied"] == 2 and out["skipped"] == 2
    )  # boom行(无usage)+Q404(实体不存在)
    # 诚实成本口径:Q404 那行 Batch 真翻了、真收费 → 记账算它(即使回填不上);
    # boom 行 response=None 无 usage → 不记。故 3 条记账。
    assert recorded == ["gpt-4o@batch"] * 3


def test_apply_does_not_overwrite_existing(session):
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.attributes = {**o.attributes, "title_i18n": {"zh": "既有译名"}}
    session.commit()
    apply(session, [_ok_line("title|Q1|zh", "新译名")])
    assert (
        session.query(MuseumObject)
        .filter_by(qid="Q1")
        .one()
        .attributes["title_i18n"]["zh"]
        == "既有译名"
    )


def test_state_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    save_state(p, "batch-9", 42)
    st = load_state(p)
    assert st["job_id"] == "batch-9" and st["task_count"] == 42


class _ChunkClient:
    """记录每次 submit 的任务数,验证分块;retrieve 恒 completed。"""

    def __init__(self):
        self.chunk_sizes = []
        self.job_ids = []
        outer = self

        class _Files:
            def create(self, file, purpose):
                outer.chunk_sizes.append(len(file.read().decode().splitlines()))

                class R:
                    id = "file-in"

                return R()

            def content(self, fid):
                class R:
                    text = ""  # 空结果:本测试只验证提交分块

                return R()

        class _Batches:
            def create(self, **kw):
                jid = f"batch-{len(outer.job_ids) + 1}"
                outer.job_ids.append(jid)

                class R:
                    id = jid

                return R()

            def retrieve(self, bid):
                class R:
                    status = "completed"
                    output_file_id = "file-out"

                return R()

        self.files, self.batches = _Files(), _Batches()


def test_run_chunks_over_openai_50k_limit(session, monkeypatch):
    # OpenAI Batch 单 job 上限 5万请求;卢浮宫 17283件×10语 远超 → 必须分块
    # (2026-07-25 prod 实测 maximum_requests_exceeded,提交即拒)
    from app.services.enrichment import batch_names as bn

    fake_tasks = [bn.BatchTask(f"title|Q{i}|zh", f"N{i}", "zh") for i in range(120_000)]
    monkeypatch.setattr(bn, "collect_missing", lambda *a, **k: fake_tasks)
    c = _ChunkClient()
    out = bn.run(session, "louvre", ["zh"], client=c, state_path="/tmp/_t.json")
    assert len(c.job_ids) == 3  # 120k / 50k → 3 块
    assert all(n <= bn.MAX_BATCH_REQUESTS for n in c.chunk_sizes)
    assert sum(c.chunk_sizes) == 120_000  # 一个任务不丢
    assert out["job_id"] == ",".join(c.job_ids)  # 多 job 可续传


def test_collect_resolves_creators_and_creates_artist_rows(session):
    # 路径等价性:batch 路径此前只读已有 artist_qid、从不抓 P170,新馆 catalog 不产
    # artist_qid → 作者一个都建不了(卢浮宫实测 17283件仅1件有,10041件作者名无中文)
    from app.models.artist import Artist
    from app.models.museum import Museum
    from app.services.enrichment import batch_names as bn

    m = session.query(Museum).one()
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_en = "Eugène Delacroix"
    o.attributes = {}  # 无 artist_qid,模拟新馆 catalog 产物
    session.commit()

    tasks = bn.collect_missing(
        session,
        m.slug,
        ["en", "zh"],
        fetch_labels=lambda qid, langs: {},  # 无权威标签 → 该出翻译任务
        fetch_creators=lambda qids: {"Q1": "Q33477"},  # P170 → 德拉克罗瓦
    )
    session.commit()
    assert (session.query(MuseumObject).filter_by(qid="Q1").one().attributes or {}).get(
        "artist_qid"
    ) == "Q33477"  # 解析结果落库
    art = session.query(Artist).filter_by(qid="Q33477").one()
    assert art.name_en == "Eugène Delacroix"  # 新馆首跑建行,轴心取自作品行
    assert any(t.custom_id == "artist|Q33477|zh" for t in tasks)  # 出中文翻译任务


def test_collect_prefers_authoritative_artist_labels(session):
    # 名家在 Wikidata 多语齐全 → 直接落库,不出翻译任务(免费且更准)
    from app.models.artist import Artist
    from app.models.museum import Museum
    from app.services.enrichment import batch_names as bn

    m = session.query(Museum).one()
    o = session.query(MuseumObject).filter_by(qid="Q1").one()
    o.artist_en = "Eugène Delacroix"
    o.attributes = {}
    session.commit()

    tasks = bn.collect_missing(
        session,
        m.slug,
        ["en", "zh"],
        fetch_labels=lambda qid, langs: (
            {"en": "Eugène Delacroix", "zh": "欧仁·德拉克罗瓦"}
            if qid == "Q33477"
            else {}
        ),
        fetch_creators=lambda qids: {"Q1": "Q33477"},
    )
    session.commit()
    art = session.query(Artist).filter_by(qid="Q33477").one()
    assert (art.name_i18n or {}).get("zh") == "欧仁·德拉克罗瓦"  # 权威直接落库
    assert not any(t.custom_id.startswith("artist|Q33477") for t in tasks)  # 无需翻译
