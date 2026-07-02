from app.services.enrichment.material import fetch_object_material
from app.services.enrichment.registry import SourceRegistry
from app.services.enrichment.sources.base import ObjectContribution, Source


class _FakeWiki(Source):
    name = "wikipedia"

    def fetch(self, cfg):
        return []

    def enrich(self, qid, external_ids, context):
        title = (context.get("wiki_titles") or {}).get("en")
        if not title:
            return None
        return ObjectContribution(
            source="wikipedia",
            qid=qid,
            fields={"extract_en": f"lead of {title}"},
            raw={},
        )


def test_fetch_object_material_returns_enrichment_attributes():
    reg = SourceRegistry([_FakeWiki()])
    out = fetch_object_material("Q1", {}, {"en": "The_Balcony"}, reg)
    assert out["extract_en"] == "lead of The_Balcony"
    # 身份/留痕键不进材料
    assert "qid" not in out and "sources" not in out and "external_ids" not in out


def test_fetch_object_material_empty_when_no_contribs():
    reg = SourceRegistry([_FakeWiki()])
    assert fetch_object_material("Q1", {}, {}, reg) == {}


def test_fetch_artist_material_via_injected_query():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry
    from app.services.enrichment.sources.base import ObjectContribution, Source

    def fake_run_query(sparql):
        return [{"al_en": {"value": "https://en.wikipedia.org/wiki/Gustave_Courbet"}}]

    class _Wiki(Source):
        name = "wikipedia"

        def fetch(self, cfg):
            return []

        def enrich(self, qid, ext, ctx):
            t = (ctx.get("wiki_titles") or {}).get("en")
            return (
                ObjectContribution(
                    source="wikipedia",
                    qid=qid,
                    fields={"extract_en": f"bio of {t}"},
                    raw={},
                )
                if t
                else None
            )

    reg = SourceRegistry([_Wiki()])
    out = fetch_artist_material("Q1", reg, run_query=fake_run_query, country_lang="fr")
    assert out["artist_extract_en"] == "bio of Gustave_Courbet"


def test_fetch_artist_material_empty_when_no_artist():
    from app.services.enrichment.material import fetch_artist_material
    from app.services.enrichment.registry import SourceRegistry

    out = fetch_artist_material(
        "Q1", SourceRegistry([]), run_query=lambda s: [], country_lang="fr"
    )
    assert out == {}


def test_fetch_artist_facts_parses_structured():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {
                "birth": {"value": "1832-01-23T00:00:00Z"},
                "death": {"value": "1883-04-30T00:00:00Z"},
                "natLabel": {"value": "France"},
                "workLabel": {"value": "Olympia"},
            },
            {"natLabel": {"value": "France"}, "workLabel": {"value": "The Fifer"}},
            {"natLabel": {"value": "France"}, "workLabel": {"value": "Olympia"}},
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_birth"] == "1832" and f["artist_death"] == "1883"
    assert f["artist_nationality"] == "France"
    assert f["artist_notable_works"] == ["Olympia", "The Fifer"]  # 去重保序


def test_fetch_artist_facts_empty_on_no_rows():
    from app.services.enrichment.material import fetch_artist_facts

    assert fetch_artist_facts("Q1", run_query=lambda s: []) == {}


def test_fetch_artist_facts_skips_raw_qid_works():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {"workLabel": {"value": "Homage to Cézanne"}},
            {"workLabel": {"value": "Q17490760"}},  # 无标签→跳
            {"natLabel": {"value": "France"}},
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_notable_works"] == ["Homage to Cézanne"]  # QID 被过滤
    assert f["artist_nationality"] == "France"


def test_fetch_artist_facts_returns_artist_qid():
    from app.services.enrichment.material import fetch_artist_facts

    def fake(sparql):
        return [
            {
                "artist": {"value": "http://www.wikidata.org/entity/Q296"},
                "natLabel": {"value": "Netherlands"},
            }
        ]

    f = fetch_artist_facts("Q1", run_query=fake)
    assert f["artist_qid"] == "Q296"
