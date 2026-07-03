"""组件工厂:onboard 与懒生成共用装配(读真实 museums.yaml,离线构造)。"""

from app.services.enrichment.factory import build_generation_components


def test_build_generation_components_from_museum_config():
    c = build_generation_components("orsay")
    assert c["country_lang"] == "fr"
    assert "zh" in c["target_langs"] and "en" in c["target_langs"]
    assert c["registry"].get("joconde") is not None  # 按 yaml sources 组装
    assert c["registry"].get("wikipedia") is not None
    for key in ("enricher", "gate", "translator", "qa_suggester"):
        assert c[key] is not None


def test_build_generation_components_langs_override():
    c = build_generation_components("orsay", langs_override=["en", "fr"])
    assert c["target_langs"] == ["en", "fr"]
