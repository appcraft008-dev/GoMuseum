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


def test_faithfulness_prompt_judges_facts_only():
    """忠实度闸**只判事实一致**,不判翻译完整性(契约纪律 26:一个闸只判一件事)。

    这条取代了原来的 test_faithfulness_prompt_flags_untranslated_fragments。
    两件事压在同一个布尔里时,实测拦截理由绝大多数是"有词没翻译",而且判得很差 ——
    把德语规范译名 Freiheit erleuchtet die Welt 说成「Statue of Liberty 没翻译」、
    把法语地名 Canal du Loing、波兰语 Tiara Sajtafernesa 说成"英语没翻译"。
    翻译完整性/语言混杂由 lang_detect 独立判(见下一条测试),这里必须闭嘴。
    """
    from app.services.enrichment.prompts import build_faithfulness_prompt

    system, _ = build_faithfulness_prompt("A nude figure.", "《卧 nude》", "zh")
    low = system.lower()
    assert "fact" in low, "必须自我定位为事实判定"
    assert "do not judge translation completeness" in low, "必须显式放弃判完整性"
    assert "checked elsewhere" in low, "必须说明语言检查在别处"
    # 专有名词豁免仍要在(否则规范译名又会被当错译)
    assert "proper noun" in low and "not a fault" in low


def test_language_gate_catches_what_faithfulness_stopped_judging():
    """职责移交必须有人接住 —— 否则就是把检查丢了,不是拆开。

    忠实度闸不再管"有英文词没翻译"(上一条),那它必须被 lang_detect 接住:
    「卧 nude」这类混杂文本要判否,纯中文要判是。两处调用方(qa_suggester 的
    lang_ok、translator 的 _lang_ok)会把两个闸 and 起来。
    """
    from app.services.enrichment.lang_detect import text_in_language

    assert text_in_language("这是一幅描绘卧姿人体的油画作品,笔触细腻。", "zh")
    assert not text_in_language("This is an oil painting of a reclining figure.", "zh")


def test_translation_prompt_prefers_established_exonym():
    # Layer3:知名专有名词/标题优先用目标语言既定译名(Salome→莎乐美),不留英文原名
    # (语言无关:靠 {lang} 与"established form"表述,不硬编具体译名表)
    from app.services.enrichment.prompts import build_translation_prompt

    for lang_code in ("zh", "ja", "ko", "pl"):
        system, _ = build_translation_prompt("x", lang_code)
        low = system.lower()
        assert "established" in low
        # 要求"存在既定译名则用之",而非仅"保留原文或既定译名"的二选一
        assert "prefer" in low or "use it" in low or "use the" in low
        assert "consistent" in low  # 全文一致


def test_translation_prompt_pins_canonical_title():
    # 标题真相唯一化:内容翻译收到显示名标题→正文必须用它(消除'显现'vs'幻影'分叉)
    from app.services.enrichment.prompts import build_translation_prompt

    system, _ = build_translation_prompt(
        "The Apparition is famous.", "zh", title="幻影"
    )
    assert "幻影" in system
    low = system.lower()
    assert "title" in low
    # 无 title 时不注入,行为不变
    s2, _ = build_translation_prompt("x", "zh")
    assert "幻影" not in s2


def test_name_translation_prompt_no_fragments_and_standard():
    # 显示名翻译也要:全部译出无残片(卧 nude→卧姿裸女)+标准音译(奥林匹亚非奥林比亚)
    from app.services.enrichment.prompts import build_name_translation_prompt

    system, _ = build_name_translation_prompt("Reclining Nude", "zh")
    low = system.lower()
    assert "fragment" in low or "every word" in low
    assert "standard" in low or "conventional" in low


def test_faithfulness_prompt_declares_canonical_title_authoritative():
    """规范标题必须告知检查器,否则它拿英文直译当标准、把传统名判成错译。

    实测 Q3745385《Red-Haired Girl》:德语传统名是「Russisches Mädchen」、
    意语 Wikidata 标签是「Fille rousse」—— 都是有来源的事实。不告知时检查器报
    "incorrectly refers to the painting as ... instead of 'Rothaariges Mädchen'",
    于是这两段被永久卡在 needs_review:翻译侧注入规范标题(对的)→ 检查侧不知情
    判不忠实 → 强模型重译仍用同一标题 → 还是不过。**两侧假设冲突,重跑修不好。**
    """
    from app.services.enrichment.prompts import build_faithfulness_prompt

    _, user = build_faithfulness_prompt(
        "Take a look at the Red-Haired Girl by Modigliani.",
        "Betrachten Sie das „Russische Mädchen“ von Modigliani.",
        "de",
        title="Russisches Mädchen",
    )
    assert "Russisches Mädchen" in user, "规范标题必须出现在给检查器的消息里"
    low = user.lower()
    assert "canonical" in low
    assert (
        "correct" in low and "cannot be an infidelity" in low
    ), "必须明确声明它不算不忠实"

    # 不传规范名时行为不变(老调用方不受影响)
    _, plain = build_faithfulness_prompt("A.", "B.", "de")
    assert "canonical" not in plain.lower()
    assert plain.startswith("SOURCE (English):")


def test_faithfulness_prompt_declares_canonical_artist_authoritative():
    """作者规范名是标题那桩冤案的**同构第二例**,同一个注入机制的另一半。

    翻译侧把 artists.name_i18n 当 glossary 注入译文(消除作者称呼分叉,是对的),
    检查侧却不知情 → 把规范作者名判成错译。实测 539 段复检里判「真不忠实」的
    147 段,抱怨的几乎全是作者名:「'Michel-Ange Buronarroti' 应为 'Michel-Ange'」、
    「'Vouet' 不该译成 '西蒙·沃特'」。修一个实例时要把整类一起修(契约纪律 22)。
    """
    from app.services.enrichment.prompts import build_faithfulness_prompt

    _, user = build_faithfulness_prompt(
        "Vouet painted this in Rome.",
        "西蒙·沃埃在罗马画了这幅作品。",
        "zh",
        artist="西蒙·沃埃",
    )
    assert "西蒙·沃埃" in user, "规范作者名必须出现在给检查器的消息里"
    low = user.lower()
    assert "canonical" in low and "artist" in low
    assert "cannot be an infidelity" in low

    # 标题与作者可同时给,也可只给其一
    _, both = build_faithfulness_prompt(
        "A.", "B.", "zh", title="奥林匹亚", artist="马奈"
    )
    assert "奥林匹亚" in both and "马奈" in both


def test_faithfulness_note_does_not_grant_blanket_leniency():
    """NOTE 必须显式圈定「只豁免名字写法」,否则等于把检查器整体调宽松。

    这条不是假想:539 段复检里 68.8% 因加了标题提示而翻盘,当时的替代解释正是
    "NOTE 只是让检查器变宽容了"。抽 60 条重跑旧 prompt 读原始抱怨才排除掉
    (约 50 条抱怨的确实是标题)。加入作者名后覆盖面更宽,护栏必须写进 prompt。

    2026-09-03 note 措辞改成 STEP0/STEP1 两步式(见 build_faithfulness_prompt
    docstring),断言随之改为新措辞,但意图不变:STEP1 必须显式把"判断范围"
    限定回"剩下的事实"，不能通篇不再提"其余照常判"。
    """
    from app.services.enrichment.prompts import build_faithfulness_prompt

    _, user = build_faithfulness_prompt("A.", "B.", "de", title="X", artist="Y")
    low = user.lower()
    assert "name/title translation choice" in low, "缺少防整体放宽的护栏句"
    assert "step 1" in low and "judge only the remaining facts" in low


def test_translation_prompt_does_not_demo_language_label_format():
    """输入不得写成「语言名: 内容」—— 那是格式示范,模型会照猫画虎回贴目标语言名。

    实测 prod 存量 **1088 段**译文以 "Polish:" / "Italiano:" / "German:" 开头
    (pl 289 / it 267 / de 144 / es 144 / ja 98 / fr 91 …,涉及 900+ 件作品),
    根因就是 user 消息曾写成 `English:\n{en_body}`。system 里那句
    "Return ONLY the translated text" 拦不住 —— **格式示范比指令更强**。
    """
    from app.services.enrichment.prompts import build_translation_prompt

    _, user = build_translation_prompt("Take a look at the painting.", "pl")
    assert not user.lstrip().lower().startswith("english:"), "不得用语言名标签开头"
    assert "Take a look at the painting." in user


def test_strip_language_label_handles_english_and_native_names():
    """两道闸都抓不到这种形式缺陷,所以要有独立的形式检查兜底。"""
    from app.services.enrichment.lang_config import strip_language_label as strip

    assert strip("Polish:\nPoświęć chwilę") == "Poświęć chwilę"
    assert strip("Italiano:  \nMentre ti trovi") == "Mentre ti trovi"
    assert strip("Italiano: Questo disegno") == "Questo disegno"  # 同行也要剥
    assert strip("日本語：\nこの絵画は") == "この絵画は"  # 全角冒号
    assert strip("Traditional Chinese:\n這幅畫") == "這幅畫"  # 多词语言名
    assert strip("中文（繁體）：\n這幅畫") == "這幅畫"  # 语言名带括号补充
    assert strip("Français :\nPrenez un") == "Prenez un"  # 法式排版冒号前有空格

    # 绝不能误伤 —— 以下都是 prod 里 facts 段的**合法开头**(广谱扫描实测存在)。
    # 如果按"短词+冒号"通用剥离,这些正文会被削掉头。误伤比漏网糟。
    assert strip("Oto ciekawostka: Gustave") == "Oto ciekawostka: Gustave"
    assert strip("Ecco un curioso aneddoto: Il") == "Ecco un curioso aneddoto: Il"
    assert strip("흥미로운 사실이 있습니다: 이") == "흥미로운 사실이 있습니다: 이"
    assert strip("這裡有個有趣的小知識：這幅") == "這裡有個有趣的小知識：這幅"
    assert strip("Notes: 这是合法正文") == "Notes: 这是合法正文"
    assert strip("正常正文，没有前缀") == "正常正文，没有前缀"
    assert strip("") == ""
