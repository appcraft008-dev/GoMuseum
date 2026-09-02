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
        if '"faithful"' not in s:  # 翻译调用(非忠实判官)
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


def test_translate_object_threads_artist_into_faithfulness_check():
    """透传测试:光给 build_faithfulness_prompt 加参数不够,translate_object 得真传进去。

    上一轮修语言标签时就栽在这:只测了零件(prompt 构造)、没测装配(translate_section
    的调用),漏掉的 import 靠 CI 才抓到。零件对 ≠ 装配对。
    """
    seen = []

    def router(system, user):
        if '"faithful"' in system:
            seen.append(user)
            return json.dumps({"faithful": True, "issues": []})
        return "译文"

    t = ContentTranslator(router)
    t.translate_object(
        {"guide": "Vouet painted this."},
        ["zh"],
        titles={"zh": "圣殿献耶稣"},
        artists={"zh": "西蒙·沃埃"},
    )
    assert seen, "忠实度检查没被调用"
    assert "西蒙·沃埃" in seen[0], "作者规范名没传到检查器"
    assert "圣殿献耶稣" in seen[0], "标题规范名没传到检查器"


def test_translate_qa_items_threads_names_into_faithfulness_check():
    """问答侧是同一个 bug 的第三个实例:翻译注入了 title/artist,检查侧原本一个没传。"""
    from app.services.enrichment.qa_suggester import translate_qa_items

    seen = []

    def router(system, user):
        if '"faithful"' in system:
            seen.append(user)
            return json.dumps({"faithful": True, "issues": []})
        return "这是中文答案。"

    t = ContentTranslator(router)
    translate_qa_items(
        t,
        [{"question": "Who painted it?", "answer": "Vouet did."}],
        "zh",
        title="圣殿献耶稣",
        artist="西蒙·沃埃",
    )
    assert seen, "问答的忠实度检查没被调用"
    assert "西蒙·沃埃" in seen[0] and "圣殿献耶稣" in seen[0]
