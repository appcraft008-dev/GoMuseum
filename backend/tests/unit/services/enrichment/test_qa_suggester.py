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
    def translate_section(self, body, lang):
        return f"[{lang}] {body}"

    def check_faithfulness(self, en, tr, lang):
        return True, []


def test_suggest_en_gates_answers_and_translates_published():
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
