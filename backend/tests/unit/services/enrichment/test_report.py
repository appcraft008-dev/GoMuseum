from app.services.enrichment.report import build_report


def test_report_counts_coverage_and_distribution():
    objs = [
        {
            "qid": "Q1",
            "category": "painting",
            "title_zh": "A",
            "title_en": "A",
            "artist_zh": "x",
            "year": "1866",
            "image": {"source_url": "u"},
        },
        {
            "qid": "Q2",
            "category": "sculpture",
            "title_zh": None,
            "title_en": "B",
            "artist_zh": None,
            "year": None,
            "image": None,
        },
    ]
    rep = build_report("orsay", objs)
    assert rep["total"] == 2
    assert rep["coverage"]["image"] == 0.5
    assert rep["coverage"]["artist_zh"] == 0.5
    assert rep["coverage"]["title_zh"] == 0.5
    assert rep["category_dist"] == {"painting": 1, "sculpture": 1}
    assert "Q2" in rep["anomalies"]["missing_image"]


def test_report_renders_markdown():
    md = build_report(
        "orsay",
        [
            {
                "qid": "Q1",
                "category": "painting",
                "title_zh": "A",
                "title_en": "A",
                "artist_zh": "x",
                "year": "1",
                "image": {"source_url": "u"},
            }
        ],
        as_markdown=True,
    )
    assert "# 抽样报告: orsay" in md
    assert "覆盖率" in md
