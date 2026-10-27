"""批量生产:读 jobs.json → 拉文本 → 单种子生成 → 语速/响度对齐 → 三关质检 → 160k mp3。
特性:幂等(已存在合格文件跳过)、断点续传、失败重试≤3、进度落盘。

用法: run_batch.py <jobs.json> <输出目录>
"""
import atexit
import hashlib
import io
import json
import os
import subprocess
import sys
import time
import warnings
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

warnings.filterwarnings("ignore")
import librosa
import mlx_whisper
import numpy as np
import soundfile as sf
from voxcpm import VoxCPM

from batch_record import make_record, pick
from consistency import consistency, length_ratio, spoken_len, tts_input
from fetch_text import fetch_text  # 取文本只此一份实现(含 502 重试)
from loudness import TARGET_LUFS, gain_db, measure

LAB = Path(os.environ.get("TTS_LAB", Path(__file__).resolve().parent))

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
# 种子对照实验开关:SEED_OVERRIDE="en=SEED_zh"(逗号分隔多项)。
# 只为做 A/B —— 选型结论一律写回上面的 dict,这里永远不留默认值,
# 否则"生产到底用了哪个种子"就有两处真相源。产物的 seed 字段记的是实际用的那个。
for _kv in filter(None, os.environ.get("SEED_OVERRIDE", "").split(",")):
    _k, _v = _kv.split("=")
    SEED_OF[_k] = _v
# 各语言语速基准(字/秒),来自 tts-1 在 Q152509《草地上的午餐》上的实测。
# ⚠️ 缺了这一步的后果实测过:28 条试点音频全部偏快,平均 +15%(fr +23%、es +18%),
# 远超配方 ①-④ 里"时长差 ≤7%"的验收线。VoxCPM2 原速就是比 tts-1 快,
# 定稿基准批是靠 atempo 压回去的(实测对齐误差 <0.05s),生产脚本必须继承。
# en/fr 按 spoken_len 计(数字加权),基准同比放大 1.041/1.038(修线上批均值),
# 让全体平均语速不变,只把数字密的段相对放慢。
RATE = {"zh": 4.64, "en": 16.49, "fr": 16.20, "de": 15.67, "es": 15.87,
        "it": 15.78, "pl": 14.86, "ja": 5.47, "ko": 7.31, "zh-hant": 4.71}
ATEMPO_MIN, ATEMPO_MAX = 0.75, 1.15   # 0.75 用户听不出;0.56 明确否决"明显拉长"
# 节奏偏好(软指标,不进 ok,只决定多次尝试里留哪条,见 batch_record.pick):
# atempo 只能整体缩放,缩放幅度大 = 这次生成原始节奏离目标远,内部停顿大概率
# 也不匀。10-25 意语 358 条 atempo 主体落在 0.80-1.00(mean 0.891,sd 0.046);
# 加偏好后 56 条 sd 0.038,约 12.5% 的条目多生成一次。边界取整是判断,未精确拟合。
ATEMPO_PREFER = (0.80, 1.00)
SHARP_MAX = 240.0       # 谐波锐度(丝丝)
# 为什么是 240 而不是原来的 200(2026-09-14 九条盲听定的,含真实被拦样本):
# 用户只按"丝丝声"盲评,判断与锐度值**不单调** —— 176 被评"最轻"、143 被评
# "不可接受"、被闸拦掉的 211(《但丁之舟》英语主讲解)被评"可接受"。而英语
# 232 条实测里失败值紧贴门槛(200 201 202 203 204…238),过闸值也紧贴
# (199.0 198.9 198.5…):**200 这一刀切在一团连续分布的正中间,两边听感无别**,
# 代价是英语 16.1% 的生成纯为它返工(一致性/长度比在英语上一次都没触发)。
# ⚠️ 这**不是**下面那条"为迁就坏结论放宽门槛"的重演 —— 那次是根因没修、
# 拿阈值打补丁;这次是拿人耳盲听证伪了指标本身在此区间的判别力。
# ⚠️ 也不要就此删掉这道闸:谐波锐度当年是在**种子之间**(差异大)验证出来的
# 判别式,拿来做**同种子单条样本的闸**从没验证过。240 保留的是防模型崩坏的
# 离群上界(实测最高 263),不再承担"挑出更好的一条"的职责。
# 240 有直评支撑:211 与 238 两档都判「可接受」,再往上 289(tts-1 跨模型锚点)
# 才降为「勉强」—— 门槛正落在直评由「可接受」转「勉强」的那一段里。
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

# TTS_GPU=modal:生成放 Modal L40S(见 modal_gen.py),其余全在本机,口径不变。
# GPU 模式下一条的首次生成提前在后台提交,与本条质检重叠,GPU 不空转。
GPU = os.environ.get("TTS_GPU") == "modal"
MAX_USD = float(os.environ.get("MAX_USD", "5"))  # 本次运行的费用闸(按墙钟保守估)
ENGINE = "modal-l40s-fp32" if GPU else "mac-mps-fp32"
PIPELINE = os.environ.get("TTS_PIPELINE")  # start_run.sh 注入起跑 commit;缺了灌入端会拒

_model = None


def model():
    global _model
    if _model is None:
        _model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    return _model


def generate(text, lang):
    """→ (float32 波形, 采样率)。"""
    seed = LAB / f"seeds_final/{SEED_OF[lang]}.wav"
    if GPU:
        import modal_gen
        wav, _ = modal_gen.TTS().gen.remote(text, seed.read_bytes(), CFG, TIMESTEPS)
        w, sr = sf.read(io.BytesIO(wav), dtype="float32")
        return w, sr
    m = model()
    wav = m.generate(text=text, reference_wav_path=str(seed),
                     cfg_value=CFG, inference_timesteps=TIMESTEPS)
    return np.asarray(wav, dtype=np.float32), m.tts_model.sample_rate


def prepare(j):
    """取文本 + (GPU 时)首次生成。在后台线程里跑,给下一条预取。"""
    text, lang = fetch_text(j), j["language"]
    # zh-hant 喂**简体**给模型(见 tts_input:模型认不全繁体专用字形)。
    # 质检、语速、长度比一律仍按原始正文 `text` 算 —— 用户读到的是它,
    # 口径不能跟着输入走(normalize() 本来两侧都转简体,读数零影响)。
    first = generate(tts_input(text, lang), lang) if text and GPU else None
    return text, first


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

    if GPU:
        import modal_gen
        run_ctx = modal_gen.app.run()
        run_ctx.__enter__()  # 容器空闲 60s 自动缩到 0
        atexit.register(run_ctx.__exit__, None, None, None)
        t_start = time.time()
    pool = ThreadPoolExecutor(1)
    nxt = pool.submit(prepare, todo[0][0]) if todo else None
    for i, (j, name) in enumerate(todo, 1):
        if GPU and (time.time() - t_start) * modal_gen.USD_PER_S > MAX_USD:
            print(f"💰 费用闸:估算已超 ${MAX_USD},停在第 {i} 条(调大 MAX_USD 续跑)", flush=True)
            break
        lang = j["language"]
        text, first = nxt.result()
        nxt = pool.submit(prepare, todo[i][0]) if i < len(todo) else None
        if not text:
            print(f"[{i}/{len(todo)}] {name} 无文本,跳过", flush=True)
            state[name] = {"ok": False, "reason": "no_text"}
            statef.write_text(json.dumps(state, ensure_ascii=False, indent=1))
            continue
        tries = []
        for attempt in range(1, MAX_TRY + 1):
            t0 = time.time()
            w, sr = first if attempt == 1 and first else generate(tts_input(text, lang), lang)
            raw = outdir / f"_tmp_{name}.wav"
            sf.write(raw, w, sr)
            # 每次尝试单独落一个文件:合格但节奏偏时会接着试,若后面那次反而
            # 没过闸,直接写 outdir/name 就会把已经合格的那条冲掉。
            mp3 = outdir / f"_try{attempt}_{name}"
            # 语速对齐:按该语言 tts-1 字/秒算目标时长,atempo 压回去。
            # atempo 只伸缩时间不改音高(实测 F0 190→188),且锐度/HNR 反而变好。
            at = min(max((len(w) / sr) / (spoken_len(text, lang) / RATE[lang]),
                         ATEMPO_MIN), ATEMPO_MAX)
            # 响度对齐:量一遍变速后的响度/峰值,算纯增益(见 loudness.py)。
            # 与语速对齐同理 —— **必须在生成侧做完**:灌入端的 check_audio 只看
            # 时长和替换偏差,三道质检门对音量完全免疫,下游没有任何东西能兜住。
            lufs, peak = measure(raw, at)
            g = gain_db(lufs, peak)
            filt = f"atempo={at:.4f}" + (f",volume={g:.2f}dB" if abs(g) >= 0.05 else "")
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw),
                            "-filter:a", filt,
                            "-codec:a", "libmp3lame", "-b:a", BITRATE, str(mp3)], check=True)
            raw.unlink(missing_ok=True)
            sharp, ratio, lr = qc(mp3, text, WLANG[lang])  # 对最终产物质检(atempo 之后)
            ok = (sharp < SHARP_BY_LANG.get(lang, SHARP_MAX)
                  and ratio >= CONSIST_BY_LANG.get(lang, CONSIST_MIN)
                  and LEN_RANGE[0] <= lr <= LEN_RANGE[1])
            paced = ATEMPO_PREFER[0] <= at <= ATEMPO_PREFER[1]
            gen = time.time() - t0
            print(f"[{i}/{len(todo)}] {name} 第{attempt}次 锐度={sharp:.0f}% 一致={ratio:.2f} "
                  f"长度比={lr:.2f} "
                  f"{len(w)/sr:.0f}s→{len(w)/sr/at:.0f}s(atempo {at:.2f}{'' if paced else ',偏'}) "
                  f"响度{lufs if lufs is None else round(lufs, 1)}→{TARGET_LUFS}({g:+.1f}dB) "
                  f"{'✅' if ok else '重试'} {gen:.0f}s", flush=True)
            tries.append({"try": attempt, "ok": ok, "sharp": round(sharp, 1),
                          "consist": round(ratio, 2), "lenratio": round(lr, 2),
                          "atempo": round(at, 3), "paced": paced, "engine": ENGINE,
                          "lufs_in": None if lufs is None else round(lufs, 1),
                          "gain": round(g, 2)})
            if ok and paced:
                break
        kept = pick(tries)
        for t in tries:
            f = outdir / f"_try{t['try']}_{name}"
            if t is tries[kept]:
                f.replace(outdir / name)
            else:
                f.unlink(missing_ok=True)
        if not tries[kept]["ok"]:
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

        # md5 让灌入端能核验"传过去的就是判定过的那一份"(契约 音频节⑫)。
        # 不合格条目的文件已被移走,算不到 md5,记 None。
        # 顶层分数为何取最后一次、tries 为何要留 —— 见 batch_record.make_record。
        final = outdir / name
        state[name] = make_record(
            tries, SEED_OF[lang],
            hashlib.md5(final.read_bytes()).hexdigest() if final.exists() else None,
            kept=kept, pipeline=PIPELINE)
        statef.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    done = sum(1 for v in state.values() if v.get("ok"))
    print(f"\n完成 {done}/{len(jobs)} 合格", flush=True)
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
