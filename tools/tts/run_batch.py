"""批量生产:读 jobs.json → 拉文本 → 单种子生成 → 三关质检 → 160k mp3。
特性:幂等(已存在合格文件跳过)、断点续传、失败重试≤3、进度落盘。

用法: run_batch.py <jobs.json> <输出目录>
"""
import json
import os
import subprocess
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")
import librosa
import mlx_whisper
import numpy as np
import requests
import soundfile as sf
from voxcpm import VoxCPM

from consistency import consistency, length_ratio

LAB = Path(os.environ.get("TTS_LAB", Path(__file__).resolve().parent))
API = os.environ.get("GOMUSEUM_API", "https://api.gomuseum.app/api/v1")

# ===== 定稿参数 =====
CFG, TIMESTEPS, BITRATE = 1.7, 10, "160k"
# 各语言定稿种子(选型已完成,生产不再双份)
SEED_OF = {
    "zh": "SEED_zh", "en": "SEED_en",
    "fr": "SEED_zh", "ko": "SEED_zh", "es": "SEED_zh",
    "it": "SEED_zh", "pl": "SEED_zh", "de": "SEED_zh",
    "ja": "SEED_en",        # 日语保持 EN:实测 EN 一致性 0.980 > ZH 0.963
                            # (ZH 种子浊音念错:「じっくり」→「つっくり」);
                            # ZH 锐度更好(103% vs 126%)但发音准确度优先。
    "zh-hant": "SEED_zh",   # ⚠️ 2026-08-31 纠正:原为 SEED_en,依据是"zh 种子念繁体
                            # 一致性仅 0.58"——**那是打分函数还坏着时测的**
                            # (autojunk + 无简繁归一化)。用修好的函数重测:
                            # ZH 0.951 / EN 0.913,锐度 ZH 144% / EN 189%,
                            # 耗时 ZH 148s / EN 187s —— 三项全胜。
                            # 转写实证:EN 种子把「花點時間仔細欣賞」念成
                            # 「哈点时间十岁新手」,用户听感"发音很怪"即源于此。
                            # 教训:判定工具修好后,**当初由它产出、已写进配方
                            # 当成定论的旧结论也必须重验**。
}
# 各语言语速基准(字/秒),来自 tts-1 在 Q152509《草地上的午餐》上的实测。
# ⚠️ 缺了这一步的后果实测过:28 条试点音频全部偏快,平均 +15%(fr +23%、es +18%),
# 远超配方 ①-④ 里"时长差 ≤7%"的验收线。VoxCPM2 原速就是比 tts-1 快,
# 定稿基准批是靠 atempo 压回去的(实测对齐误差 <0.05s),生产脚本必须继承。
RATE = {"zh": 4.64, "en": 15.84, "fr": 15.61, "de": 15.67, "es": 15.87,
        "it": 15.78, "pl": 14.86, "ja": 5.47, "ko": 7.31, "zh-hant": 4.71}
ATEMPO_MIN, ATEMPO_MAX = 0.75, 1.15   # 0.75 用户听不出;0.56 明确否决"明显拉长"
SHARP_MAX = 200.0       # 谐波锐度(丝丝)
# ⚠️ 曾为 zh-hant 放宽门槛(锐度 215 / 一致性 0.88),那是**为迁就 EN 种子的
# 差表现**加的补丁 —— 根因(种子选错)修掉后一并撤回:ZH 种子实测锐度 144%、
# 一致性 0.951,通用门槛绰绰有余。**为绕过某个坏结论加的补丁,在结论纠正后
# 必须撤掉**,否则它会继续放行本该被拦下的东西。
SHARP_BY_LANG: dict[str, float] = {}
CONSIST_MIN = 0.90      # 内容一致性
CONSIST_BY_LANG: dict[str, float] = {}
# 转写字数/原文字数。专抓**复读崩坏与截断** —— 比一致性阈值更直接:
# 实测崩坏的 de 那条转写 1547 字 vs 原文 1070 字(比值 1.45),末尾把同一句
# 复读了十几遍。有了这道独立的门,一致性阈值才敢为 zh-hant 放宽。
LEN_RANGE = (0.80, 1.25)
MAX_TRY = 3
WLANG = {"zh": "zh", "zh-hant": "zh", "en": "en", "fr": "fr", "de": "de",
         "es": "es", "it": "it", "pl": "pl", "ja": "ja", "ko": "ko"}
# ====================

_model = None


def model():
    global _model
    if _model is None:
        _model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    return _model


def fetch_text(job):
    """从 prod API 取文本(只读)。QA 按'问+答'拼接,与后端质量闸取文本方式一致。

    ⚠️ artist_bio 的 job["qid"] 是**作者 qid**,而 bio 正文挂在作品的 content
    响应上 —— 所以这类 job 必须额外带一个 job["via_qid"](该作者名下任一作品)。
    """
    qid, lang, sec = job["qid"], job["language"], job["section"]
    via = job.get("via_qid", qid)
    r = requests.get(f"{API}/museums/{job['museum']}/objects/{via}/content",
                     params={"language": lang}, timeout=30)
    r.raise_for_status()
    d = r.json()
    if sec == "artist_bio":
        return ((d.get("artist") or {}).get("bio")) or None
    if sec.startswith("qa_"):
        idx = int(sec.split("_", 1)[1])
        for q in (d.get("suggested_questions") or []):
            if q.get("sort") == idx:
                return f"{q['question']}\n\n{q['answer']}"
        return None
    if sec == "guide":
        return ((d.get("default_guide") or {}).get("body")) or None
    for t in (d.get("tabs") or []):
        # 🔴 字段名是 section_code,不是 code。第1批只做 guide(走 default_guide),
        # 从没走到这一行 —— 于是 t.get("code") 恒为 None,深度段会**全部**被判
        # "无文本,跳过",而且状态里写的是 no_text,看起来像内容缺失而不是 bug。
        if t.get("section_code") == sec:
            return t.get("body")
    return None


def qc(path, text, wl):
    y, _ = librosa.load(path, sr=22050, duration=60)
    S = np.abs(librosa.stft(y, n_fft=2048))
    H, P = librosa.decompose.hpss(S)
    sharp = float(P.sum() / (H.sum() + 1e-9) * 100)
    r = mlx_whisper.transcribe(str(path), path_or_hf_repo="mlx-community/whisper-small-mlx",
                               language=wl)
    tr = r["text"].strip()
    return sharp, consistency(text, tr), length_ratio(text, tr)


def main():
    jobs = json.load(open(sys.argv[1]))
    outdir = Path(sys.argv[2])
    outdir.mkdir(parents=True, exist_ok=True)
    statef = outdir / "_state.json"
    state = json.loads(statef.read_text()) if statef.exists() else {}

    todo = []
    for j in jobs:
        name = f"{j['qid']}__{j['language']}__{j['section']}.mp3"
        rec = state.get(name)
        if rec and rec.get("ok") and (outdir / name).exists():
            continue                      # 幂等:已有合格文件,跳过
        todo.append((j, name))
    print(f"总任务 {len(jobs)},待做 {len(todo)}(已完成 {len(jobs)-len(todo)})", flush=True)

    m = model()
    sr = m.tts_model.sample_rate
    for i, (j, name) in enumerate(todo, 1):
        lang = j["language"]
        text = fetch_text(j)
        if not text:
            print(f"[{i}/{len(todo)}] {name} 无文本,跳过", flush=True)
            state[name] = {"ok": False, "reason": "no_text"}
            statef.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            continue
        seed = LAB / f"seeds_final/{SEED_OF[lang]}.wav"
        best = None
        for attempt in range(1, MAX_TRY + 1):
            t0 = time.time()
            wav = m.generate(text=text, reference_wav_path=str(seed),
                             cfg_value=CFG, inference_timesteps=TIMESTEPS)
            w = np.asarray(wav, dtype=np.float32)
            raw = outdir / f"_tmp_{name}.wav"
            sf.write(raw, w, sr)
            mp3 = outdir / name
            # 语速对齐:按该语言 tts-1 字/秒算目标时长,atempo 压回去。
            # atempo 只伸缩时间不改音高(实测 F0 190→188),且锐度/HNR 反而变好。
            at = min(max((len(w) / sr) / (len(text) / RATE[lang]),
                         ATEMPO_MIN), ATEMPO_MAX)
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                            "-filter:a", f"atempo={at:.4f}",
                            "-codec:a", "libmp3lame", "-b:a", BITRATE, str(mp3)], check=True)
            raw.unlink(missing_ok=True)
            sharp, ratio, lr = qc(mp3, text, WLANG[lang])  # 对最终产物质检(atempo 之后)
            ok = (sharp < SHARP_BY_LANG.get(lang, SHARP_MAX)
                  and ratio >= CONSIST_BY_LANG.get(lang, CONSIST_MIN)
                  and LEN_RANGE[0] <= lr <= LEN_RANGE[1])
            gen = time.time() - t0
            print(f"[{i}/{len(todo)}] {name} 第{attempt}次 锐度={sharp:.0f}% 一致={ratio:.2f} "
                  f"长度比={lr:.2f} "
                  f"{len(w)/sr:.0f}s→{len(w)/sr/at:.0f}s(atempo {at:.2f}) "
                  f"{'✅' if ok else '重试'} {gen:.0f}s", flush=True)
            if best is None or (ok and not best[0]) or (ok and sharp < best[1]):
                best = (ok, sharp, ratio)
            if ok:
                break
        if not best[0]:
            # 三次都没过闸 → 把产物移出灌入目录(不是删掉)。
            # 必须移走:灌入端的 check_audio 只判时长比例与替换偏差,**不看锐度/
            # 一致性**,留在原地会一路绿灯进 prod(实测已漏进去一条 Q3937645/ja/qa_0)。
            # 又必须留着:排查"到底哪里不合格"要拿这条音频去转写比对 —— 第一版直接
            # unlink,结果查确定性失败时发现证据已被自己删干净。
            # _rejected/ 不在灌入端的查找路径上(它按 outdir/<name> 精确取文件)。
            # state 里的 ok=False 保留,重跑时会自动重做这一条。
            failed = outdir / name
            if failed.exists():
                rej = outdir / "_rejected"
                rej.mkdir(exist_ok=True)
                failed.replace(rej / name)

        state[name] = {"ok": bool(best[0]), "sharp": round(best[1], 1),
                       "consist": round(best[2], 2), "lenratio": round(lr, 2),
                       "seed": SEED_OF[lang],
                       "atempo": round(at, 3)}
        statef.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    done = sum(1 for v in state.values() if v.get("ok"))
    print(f"\n完成 {done}/{len(jobs)} 合格", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
