"""embedder:模型懒下载/校验失败降级 None/单例;不加载真模型。"""

import hashlib

import app.services.recognition.embedder as emb


class _Storage:
    def __init__(self, data):
        self.data = data

    def get(self, key):
        return self.data


def _pin_sha(monkeypatch, sha):
    cfg = dict(emb.MODELS[emb.MODEL_NAME], sha256=sha)
    monkeypatch.setitem(emb.MODELS, emb.MODEL_NAME, cfg)


def test_download_verify_and_singleton(monkeypatch, tmp_path):
    emb._reset_for_test()
    blob = b"fake-onnx"
    monkeypatch.setattr(emb, "_get_storage", lambda: _Storage(blob))
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    _pin_sha(monkeypatch, hashlib.sha256(blob).hexdigest())
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
    _pin_sha(monkeypatch, "deadbeef")
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


def test_model_switch_picks_file_and_preset(monkeypatch, tmp_path):
    # RECOG_MODEL=dinov3-vits16 → 拉 v3 文件、用 v3 预处理(换引擎只改一个配置)
    emb._reset_for_test()
    blob = b"fake-v3"
    keys = []

    class _S:
        def get(self, key):
            keys.append(key)
            return blob

    monkeypatch.setattr(emb, "MODEL_NAME", "dinov3-vits16")
    monkeypatch.setattr(emb, "_get_storage", lambda: _S())
    monkeypatch.setattr(emb.settings, "RECOG_MODEL_CACHE", str(tmp_path))
    _pin_sha(monkeypatch, hashlib.sha256(blob).hexdigest())
    presets = []
    monkeypatch.setattr(
        emb, "OnnxEmbedder", lambda path, preset: presets.append(preset) or "E"
    )
    assert emb.get_embedder() == "E"
    assert keys == ["models/dinov3_vits16.onnx"] and presets == ["dinov3"]


def test_dinov3_preprocess_keeps_whole_image():
    # v3 官方预处理=整图缩放不裁边:宽图两侧的内容必须还在(v2 会被中心裁掉)
    from PIL import Image

    img = Image.new("RGB", (800, 200), (0, 0, 0))
    img.paste((255, 255, 255), (0, 0, 80, 200))  # 最左 10% 白条
    x3 = emb.preprocess(img, "dinov3")
    x2 = emb.preprocess(img, "dinov2")
    assert x3.shape == x2.shape == (1, 3, 224, 224)
    assert x3[0, 0, :, 0].mean() > 1.5  # 白条在 v3 输入里
    assert x2[0, 0, :, 0].mean() < 0  # v2 中心裁掉了它
