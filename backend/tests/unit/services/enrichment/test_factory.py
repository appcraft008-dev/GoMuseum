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


def test_petit_palais_has_joconde():
    """小皇宫必须装上 joconde —— 这条守的是一条**曾被错误关掉两个月**的源。

    yaml 里原注释以「API 返回 HTML」+「市立馆未必在收录范围」为由关掉它。
    前者是 2026-07-22 老 API 断供留下的疤(已修);后者实测是错的:上游按
    Localisation "Petit Palais, musée des Beaux-arts de la Ville de Paris"
    有 29502 件 —— 按国立馆的「城市 ; 馆名」分号格式去搜才会得到 0。
    静默降级的代价不只是老馆数据变薄,还会让**新馆在配置阶段就把源排除掉**。
    """
    c = build_generation_components("petit_palais")
    assert c["registry"].get("joconde") is not None


def test_build_generation_components_langs_override():
    c = build_generation_components("orsay", langs_override=["en", "fr"])
    assert c["target_langs"] == ["en", "fr"]


def test_build_translator_judges_deterministically(monkeypatch):
    """build_translator 出来的 translator:判定用 temperature=0,翻译仍是 0.3。"""
    from app.services.enrichment.factory import build_translator

    sink = []

    class _Msg:
        content = '{"faithful": true}'

    class _Choice:
        message = _Msg()

    class _Resp:
        choices = [_Choice()]
        usage = None

    class _Completions:
        async def create(self, **kw):
            sink.append(kw)
            return _Resp()

    class _Chat:
        completions = _Completions()

    class _Client:
        chat = _Chat()

    monkeypatch.setattr(
        "app.services.content_generation_service._get_openai_client", lambda: _Client()
    )
    tr = build_translator("translate")

    tr.check_faithfulness("en body", "译文", "zh")
    assert sink[-1]["temperature"] == 0, "忠实度判定必须确定性"

    tr.translate_section("en body", "zh")
    assert sink[-1]["temperature"] == 0.3, "翻译是创作,不该被改成 0"


def test_content_translator_is_constructed_only_by_the_factory():
    """ContentTranslator 只许在 factory 里构造 —— 这条守的是**上一个 bug 的根因**。

    PR #430 给忠实度闸接确定性通道时,装配代码原样复制在 4 处
    (factory / lazy / onboard×2),只改到 1 处;另外 3 条路径照旧 temperature=0.3,
    而当时的测试只覆盖 factory 那条,**全绿**。
    只测"某一条路径对不对"永远抓不到"还有几条路径没改";能抓到的是"路径只有一条"。
    """
    import pathlib

    backend = pathlib.Path(__file__).resolve().parents[4]
    root, scripts = backend / "app", backend / "scripts"
    # 先自检:扫不到文件就说明路径写错了,而不是"没人违规"。
    # (第一版把 parents 数错一层,root 指向不存在的目录,rglob 返回空 → 测试恒绿。)
    files = list(root.rglob("*.py")) + list(scripts.rglob("*.py"))
    assert len(files) > 50, f"只扫到 {len(files)} 个文件,路径写错了"
    assert any(f.name == "onboard.py" for f in files), "没扫到 onboard.py,路径写错了"
    offenders = []
    for f in files:
        if f.name in ("translator.py", "factory.py"):  # 定义处 + 唯一构造处
            continue
        if "ContentTranslator(" in f.read_text():
            offenders.append(str(f.relative_to(root.parent)))
    assert (
        not offenders
    ), f"这些文件在自己拼 ContentTranslator,请改用 factory.build_translator(): {offenders}"
