from app.services.storage.local import LocalObjectStorage


def test_put_get_exists_delete_and_url(tmp_path):
    s = LocalObjectStorage(root_dir=str(tmp_path), public_base_url="http://x/assets")
    key = "images/Q1/primary.jpg"
    assert s.exists(key) is False
    assert s.get(key) is None

    s.put(key, b"hello", "image/jpeg")
    assert s.exists(key) is True
    assert s.get(key) == b"hello"
    assert s.public_url(key) == "http://x/assets/images/Q1/primary.jpg"

    s.delete(key)
    assert s.exists(key) is False
