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


def translate_qa_items(translator, en_items: list, lang: str, title=None) -> list:
    """把英语问答对翻到 lang(问句截到问号+答案忠实校验)。suggest 与补语种共用。
    title=规范标题:问答引用标题统一用显示名(消除分叉,同 guide/deep)。"""
    import re as _re

    out = []
    for it in en_items:
        raw_q = translator.translate_section(it["question"], lang, title=title)
        tq = _clean_question(raw_q)
        ta = translator.translate_section(it["answer"], lang, title=title)
        if not tq:
            # 翻译丢了问号 → 补目标语问号(别回退英文,那样中文里混英文问题);真空才回退英文
            stripped = (raw_q or "").strip()
            if stripped:
                cjk = _re.search(r"[一-鿿぀-ゟ゠-ヿ가-힣]", stripped)
                tq = stripped.rstrip("。.！!？?") + ("？" if cjk else "?")
            else:
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
        titles: dict | None = None,
    ) -> dict:
        titles = titles or {}
        en_items = self._generate_en(material, facts, category, covered)
        out = {"en": en_items}
        published = [it for it in en_items if it["status"] == "published"]
        for lang in target_langs:
            if lang == "en":
                continue
            out[lang] = translate_qa_items(
                self._translator, published, lang, title=titles.get(lang)
            )
        return out
