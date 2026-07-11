"""索引构建:manifest 全目录所有参考图 → 向量矩阵 .npz(带模型名版本化)。
每件全部 ObjectImage 入索引——多视角对雕塑关键(查询时同 qid 取最大分)。"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import numpy as np

DATA = Path(__file__).parent / "data"


def build_index(manifest: dict, embed_fn, img_loader):
    vecs, qids = [], []
    for o in manifest["objects"]:
        for url in o["images"]:
            img = img_loader(url)
            if img is None:
                continue
            vecs.append(embed_fn(img))
            qids.append(o["qid"])
    return np.stack(vecs).astype(np.float32), qids


def save_index(path, vecs, qids, model: str):
    np.savez_compressed(path, vecs=vecs, qids=np.array(qids), model=model)


def load_index(path):
    z = np.load(path, allow_pickle=False)
    return z["vecs"], [str(q) for q in z["qids"]], str(z["model"])


def _cached_loader():
    """URL → PIL.Image,磁盘缓存 data/refimgs/(幂等,断点续跑)。"""
    from PIL import Image

    from scripts.recognition_bench.build_testset import _download

    refdir = DATA / "refimgs"

    def load(url):
        dest = refdir / (hashlib.sha1(url.encode()).hexdigest()[:16] + ".jpg")
        if _download(url, dest):
            return Image.open(dest)
        return None

    return load


def main():
    preset = sys.argv[1]  # dinov2 | clip
    from scripts.recognition_bench.embed import OnnxEmbedder

    onnx = {"dinov2": "dinov2_vits14.onnx", "clip": "clip_vitb32.onnx"}[preset]
    embedder = OnnxEmbedder(str(DATA / onnx), preset)
    manifest = json.loads((DATA / "manifest.json").read_text())
    vecs, qids = build_index(manifest, embedder.embed, _cached_loader())
    save_index(DATA / f"index_{preset}.npz", vecs, qids, model=preset)
    print(f"index_{preset}.npz: {vecs.shape[0]} vecs, {len(set(qids))} objects")


if __name__ == "__main__":
    main()
