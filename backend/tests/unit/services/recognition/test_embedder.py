"""embedder:模型懒下载/校验失败降级 None/单例;不加载真模型。"""

import hashlib

import app.services.recognition.embedder as emb


class _Storage:
    def __init__(self, data):
        self.data = data

    def get(self, key):
        return self.data


def test_download_verify_and_singleton(monkeypatch, tmp_path):
    emb._reset_for_test()
    blob = b"fake-onnx"
    monkeypatch.setattr(emb, "_get_storage", lambda: _Storage(blob))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(
        emb.settings, "RECOG_MODEL_SHA256", hashlib.sha256(blob).hexdigest()
    )
    created = []
    monkeypatch.setattr(
        emb, "OnnxEmbedder", lambda path, preset: created.append(path) or "ENGINE"
    )
    assert emb.get_embedder() == "ENGINE"
    assert emb.get_embedder() == "ENGINE"  # 单例
    assert len(created) == 1
    assert (tmp_path / "dinov2_vits14.onnx").read_bytes() == blob


def test_bad_sha_returns_none(monkeypatch, tmp_path):
    emb._reset_for_test()
    monkeypatch.setattr(emb, "_get_storage", lambda: _Storage(b"corrupt"))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_SHA256", "deadbeef")
    assert emb.get_embedder() is None


def test_storage_failure_returns_none(monkeypatch, tmp_path):
    emb._reset_for_test()

    def boom():
        raise RuntimeError("no storage")

    monkeypatch.setattr(emb, "_get_storage", boom)
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    assert emb.get_embedder() is None


def test_crop_pyramid_boxes():
    from PIL import Image

    crops = emb.crop_pyramid(Image.new("RGB", (1000, 800)))
    assert len(crops) == 8
    # center-60% 框 = (0.2,0.2,0.8,0.8) × (1000,800) → 600×480
    assert crops[0].size == (600, 480)
    # 左半幅框 = (0,0,0.55,1) × (1000,800) → 550×800
    assert crops[6].size == (550, 800)
