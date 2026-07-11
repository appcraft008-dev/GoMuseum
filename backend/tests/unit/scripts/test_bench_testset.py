"""分层抽样:名作线=前200;非名作占70%;fame/dim 标注。"""

from scripts.recognition_bench.build_testset import stratified_sample


def _objects(n):
    return [
        {
            "qid": f"Q{i}",
            "popularity": n - i,
            "category": "painting" if i % 2 else "sculpture",
            "images": ["u"],
        }
        for i in range(n)
    ]


def test_stratified_ratio_and_tags():
    sample = stratified_sample(_objects(1000), n=100, seed=42)
    famous = [o for o in sample if o["fame"] == "famous"]
    nonfamous = [o for o in sample if o["fame"] == "nonfamous"]
    assert len(sample) == 100 and len(famous) == 30 and len(nonfamous) == 70
    assert all(o["dim"] in ("2d", "3d") for o in sample)


def test_small_pool_takes_what_pools_allow():
    # 40 件全落名作池(前200):名作配额取 30,非名作池空 → 共 30
    sample = stratified_sample(_objects(40), n=100, seed=42)
    assert len(sample) == 30
    assert all(o["fame"] == "famous" for o in sample)


def test_deterministic():
    a = [o["qid"] for o in stratified_sample(_objects(1000), n=100, seed=42)]
    b = [o["qid"] for o in stratified_sample(_objects(1000), n=100, seed=42)]
    assert a == b
