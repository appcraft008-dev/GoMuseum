import json

from app.services.enrichment.quality import SectionQuality
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


def test_translate_object_skips_en_and_marks_unfaithful():
    # fr 忠实→published；de 不忠实→needs_review
    def router(system, user):
        s = system.lower()
        if "translate" in s:  # 翻译调用
            return "translated body"
        # 忠实判定：fr 忠实、de 不忠实（按 system 里的语言名区分）
        if "german" in s:
            return json.dumps({"faithful": False, "issues": ["added a claim"]})
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(router)
    out = t.translate_object({"overview": "English overview."}, ["en", "fr", "de"])

    assert set(out.keys()) == {"fr", "de"}  # en 被跳过
    assert out["fr"]["overview"].status == "published"
    assert out["fr"]["overview"].body == "translated body"
    assert out["de"]["overview"].status == "needs_review"
    assert out["de"]["overview"].conflicts == ["added a claim"]


def test_translate_object_skips_empty_section_bodies():
    def router(system, user):
        if "translate" in system.lower():
            return "x"
        return json.dumps({"faithful": True, "issues": []})

    t = ContentTranslator(router)
    out = t.translate_object({"overview": "ok", "artist": None}, ["fr"])
    assert set(out["fr"].keys()) == {"overview"}  # artist(None) 不翻
