"""QASuggester：每件接地预生成 3-4 个"问题+答案"（英语轴心→答案过闸→翻译铺语言）。
组件注入（complete/gate/translator），离线可测。spec §12b 推荐 chips。"""

from __future__ import annotations

from app.services.enrichment.prompts import build_qa_prompt


def _parse():
    from app.services.enrichment.content_enricher import _parse_json

    return _parse_json


def _clean_question(q: str):
    """硬 guard:question 到第一个问号截断(救"Q？+描述");没问号=陈述句→丢(返 None)。
    英语轴心问号是 '?';翻译后可能是 '？'——两者都认。"""
    if not q:
        return None
    idx = [q.find(m) for m in ("?", "？") if q.find(m) != -1]
    if not idx:
        return None  # 无问号 = 陈述句,不发
    return q[: min(idx) + 1].strip()


def translate_qa_items(translator, en_items: list, lang: str) -> list:
    """把英语问答对翻到 lang(问句截到问号+答案忠实校验)。suggest 与补语种共用。"""
    out = []
    for it in en_items:
        tq = _clean_question(translator.translate_section(it["question"], lang))
        ta = translator.translate_section(it["answer"], lang)
        if not tq:  # 翻译把问句变陈述了 → 回退英文问句(已是短问句)
            tq = it["question"]
        ok, _ = translator.check_faithfulness(it["answer"], ta, lang)
        out.append(
            {
                "question": tq,
                "answer": ta,
                "status": "published" if ok else "needs_review",
            }
        )
    return out


class QASuggester:
    def __init__(self, complete, gate, translator):
        self._complete = complete
        self._gate = gate
        self._translator = translator

    def _generate_en(
        self, material: str, facts: str, category: str, covered: str | None = None
    ) -> list:
        raw = self._complete(*build_qa_prompt(material, category, covered))
        pairs = _parse()(raw).get("qa") or []
        items = []
        for p in pairs:
            q = _clean_question((p.get("question") or "").strip())
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
        self,
        material: str,
        facts: str,
        category: str,
        target_langs: list,
        covered: str | None = None,
    ) -> dict:
        en_items = self._generate_en(material, facts, category, covered)
        out = {"en": en_items}
        published = [it for it in en_items if it["status"] == "published"]
        for lang in target_langs:
            if lang == "en":
                continue
            out[lang] = translate_qa_items(self._translator, published, lang)
        return out
