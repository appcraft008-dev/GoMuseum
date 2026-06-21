import json

from app.services.enrichment.translator import ContentTranslator


def test_translate_section_returns_stripped_text():
    def fake_complete(system, user):
        return "  Olympia est un tableau de 1863.  "

    t = ContentTranslator(fake_complete)
    out = t.translate_section("Olympia is an 1863 painting.", "fr")
    assert out == "Olympia est un tableau de 1863."


def test_check_faithfulness_true_no_issues():
    def fake_complete(system, user):
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(fake_complete)
    ok, issues = t.check_faithfulness("en body", "fr body", "fr")
    assert ok is True
    assert issues == []


def test_check_faithfulness_false_with_issues():
    def fake_complete(system, user):
        return json.dumps({"faithful": False, "issues": ["dropped the year"]})

    t = ContentTranslator(fake_complete)
    ok, issues = t.check_faithfulness("en body", "fr body", "fr")
    assert ok is False
    assert issues == ["dropped the year"]
