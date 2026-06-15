import app.services.storage as storage_mod
from app.services.storage.local import LocalObjectStorage


def test_factory_returns_local_singleton(monkeypatch):
    storage_mod._instance = None  # 重置单例
    monkeypatch.setattr(
        "app.services.storage.settings.STORAGE_BACKEND", "local", raising=False
    )
    s1 = storage_mod.get_object_storage()
    s2 = storage_mod.get_object_storage()
    assert isinstance(s1, LocalObjectStorage)
    assert s1 is s2
