"""索引构建:全目录全图入索引;npz 读写往返带模型版本。"""

import numpy as np
from PIL import Image

from scripts.recognition_bench.build_index import build_index, load_index, save_index


def test_build_and_roundtrip(tmp_path):
    manifest = {
        "objects": [
            {"qid": "Q1", "images": ["u1", "u2"]},
            {"qid": "Q2", "images": ["u3", "bad"]},
        ]
    }
    fake_vec = {"u1": [1, 0], "u2": [0.9, 0.1], "u3": [0, 1]}
    urls_seen = []

    def loader(url):
        urls_seen.append(url)
        return Image.new("RGB", (8, 8)) if url != "bad" else None

    def embed(img):
        v = np.array(fake_vec[urls_seen[-1]], dtype=np.float32)  # loader 刚看过的 url
        return v / np.linalg.norm(v)

    vecs, qids = build_index(manifest, embed, loader)
    assert vecs.shape == (3, 2) and qids == ["Q1", "Q1", "Q2"]  # bad 被跳过

    p = tmp_path / "i.npz"
    save_index(p, vecs, qids, model="dinov2")
    v2, q2, m2 = load_index(p)
    assert np.allclose(v2, vecs) and q2 == qids and m2 == "dinov2"
