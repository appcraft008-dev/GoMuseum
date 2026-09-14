"""译文里漏翻的英文词 → 触发重译,重译还漏就挂起。

两道现有的闸都对它失明:忠实度闸看事实(漏词没漏掉事实),
语言检测看整段语种(99% 是中文,判过)。所以它一路绿灯发到用户眼前。
"""

from app.services.enrichment.translator import ContentTranslator, untranslated_words


def test_catches_the_two_real_leaks():
    """2026-09-13 第一批 10 件实测出的两处,都在大卫《塞内卡之死》。"""
    assert untranslated_words("背景中华丽的 urn 和宏伟的柱子。", "zh") == ["urn"]
    assert untranslated_words(
        "构图经过精心安排， reclining 的塞内卡位于中心。", "zh"
    ) == ["reclining"]


def test_keeps_names_and_quoted_originals():
    """大写开头的是人名/地名,引号与书名号里的是刻意保留的原名 —— 都不算漏译。

    没有这条,《Têtes d'enfants》这类保留原名会被判成漏译,把好译文误挂。
    """
    assert untranslated_words("雅克-路易·大卫（Jacques-Louis David）作。", "zh") == []
    assert untranslated_words("这幅《Têtes d'enfants》画于 1896 年。", "zh") == []
    assert untranslated_words("题为「the mouthful of bread」的作品。", "zh") == []


def test_latin_script_languages_are_not_scanned():
    """法语/德语正文本来就是拉丁字母,这把尺子对它们没有意义 —— 全判成漏译才是灾难。"""
    assert untranslated_words("Ce tableau montre un vieil homme au béret.", "fr") == []
    assert untranslated_words("Das Gemälde zeigt einen alten Mann.", "de") == []


class _Fake:
    """mini 首译漏词、强模型重译干净;忠实度一律通过。

    ⚠️ 判定分支必须认 "fact judge" 而不是 "faithful":翻译 prompt 自己就写着
    「Be FAITHFUL」,用后者路由会把翻译调用也截胡,于是忠实度解析失败 → ok=False
    → 无论有没有漏译检测都会触发重译,这条用例就永远绿。
    """

    def __init__(self):
        self.mini_calls = self.strong_calls = 0

    def mini(self, system, user):
        if "fact judge" in system.lower():
            return '{"faithful": true, "issues": []}'
        self.mini_calls += 1
        return "背景中华丽的 urn 和宏伟的柱子构成对比。"

    def strong(self, system, user):
        self.strong_calls += 1
        return "背景中华丽的骨灰瓮和宏伟的柱子构成对比。"


def test_leak_triggers_strong_retranslation_and_publishes_the_clean_one():
    f = _Fake()
    t = ContentTranslator(f.mini, complete_strong=f.strong)
    out = t.translate_object({"guide": "An ornate urn stands behind."}, ["zh"])
    r = out["zh"]["guide"]
    assert f.strong_calls == 1, "漏词必须走到强模型重译"
    assert "urn" not in r.body
    assert r.status == "published"


def test_still_leaking_after_retranslation_is_held():
    """重译还漏 → 挂起,不能把夹着英文词的正文发给用户。"""

    class _AlwaysLeaks(_Fake):
        def strong(self, system, user):
            self.strong_calls += 1
            return "背景中华丽的 urn 依旧在。"

    f = _AlwaysLeaks()
    t = ContentTranslator(f.mini, complete_strong=f.strong)
    out = t.translate_object({"guide": "An ornate urn stands behind."}, ["zh"])
    assert out["zh"]["guide"].status == "needs_review"
