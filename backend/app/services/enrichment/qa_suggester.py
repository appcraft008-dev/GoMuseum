"""QASuggester：每件接地预生成 3-4 个"问题+答案"（英语轴心→答案过闸→翻译铺语言）。
组件注入（complete/gate/translator），离线可测。spec §12b 推荐 chips。"""

from __future__ import annotations

from app.services.enrichment.prompts import build_qa_prompt


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


class QASuggester:
    def __init__(self, complete, gate, translator):
        self._complete = complete
        self._gate = gate
        self._translator = translator

    def _generate_en(self, material: str, facts: str, category: str) -> list:
        raw = self._complete(*build_qa_prompt(material, category))
        pairs = _parse()(raw).get("qa") or []
        items = []
        for p in pairs:
            q = (p.get("question") or "").strip()
            a = (p.get("answer") or "").strip()
            if not q or not a:
                continue
            r = self._gate.check_section(material, facts, a)
            if r.status == "published" and r.body:
                items.append({"question": q, "answer": r.body, "status": "published"})
            else:
                items.append({"question": q, "answer": a, "status": "needs_review"})
        return items

    def suggest(
        self, material: str, facts: str, category: str, target_langs: list
    ) -> dict:
        en_items = self._generate_en(material, facts, category)
        out = {"en": en_items}
        published = [it for it in en_items if it["status"] == "published"]
        for lang in target_langs:
            if lang == "en":
                continue
            litems = []
            for it in published:
                tq = self._translator.translate_section(it["question"], lang)
                ta = self._translator.translate_section(it["answer"], lang)
                ok, _ = self._translator.check_faithfulness(it["answer"], ta, lang)
                litems.append(
                    {
                        "question": tq,
                        "answer": ta,
                        "status": "published" if ok else "needs_review",
                    }
                )
            out[lang] = litems
        return out
