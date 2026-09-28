import json

from app.services.enrichment.qa_suggester import QASuggester
from app.services.enrichment.quality import SectionQuality


class _Complete:
    def __call__(self, system, user):
        return json.dumps(
            {
                "qa": [
                    {"question": "Q1?", "answer": "A1 grounded."},
                    {"question": "Q2?", "answer": "A2 ungrounded."},
                ]
            }
        )


class _Gate:
    def check_section(self, material, facts, body):
        if "A1" in body:
            return SectionQuality(
                body=body,
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )
        return SectionQuality(
            body=None,
            status="needs_review",
            grounding_ratio=0.0,
            conflicts=[],
            score=0.0,
        )


class _Translator:
    def translate_section(
        self, body, lang, *, strong=False, title=None, artist=None, **_kw
    ):
        return f"[{lang}] {body}"

    def check_faithfulness(self, en, tr, lang, title=None, artist=None, **_kw):
        return True, []


def test_suggest_en_gates_answers_and_translates_published(monkeypatch):
    # 合成 [lang] 假译文非真语言,此测试验翻译流程非语言检测→屏蔽语言闸
    monkeypatch.setattr(
        "app.services.enrichment.lang_detect.text_in_language", lambda t, l: True
    )
    s = QASuggester(_Complete(), _Gate(), _Translator())
    out = s.suggest("material", "facts", "painting", ["en", "fr"])

    en = out["en"]
    assert {i["status"] for i in en} == {"published", "needs_review"}
    a1 = next(i for i in en if i["question"] == "Q1?")
    assert a1["status"] == "published" and a1["answer"] == "A1 grounded."

    fr = out["fr"]
    assert len(fr) == 1
    assert fr[0]["question"] == "[fr] Q1?"
    assert fr[0]["answer"] == "[fr] A1 grounded."
    assert fr[0]["status"] == "published"


def test_suggest_skips_empty_pairs():
    class _C:
        def __call__(self, system, user):
            return json.dumps(
                {
                    "qa": [
                        {"question": "", "answer": "x"},
                        {"question": "Q?", "answer": ""},
                    ]
                }
            )

    s = QASuggester(_C(), _Gate(), _Translator())
    out = s.suggest("m", "f", "painting", ["en"])
    assert out["en"] == []


def test_suggest_passes_covered_to_prompt():
    captured = {}

    def fake_complete(system, user):
        captured["user"] = user
        import json as _json

        return _json.dumps({"qa": []})

    class _G:
        def check_section(self, m, f, b):
            return SectionQuality(
                body=b,
                status="published",
                grounding_ratio=1.0,
                conflicts=[],
                score=1.0,
            )

    class _T:
        pass

    s = QASuggester(complete=fake_complete, gate=_G(), translator=_T())
    s.suggest("MAT", "facts", "painting", ["en"], covered="解说讲过猫和花。")
    assert "解说讲过猫和花" in captured["user"]


def test_clean_question_guard():
    from app.services.enrichment.qa_suggester import _clean_question

    assert (
        _clean_question("这幅画的骑士是谁？他很神秘。") == "这幅画的骑士是谁？"
    )  # 截断描述
    assert _clean_question("Who is the knight? He is...") == "Who is the knight?"
    assert (
        _clean_question("Rochegrosse受多位艺术家影响，展现独特语言。") is None
    )  # 陈述句→丢
    assert _clean_question("") is None


def test_translate_qa_appends_qmark_not_english_fallback():
    # 问题2:翻译没带问号时,补目标语问号(别回退英文原问题)
    from app.services.enrichment.qa_suggester import translate_qa_items

    class _Tr:
        def translate_section(
            self, text, lang, *, strong=False, title=None, artist=None, **_kw
        ):
            # 模拟翻译丢了问号(陈述句式)
            return "梵高的信件揭示了什么" if "?" in text else f"{text}译"

        def check_faithfulness(self, en, tr, lang, title=None, artist=None, **_kw):
            return True, []

    out = translate_qa_items(
        _Tr(), [{"question": "What did Van Gogh reveal?", "answer": "X."}], "zh"
    )
    q = out[0]["question"]
    assert "？" in q  # 补了中文问号
    assert "What" not in q  # 没回退英文


def test_qa_gates_wrong_language():
    from app.services.enrichment.qa_suggester import translate_qa_items

    class _Tr:
        def translate_section(
            self, text, lang, *, strong=False, title=None, artist=None, **_kw
        ):
            return (
                "This whole answer leaked into English instead of the Chinese language."
            )

        def check_faithfulness(self, en, tr, lang, title=None, artist=None, **_kw):
            return True, []

    out = translate_qa_items(
        _Tr(),
        [{"question": "Why?", "answer": "Because of the light effects here now."}],
        "zh",
    )
    assert out[0]["status"] == "needs_review"  # 答案英文→语言不符→不发布


def test_fact_field_is_dropped_not_shown():
    """prompt 让模型先填 `fact`(材料原句),它只是出题脚手架,不能落库也不能拼进答案。"""

    class _C:
        def __call__(self, system, user):
            return json.dumps(
                {
                    "qa": [
                        {"fact": "Source sentence.", "question": "Q1?", "answer": "A1."}
                    ]
                }
            )

    out = QASuggester(_C(), _Gate(), _Translator()).suggest(
        "m", "f", "painting", ["en"]
    )
    assert out["en"] == [{"question": "Q1?", "answer": "A1.", "status": "published"}]


class _EchoTr:
    """译文 = 预设表;忠实度按 bad 集合判。"""

    def __init__(self, table, bad=()):
        self.table, self.bad = table, set(bad)

    def translate_section(self, text, lang, **_kw):
        return self.table.get(text, text)

    def check_faithfulness(self, en, tr, lang, **_kw):
        return (tr not in self.bad), []


def _one(tr, q, a="Answer text.", lang="zh", **kw):
    from app.services.enrichment.qa_suggester import translate_qa_items

    return translate_qa_items(tr, [{"question": q, "answer": a}], lang, **kw)[0]


def test_question_translated_into_an_answer_is_held(monkeypatch):
    monkeypatch.setattr(
        "app.services.enrichment.lang_detect.text_in_language", lambda t, l: True
    )
    tr = _EchoTr(
        {
            "What happened to Courbet later?": "库尔贝晚年遭遇了许多挑战。他最终被迫流亡到瑞士？",
            "Answer text.": "答案。",
        }
    )
    assert _one(tr, "What happened to Courbet later?")["status"] == "needs_review"


def test_question_that_fails_faithfulness_is_held(monkeypatch):
    """问句换了人(作者→画中人)只有问句的忠实度检查能抓到。"""
    monkeypatch.setattr(
        "app.services.enrichment.lang_detect.text_in_language", lambda t, l: True
    )
    tr = _EchoTr(
        {
            "What was Fragonard's family background?": "拉朗德的家庭背景如何？",
            "Answer text.": "答案。",
        },
        bad={"拉朗德的家庭背景如何？"},
    )
    assert (
        _one(tr, "What was Fragonard's family background?")["status"] == "needs_review"
    )


def test_abbreviations_and_dotted_titles_are_not_second_sentences(monkeypatch):
    monkeypatch.setattr(
        "app.services.enrichment.lang_detect.text_in_language", lambda t, l: True
    )
    title = "Le Repos au bord d'un ruisseau. Lisière de bois"
    for q in (
        "Wie war die Reaktion des Hofes auf das Porträt Ludwig XIV. von Rigaud?",
        "Warum zeigte van Gogh dieses Bild Dr. Paul Gachet?",
        "Was geschah mit dem Stundenbuch nach dem 17. Jahrhundert?",
        f"Pourquoi Sisley a-t-il peint '{title}' ici ?",
    ):
        tr = _EchoTr({})
        assert _one(tr, q, lang="de", title=title)["status"] == "published", q
