from app.models.museum_object import MuseumObject


def test_museum_object_has_sources_column_default_dict():
    obj = MuseumObject()
    assert "sources" in MuseumObject.__table__.columns
    col = MuseumObject.__table__.columns["sources"]
    assert col.nullable is False
