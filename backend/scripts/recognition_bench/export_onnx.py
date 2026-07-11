"""一次性:HF transformers → 两个 ONNX(dinov2-small CLS 塔 / CLIP ViT-B/32 图像塔)。
torch/transformers 只许在本文件 import(bench group,不进生产)。"""

from __future__ import annotations

from pathlib import Path

import torch

DATA = Path(__file__).parent / "data"


class _Dinov2Wrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        # last_hidden_state 已过最终 layernorm;[:,0]=CLS token(384维)
        return self.m(pixel_values=pixel_values).last_hidden_state[:, 0]


class _ClipWrap(torch.nn.Module):
    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, pixel_values):
        return self.m(pixel_values=pixel_values).image_embeds  # 512维投影


def _export(model, path: Path):
    model.eval()
    dummy = torch.zeros(1, 3, 224, 224)
    torch.onnx.export(
        model,
        dummy,
        str(path),
        input_names=["pixel_values"],
        output_names=["emb"],
        dynamic_axes={"pixel_values": {0: "b"}, "emb": {0: "b"}},
        opset_version=17,
        dynamo=False,  # torch 2.13 默认 dynamo 走 onnxscript(未装);用旧版 TorchScript 导出器
    )
    print(f"exported {path} ({path.stat().st_size/1e6:.0f} MB)")


def main():
    from transformers import AutoModel, CLIPVisionModelWithProjection

    DATA.mkdir(exist_ok=True)
    _export(
        _Dinov2Wrap(AutoModel.from_pretrained("facebook/dinov2-small")),
        DATA / "dinov2_vits14.onnx",
    )
    _export(
        _ClipWrap(
            CLIPVisionModelWithProjection.from_pretrained(
                "openai/clip-vit-base-patch32"
            )
        ),
        DATA / "clip_vitb32.onnx",
    )


if __name__ == "__main__":
    main()
