"""线上 embedding 引擎:DINOv2 ONNX 推理 + 模型 R2 懒下载。
引擎不可用一律返回 None → 编排层自动走 GPT+OCR 兜底(优雅降级,不 500)。
preprocess/OnnxEmbedder 与 bench 同源(bench re-export 本模块)。"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from pathlib import Path

import numpy as np
from PIL import Image

from app.core.config import settings

logger = logging.getLogger(__name__)

MODEL_NAME = "dinov2-vits14"

PRESETS = {
    "dinov2": {
        "resize": 256,
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
    },
    "clip": {
        "resize": 224,
        "mean": [0.48145466, 0.4578275, 0.40821073],
        "std": [0.26862954, 0.26130258, 0.27577711],
    },
}


# 全景式拍法(画占画面小)的裁剪金字塔:中心 60%/35% + 四角 55% 象限(分数框 l,t,r,b)。
CROPS: list[tuple[float, float, float, float]] = [
    (0.2, 0.2, 0.8, 0.8),
    (0.325, 0.325, 0.675, 0.675),
    (0, 0, 0.55, 0.55),
    (0.45, 0, 1, 0.55),
    (0, 0.45, 0.55, 1),
    (0.45, 0.45, 1, 1),
    # 合影构图(画占一侧+人占一侧)对症——实证《世界的起源》象限裁剪只到0.711差线,半幅可过。
    (0, 0, 0.55, 1),
    (0.45, 0, 1, 1),
]


def crop_pyramid(img: Image.Image) -> list[Image.Image]:
    img = img.convert("RGB")
    w, h = img.size
    return [
        img.crop((round(l * w), round(t * h), round(r * w), round(b * h)))
        for (l, t, r, b) in CROPS
    ]


def preprocess(img: Image.Image, preset: str) -> np.ndarray:
    cfg = PRESETS[preset]
    img = img.convert("RGB")
    w, h = img.size
    scale = cfg["resize"] / min(w, h)
    img = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    img = img.crop((left, top, left + 224, top + 224))
    x = np.asarray(img, dtype=np.float32) / 255.0
    x = (x - np.array(cfg["mean"], dtype=np.float32)) / np.array(
        cfg["std"], dtype=np.float32
    )
    return x.transpose(2, 0, 1)[None]


class OnnxEmbedder:
    def __init__(self, onnx_path: str, preset: str):
        import onnxruntime as ort  # 懒加载

        self.preset = preset
        self.sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name

    def embed(self, img: Image.Image) -> np.ndarray:
        out = self.sess.run(None, {self.input_name: preprocess(img, self.preset)})
        v = out[0][0].astype(np.float32)
        return v / np.linalg.norm(v)

    def embed_batch(self, imgs: list[Image.Image]) -> np.ndarray:
        """一次 sess.run 批量推理(ONNX 有动态 batch 轴),每行 L2 归一化 → [N,D]。"""
        batch = np.concatenate([preprocess(im, self.preset) for im in imgs], axis=0)
        out = self.sess.run(None, {self.input_name: batch})[0].astype(np.float32)
        return out / np.linalg.norm(out, axis=1, keepdims=True)


def _get_storage():
    from app.services.storage import get_object_storage

    return get_object_storage()


_lock = threading.Lock()
_engine = None
_retry_after = 0.0
_RETRY_COOLDOWN = 60.0


def _reset_for_test():
    global _engine, _retry_after
    _engine, _retry_after = None, 0.0


def get_embedder():
    """单例;失败返回 None 且 60s 内不重试(避免每请求重复打 R2)。"""
    global _engine, _retry_after
    if _engine is not None:
        return _engine
    if time.time() < _retry_after:
        return None
    with _lock:
        if _engine is not None:
            return _engine
        if time.time() < _retry_after:  # 并发冷启动:首个失败后其余不重试
            return None
        try:
            cache = Path(settings.RECOG_MODEL_CACHE)
            local = cache / Path(settings.RECOG_MODEL_KEY).name
            if not local.exists():
                data = _get_storage().get(settings.RECOG_MODEL_KEY)
                if not data:
                    raise RuntimeError(
                        f"model missing in storage: {settings.RECOG_MODEL_KEY}"
                    )
                want = settings.RECOG_MODEL_SHA256
                if want and hashlib.sha256(data).hexdigest() != want:
                    raise RuntimeError("model sha256 mismatch")
                cache.mkdir(parents=True, exist_ok=True)
                tmp = local.with_suffix(".tmp")
                tmp.write_bytes(data)
                os.replace(tmp, local)  # 原子替换:防半写文件被当有效缓存
            _engine = OnnxEmbedder(str(local), "dinov2")
            logger.info("recognition embedder ready: %s", local)
            return _engine
        except Exception:
            logger.exception("embedder unavailable, falling back to GPT chain")
            _retry_after = time.time() + _RETRY_COOLDOWN
            return None
