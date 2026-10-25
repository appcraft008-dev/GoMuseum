"""核验生成侧的合格判定(契约「音频批量生产与灌入」⑫)。

为什么单独成一个模块:这里是纯函数,不碰 DB / 对象存储,**测试才能直接 import**。
放在 `audio_ingest_cli.py` 里的话,测试要连带加载 SessionLocal 等一堆东西,
缺依赖时只能 skip —— 而 skip 掉的测试和通过的测试在报告里长得一样。

背景:灌入端的 `check_audio` 只判时长比例与替换偏差,**不看谐波锐度、
不看内容一致性**。生成侧唯一的质量判据在灌入侧没有对应护栏,目录里放什么就传什么。
实测已漏进 prod 一条(Q3937645/ja/qa_0),而当时 md5 逐条核对 127/127 全过 ——
核的是"上传的和本地一致",**验不出"本地这条本身没过闸"**。
"""

import hashlib
import json


def load_verdicts(root, *, apply: bool, allow_unverified: bool):
    """读生成侧的判定结果 `_state.json`。

    返回 None = 不做核验,只在 dry-run 或显式 `--allow-unverified` 时允许。
    `--apply` 却没有该文件时抛 SystemExit:**这道护栏的失败方向必须是拒绝**,
    悄悄降级成"不校验"等于没装。
    """
    f = root / "_state.json"
    if f.exists():
        return json.loads(f.read_text())
    if not apply or allow_unverified:
        return None
    raise SystemExit(
        f"❌ {f} 不存在,拒绝 --apply。\n"
        "   生成侧的合格判定必须随文件一起交付(契约 音频节⑫)。\n"
        "   外部引擎产出、确实没有该文件时,显式加 --allow-unverified。"
    )


def verdict_problem(
    verdicts: dict, name: str, data: bytes, *, allow_legacy: bool = False
) -> str | None:
    """这条产物有没有问题?没有则返回 None。

    - 判定记录缺失 → 可能是拷错目录 / 别批残留
    - 判定为不合格 → 生成侧三次都没过闸
    - 缺 md5/pipeline → 不是仓库 tools/tts/start_run.sh 产的
    - md5 不符     → 传输损坏,或文件被换过

    缺 md5/pipeline 默认拒绝:2026-10-19 起有批次绕过仓库脚本、用了生成机上
    8 月的旧副本(没有响度归一),535 条照样灌进 prod,线上响度极差 12.1dB。
    旧副本不写这两个字段,所以这道闸能把它挡在门外。真要重灌老批次,显式
    `allow_legacy`。
    """
    rec = verdicts.get(name)
    if rec is None:
        return "no_verdict(不在 _state.json 里,可能是拷错目录或别批残留)"
    if not rec.get("ok"):
        return (
            f"gate_failed(生成侧判定 ok=false,"
            f"sharp={rec.get('sharp')} consist={rec.get('consist')})"
        )
    want = rec.get("md5")
    if not allow_legacy and not (want and rec.get("pipeline")):
        return (
            "unverified_pipeline(判定记录缺 md5/pipeline,不是 tools/tts/start_run.sh "
            "产的;老批次重灌显式加 --allow-legacy-state)"
        )
    if want and hashlib.md5(data).hexdigest() != want:
        return "md5_mismatch(与判定时的内容不符,传输损坏或文件被换过)"
    return None
