"""embedding 引擎:ONNX CPU 推理 + 各模型预处理。接口 embed(img)->单位向量。
这块将来直接搬线上引擎位(spec ①);onnxruntime 懒 import,纯逻辑可无重依赖单测。"""

from __future__ import annotations

import numpy as np
from PIL import Image

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


def preprocess(img: Image.Image, preset: str) -> np.ndarray:
    cfg = PRESETS[preset]
    img = img.convert("RGB")
    w, h = img.size
    scale = cfg["resize"] / min(w, h)
    img = img.resize((round(w * scale), round(h * scale)), Image.BICUBIC)
    w, h = img.size
    left, top = (w - 224) // 2, (h - 224) // 2
    img = img.crop((left, top, left + 224, top + 224))
    x = np.asarray(img, dtype=np.float32) / 255.0  # HWC
    x = (x - np.array(cfg["mean"], dtype=np.float32)) / np.array(
        cfg["std"], dtype=np.float32
    )
    return x.transpose(2, 0, 1)[None]  # 1CHW


class OnnxEmbedder:
    def __init__(self, onnx_path: str, preset: str):
        import onnxruntime as ort  # 懒加载:单测预处理不需要它

        self.preset = preset
        self.sess = ort.InferenceSession(onnx_path, providers=["CPUExecutionProvider"])
        self.input_name = self.sess.get_inputs()[0].name

    def embed(self, img: Image.Image) -> np.ndarray:
        out = self.sess.run(None, {self.input_name: preprocess(img, self.preset)})
        v = out[0][0].astype(np.float32)
        return v / np.linalg.norm(v)
