from app.services.enrichment.prompts import build_generation_prompt


def test_prompt_lists_requested_sections_and_grounding_rules():
    system, user = build_generation_prompt(
        material="[FACTS]\n- Title: X",
        sections=["overview", "artist"],
        category="painting",
    )
    assert "not" in system.lower()  # grounding rule present (do NOT invent / MUST NOT)
    assert "overview" in user and "artist" in user
    assert "painting" in user
    assert "[FACTS]" in user


def test_generation_prompt_is_audio_guide_voice_with_roles():
    system, user = build_generation_prompt(
        "MAT", ["overview", "background"], "painting"
    )
    blob = (system + user).lower()
    assert "audio" in blob or "spoken" in blob
    assert "you" in blob
    assert "framing" in blob or "guide" in blob or "second person" in blob
    assert "do not invent" in blob or "not in the material" in blob
    assert "hook" in blob  # overview 角色词
    assert "story" in blob  # background 角色词
    assert "json" in blob
    assert "overview" in user and "background" in user


def test_entailment_prompt_demands_per_sentence_json_verdicts():
    from app.services.enrichment.prompts import build_entailment_prompt

    system, user = build_entailment_prompt("[FACTS]\n- Title: Olympia", ["S1.", "S2."])
    blob = (system + user).lower()
    assert "only" in blob and "material" in blob
    assert "json" in blob
    assert "verdicts" in blob
    assert "S1." in user and "S2." in user


def test_fact_consistency_prompt_lists_conflicts_json():
    from app.services.enrichment.prompts import build_fact_consistency_prompt

    system, user = build_fact_consistency_prompt(
        "- Year: 1863", "Painted in 1900 by Manet."
    )
    blob = (system + user).lower()
    assert "contradict" in blob or "conflict" in blob
    assert "json" in blob
    assert "conflicts" in blob
    assert "1863" in user and "1900" in user


def test_fact_consistency_prompt_excuses_event_years():
    # 校准：创作年 vs 首展/收购/修复/发现年不算冲突（避免判官把不同事件的年份误报）
    from app.services.enrichment.prompts import build_fact_consistency_prompt

    system, _ = build_fact_consistency_prompt("- Year: 1863", "Exhibited in 1865.")
    blob = system.lower()
    assert "exhibition" in blob or "acquisition" in blob
    assert "same fact" in blob


def test_translation_prompt_demands_faithful_and_keeps_proper_names():
    from app.services.enrichment.prompts import build_translation_prompt

    system, user = build_translation_prompt("Olympia is an 1863 painting.", "fr")
    blob = (system + user).lower()
    assert "french" in blob
    assert "faithful" in blob or "do not add" in blob
    assert "proper" in blob or "title" in blob
    assert "Olympia is an 1863 painting." in user


def test_faithfulness_prompt_returns_json_verdict():
    from app.services.enrichment.prompts import build_faithfulness_prompt

    system, user = build_faithfulness_prompt(
        "Olympia is an 1863 painting.", "Olympia est un tableau de 1863.", "fr"
    )
    blob = (system + user).lower()
    assert "faithful" in blob
    assert "json" in blob
    assert "issues" in blob
    assert "Olympia est un tableau de 1863." in user


def test_qa_prompt_grounded_json_pairs():
    from app.services.enrichment.prompts import build_qa_prompt

    system, user = build_qa_prompt("[FACTS]\n- Title: Olympia", "painting")
    blob = (system + user).lower()
    assert "only" in blob and "material" in blob
    assert "json" in blob and "qa" in blob
    assert "question" in blob and "answer" in blob
    assert "[FACTS]\n- Title: Olympia" in user


def test_qa_prompt_encodes_chip_quality_standard():
    from app.services.enrichment.prompts import build_qa_prompt

    system, _ = build_qa_prompt("[FACTS]", "painting")
    s = system.lower()
    # 红线：禁墙签硬事实（标题/作者/年代/馆藏地…）
    assert "wall label" in s or "wall-label" in s
    assert "never ask" in s or "do not ask" in s
    # 好奇心驱动
    assert "curious" in s or "why/how" in s
    # 宁缺毋滥（少出胜过 trivia 凑数）
    assert "fewer" in s or "empty list" in s


from app.services.enrichment.prompts import (
    build_default_guide_prompt,
    build_entailment_prompt,
)


def test_default_guide_prompt_five_beats_single_throughline():
    system, user = build_default_guide_prompt("MAT", "FACTS", (270, 420))
    blob = (system + user).lower()
    assert "one" in blob and (
        "throughline" in blob or "core point" in blob or "single" in blob
    )
    assert "notice" in blob or "look" in blob
    assert "remember" in blob or "memory" in blob or "question" in blob
    assert "270" in user and "420" in user
    assert "do not invent" in blob or "not in the material" in blob
    assert (
        "headline" in blob or "more content" in blob or "don't cover everything" in blob
    )


def test_translation_prompt_preserves_tone():
    from app.services.enrichment.prompts import build_translation_prompt

    system, _ = build_translation_prompt("Hello.", "zh")
    blob = system.lower()
    assert "tone" in blob or "voice" in blob or "engaging" in blob  # 保腔调
    assert "faithful" in blob  # 仍忠实


def test_grounding_prompt_is_three_class():
    system, user = build_entailment_prompt("MAT", ["s1", "s2"])
    blob = (system + user).lower()
    assert "factual claim" in blob or "factual" in blob
    assert "framing" in blob or "guidance" in blob or "second person" in blob
    assert "impression" in blob
    assert "when in doubt" in blob or "if unsure" in blob
    assert "verdicts" in blob and "true" in blob
    assert "1. s1" in user and "2. s2" in user


def test_generation_prompt_dedup_with_guide():
    from app.services.enrichment.prompts import build_generation_prompt

    system, user = build_generation_prompt(
        "MAT", ["artist", "background"], "painting", guide="这是已播的头条讲解。"
    )
    blob = (system + user).lower()
    assert "这是已播的头条讲解" in user
    assert "do not repeat" in blob or "don't repeat" in blob or "already" in blob
    assert "empty" in blob


def test_generation_prompt_no_guide_still_works():
    from app.services.enrichment.prompts import build_generation_prompt

    system, user = build_generation_prompt("MAT", ["artist"], "painting")
    assert "artist" in user  # guide 缺省不报错


def test_generation_prompt_tiers_length_by_popularity():
    from app.services.enrichment.prompts import build_generation_prompt

    _, user_key = build_generation_prompt(
        "M", ["background"], "painting", popularity=40
    )
    _, user_norm = build_generation_prompt(
        "M", ["background"], "painting", popularity=5
    )
    assert "570" in user_key  # 重点件 background 380×1.5
    assert "380" in user_norm  # 普通件
    assert (
        "dilute" in user_key.lower()
        or "filler" in user_key.lower()
        or "pad" in user_key.lower()
    )


def test_generation_prompt_popularity_optional():
    from app.services.enrichment.prompts import build_generation_prompt

    _, user = build_generation_prompt("M", ["artist"], "painting")
    assert "artist" in user  # 无 popularity 不报错


def test_qa_prompt_includes_covered_dedup():
    from app.services.enrichment.prompts import build_qa_prompt

    _, user = build_qa_prompt("MAT", "painting", covered="解说已讲了猫和花的象征。")
    assert "解说已讲了猫和花" in user
    assert "already" in user.lower() or "已" in user or "not" in user.lower()


def test_qa_prompt_covered_optional():
    from app.services.enrichment.prompts import build_qa_prompt

    _, user = build_qa_prompt("MAT", "painting")
    assert "MAT" in user  # 无 covered 不报错


def test_qa_system_steers_peripheral_and_forbids_covered():
    from app.services.enrichment.prompts import _QA_SYSTEM, build_qa_prompt

    s = _QA_SYSTEM.lower()
    assert "forbidden" in s and "peripheral" in s
    assert "afterlife" in s or "did not cover" in s or "not already told" in s
    # covered_block 设禁区
    _, user = build_qa_prompt("M", "painting", covered="解说讲过猫和花。")
    assert "forbidden" in user.lower()


def test_qa_system_requires_short_interrogative_question():
    from app.services.enrichment.prompts import _QA_SYSTEM

    s = _QA_SYSTEM.lower()
    assert "interrogative" in s and "ending in" in s
    assert "nothing after the" in s  # 问号后不许有描述


def test_qa_system_is_english_axis_no_chinese():
    import re

    from app.services.enrichment.prompts import _QA_SYSTEM

    assert "WRITE IN ENGLISH" in _QA_SYSTEM
    assert not re.search(r"[一-龥]", _QA_SYSTEM)  # prompt 绝不含中文(否则 LLM 输出中文)


def test_translation_prompt_forbids_source_fragments_language_agnostic():
    # 语言无关:任何目标语都要求'全部译出、不留源语言残片'(修 zh 漏翻 severed head 类;
    # ja/ko/zh-hant 同类问题自动受益。靠 {lang} 占位符,零语言特例)
    from app.services.enrichment.prompts import build_translation_prompt

    for lang_code in ("zh", "ja", "ko", "pl", "de"):
        system, _ = build_translation_prompt("x", lang_code)
        low = system.lower()
        assert "every" in low and "fragment" in low, lang_code
        # 不得含硬编码语言名单(如只提 chinese)
        assert "chinese-only" not in low


def test_faithfulness_prompt_flags_untranslated_fragments():
    # 闸假阴性修复:忠实度闸也要抓'未翻译的源语言残片'(修放行"卧 nude"类)
    from app.services.enrichment.prompts import build_faithfulness_prompt

    system, _ = build_faithfulness_prompt("A nude figure.", "《卧 nude》", "zh")
    low = system.lower()
    assert "untranslated" in low or "source-language" in low or "残" in system
    # 专有名词/标题豁免(不误判保留的原文标题)
    assert "proper noun" in low or "title" in low
