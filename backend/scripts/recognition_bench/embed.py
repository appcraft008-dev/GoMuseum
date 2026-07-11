"""bench 复用线上引擎实现(单一来源,见 app/services/recognition/embedder.py)。"""

from app.services.recognition.embedder import (  # noqa: F401
    PRESETS,
    OnnxEmbedder,
    preprocess,
)
