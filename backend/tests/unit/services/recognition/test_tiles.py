"""宽幅作品识别切块:切法 + 落库 + 不进图集/分享。"""

import pytest
from PIL import Image
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base
from app.models.artist import Artist
from app.models.content import (
    CategorySection,
    ObjectContentSection,
    ObjectSuggestedQuestion,
    SectionType,
)
from app.models.museum import Museum
from app.models.museum_object import MuseumObject, ObjectImage
from app.services import museum_repo, share
from app.services.object_importer import upsert_museum, upsert_object
from app.services.recognition.tiles import add_tiles, tile_boxes


def test_not_wide_enough_no_tiles():
    assert tile_boxes(300, 200) == []
    assert tile_boxes(199, 100) == []


def test_wide_tiles_full_height_4x3_cover_both_ends():
    boxes = tile_boxes(900, 100)  # 9:1 长卷
    assert all(b[1] == 0 and b[3] == 100 and b[2] - b[0] == 133 for b in boxes)
    assert boxes[0][0] == 0 and boxes[-1][2] == 900
    # 步长半窗:相邻块重叠,不留缝
    assert all(b2[0] <= b1[2] for b1, b2 in zip(boxes, boxes[1:]))


def test_tall_tiles_along_height():
    boxes = tile_boxes(100, 500)
    assert all(b[0] == 0 and b[2] == 100 for b in boxes)
    assert boxes[-1][3] == 500


class _Storage:
    def __init__(self):
        self.files = {}

    def put(self, key, data, content_type):
        self.files[key] = data

    def public_url(self, key):
        return f"https://r2/{key}"


@pytest.fixture()
def wide():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    Base.metadata.create_all(
        bind=engine,
        tables=[
            Museum.__table__,
            MuseumObject.__table__,
            ObjectImage.__table__,
            ObjectContentSection.__table__,
            CategorySection.__table__,
            SectionType.__table__,
            ObjectSuggestedQuestion.__table__,
            Artist.__table__,
        ],
    )
    s = sessionmaker(bind=engine)()
    m = upsert_museum(s, {"slug": "orangerie", "name_en": "Orangerie"})
    o = upsert_object(s, m.id, {"qid": "Q1", "title_en": "Water Lilies"})
    p = ObjectImage(
        object_id=o.id, role="primary", image_key="images/Q1/0", credit="GAP", sort=0
    )
    s.add(p)
    s.commit()
    return s, o, p


def test_add_tiles_writes_rows_files_vectors_once(wide):
    s, o, p = wide
    st, embedded = _Storage(), []
    img = Image.new("RGB", (900, 100))
    n = add_tiles(s, st, o, img, p, lambda db, row, data: embedded.append(row.id))
    s.commit()
    tiles = s.query(ObjectImage).filter_by(object_id=o.id, role="tile").all()
    assert n == len(tiles) == len(embedded) == len(tile_boxes(900, 100))
    assert all(t.sort >= 1000 and t.credit == "GAP" for t in tiles)
    assert set(st.files) == {f"{t.image_key}_large.jpg" for t in tiles}
    # 幂等:再跑不重复切
    assert add_tiles(s, st, o, img, p, lambda *a: None) == 0


def test_tiles_hidden_from_gallery_and_share(wide, monkeypatch):
    s, o, p = wide
    add_tiles(s, _Storage(), o, Image.new("RGB", (900, 100)), p, lambda *a: None)
    s.commit()
    monkeypatch.setattr(museum_repo, "get_object_storage", lambda: _Storage())
    content = museum_repo.get_object_content(s, "orangerie", "Q1", "en")
    assert len(content["images"]) == 1
    p.sort = 5000  # 排到切块之后:不排除 tile 的话分享会取到切块
    s.commit()
    assert share.primary_image(s, o).role == "primary"
