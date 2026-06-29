from app.services.enrichment.sources.joconde import JocondeSource


def test_probe_requires_p347():
    s = JocondeSource(session=None)
    assert s.probe({"P347": "000PE004070"}) is True
    assert s.probe({}) is False


def test_enrich_maps_french_fields():
    captured = {}

    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            captured["params"] = params
            return {
                "records": [
                    {
                        "fields": {
                            "titre": "Etude : torse",
                            "auteur": "RENOIR Pierre Auguste",
                            "materiaux_techniques": "peinture à l'huile;toile",
                            "mesures": "81 H ; 64.8 L",
                            "numero_inventaire": "RF 2740",
                            "sujet_represente": "torse,nu,figure",
                            "periode_de_creation": "4e quart 19e siècle",
                            "domaine": "peinture",
                            "denomination": "tableau",
                            "ecole_pays": "France",
                            "localisation": "Paris ; musée d'Orsay",
                        }
                    }
                ]
            }

    s = JocondeSource(session=FakeSession())
    c = s.enrich("Q1", {"P347": "000PE004070"}, {})
    assert c is not None
    assert c.source == "official"
    assert c.qid == "Q1"
    assert c.fields["title_fr"] == "Etude : torse"
    assert c.fields["medium_fr"] == "peinture à l'huile;toile"
    assert c.fields["inventory_number"] == "RF 2740"
    assert "000PE004070" in str(captured["params"])
    assert c.fields["subjects_fr"] == "torse,nu,figure"
    assert c.fields["period_fr"] == "4e quart 19e siècle"
    assert c.fields["domaine_fr"] == "peinture"
    assert c.fields["denomination_fr"] == "tableau"
    assert c.fields["school_fr"] == "France"
    assert c.fields["location_fr"] == "Paris ; musée d'Orsay"


def test_enrich_returns_none_without_p347():
    assert JocondeSource(session=None).enrich("Q1", {}, {}) is None


def test_enrich_returns_none_when_no_records():
    class FakeSession:
        def get_json(self, url, params=None, _transport=None):
            return {"records": []}

    assert JocondeSource(session=FakeSession()).enrich("Q1", {"P347": "X"}, {}) is None
