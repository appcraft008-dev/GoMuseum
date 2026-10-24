"""VoxCPM2 生成搬到 Modal L40S(按秒计费,用完自动缩到 0)。只做 generate,
语速/响度/mp3/质检仍在本机 run_batch.py 里做 —— 判定口径只有一份。

由 run_batch.py 在 TTS_GPU=modal 时 import,不单独运行。

⚠️ 必须 fp32:CUDA 上 voxcpm 默认按检查点的 bf16 跑,Mac(MPS)被它强制 fp32。
2026-10-24 试点 21 条:bf16 亮度系统性偏暗 7%(超出 Mac 重抽噪声),英文盲听
0 胜 3 负;fp32 指纹落在 Mac 噪声内、盲听未输。速度 rtf 0.66(Mac 3.33)。
"""

import io
import time
from pathlib import Path

import modal

# 与 Mac 生产环境锁同版本(~/tts-lab/venv 的 freeze),版本漂移 = 音色漂移
image = (
    modal.Image.debian_slim(python_version="3.11")
    .apt_install("ffmpeg")  # torchcodec 读种子 wav 要 ffmpeg 动态库
    .pip_install(
        "voxcpm==2.0.3", "torch==2.13.0", "torchaudio==2.11.0", "torchcodec==0.15.0",
        "transformers==5.14.1", "funasr==1.3.14", "wetext==0.1.4", "numpy==2.4.6",
        "safetensors==0.8.0", "huggingface_hub==1.23.0", "soundfile==0.14.0",
    )
    .run_commands(
        "python -c \"from huggingface_hub import snapshot_download; "
        "snapshot_download('openbmb/VoxCPM2')\""
    )
)
app = modal.App("gomuseum-voxcpm", image=image)
USD_PER_S = 0.0006  # L40S $0.000542/s + CPU/内存余量,费用闸用的保守估计


# ponytail: 单容器串行;要更快把 max_containers 调大(本机质检会先成瓶颈)
@app.cls(gpu="L40S", timeout=3600, max_containers=1, scaledown_window=60)
class TTS:
    @modal.enter()
    def load(self):
        import voxcpm.model.voxcpm2 as v2
        from voxcpm import VoxCPM

        # 复刻 Mac:MPS 上 voxcpm 走的就是这个钩子把 bf16 改成 float32
        v2.pick_runtime_dtype = lambda device, dtype: "float32"
        self.m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)

    @modal.method()
    def gen(self, text: str, seed_wav: bytes, cfg: float, timesteps: int) -> tuple[bytes, float]:
        import numpy as np
        import soundfile as sf

        seed = Path("/tmp/seed.wav")  # 种子只在容器临时盘,不落 Volume
        seed.write_bytes(seed_wav)
        t0 = time.time()
        wav = self.m.generate(text=text, reference_wav_path=str(seed),
                              cfg_value=cfg, inference_timesteps=timesteps)
        dt = time.time() - t0
        buf = io.BytesIO()
        sf.write(buf, np.asarray(wav, dtype=np.float32), self.m.tts_model.sample_rate,
                 format="WAV")
        return buf.getvalue(), dt
