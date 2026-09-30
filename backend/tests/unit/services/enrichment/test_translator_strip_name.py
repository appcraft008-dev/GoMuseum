"""strip_name:剥模型回贴的「Name:」标签(prompt 的 user 写成 `Name:\n{name}`,模型把它当成
要翻译的内容,it 译成「Nome:」—— prod 2026-09-30 实测 it 663 / fr 38 / es 19 条标题带着它)。"""

import pytest

from app.services.enrichment.translator import strip_name


@pytest.mark.parametrize(
    "raw,want",
    [
        ("Nome:\nPiatto con pesci dorati", "Piatto con pesci dorati"),
        ("Nom : Motif décoratif : fleur stylisée", "Motif décoratif : fleur stylisée"),
        ("Nombre:\nRetrato de familia", "Retrato de familia"),
        ("Name:\nFigure, Arms Raised", "Figure, Arms Raised"),
        ("이름: 쓰기 케이스-AF 5158", "쓰기 케이스-AF 5158"),
        ("名前: 職業", "職業"),
        ("《睡莲》", "睡莲"),
        # 对照:标题本身带冒号不能被剥
        ("Sketch: The Flowers", "Sketch: The Flowers"),
        ("Nomade: la route", "Nomade: la route"),
        (
            "Esquisse pour la Sorbonne : les Sciences",
            "Esquisse pour la Sorbonne : les Sciences",
        ),
    ],
)
def test_strip_name_removes_echoed_label(raw, want):
    assert strip_name(raw) == want
