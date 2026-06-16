from app.models.museum_object import MuseumObject


def test_museum_object_has_sources_column_default_dict():
    assert "sources" in MuseumObject.__table__.columns
    col = MuseumObject.__table__.columns["sources"]
    assert col.nullable is False
    # 列默认（flush 时生效，故断言列元数据已配置默认，而非未 flush 的实例值；
    # 不比较 callable 身份——SQLAlchemy 会把 default=dict 包成 wrapper）
    assert col.default is not None  # Python 侧默认 default=dict 被删则触发
    assert col.server_default is not None  # server_default="{}" 被删则触发
